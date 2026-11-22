"""Projet 2 — Indice de priorité d'accès aux soins, test de sensibilité et typologie des cantons.

Indice (0 = meilleure situation, 100 = plus prioritaire), trois dimensions :
- Éloignement : rang de la mesure principale (habitants à plus de 5 km à vol d'oiseau d'une USP, d'un
  CMS ou d'un hôpital). La mesure par la route n'entre pas dans l'indice : elle est biaisée là où le
  réseau routier publié n'est pas connecté ;
- Capacité : moyenne des rangs de « habitants par USP/CMS/hôpital » et « habitants par agent de santé »
  (un canton sans centre reçoit le rang le plus défavorable ; un personnel nul dans un canton qui a des
  centres est traité comme une donnée manquante) ;
- Électricité : rang de « 100 - habitants à moins de 50 m du réseau BT » (un centre de santé sans
  électricité rend un service limité : conservation des vaccins, éclairage, matériel).
Normalisation par rangs centiles (0-100) : robuste aux valeurs extrêmes, nombreuses ici (voir
valeurs_aberrantes.csv). Pondération de référence : égale entre les trois dimensions (aucune
justification externe ne permet de préférer une dimension).

Sensibilité : 4 variantes (éloignement renforcé, sans électricité, normalisation min-max,
capacité renforcée) ; corrélation de rang avec la référence et recouvrement du top 20.

Typologie : k-means (graine 42) sur les 3 dimensions standardisées et la densité (log) ;
k choisi parmi 3 à 6 : plus petit k dont la silhouette est à moins de 0,01 du maximum.

Sorties : data/indice_cantons.parquet ; docs/chiffres/indice_classement_cantons.csv,
          sensibilite_indice.csv, typologie_choix_k.csv, typologie_profils.csv
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

RACINE = Path(__file__).resolve().parents[1]
DATA, CHIFFRES = RACINE / "data", RACINE / "docs" / "chiffres"
GRAINE = 42


def rang(s: pd.Series, pire_si_nan: bool = True) -> pd.Series:
    """Rang centile 0-100, valeur haute = situation défavorable."""
    s = s.copy()
    if pire_si_nan:
        s = s.fillna(s.max() * 10 if s.notna().any() else 0)
    return s.rank(pct=True, method="average") * 100


def minmax(s: pd.Series) -> pd.Series:
    s = s.fillna(s.max())
    return (s - s.min()) / (s.max() - s.min()) * 100


def dimensions(c: pd.DataFrame, norm=rang) -> pd.DataFrame:
    d = pd.DataFrame(index=c.index)
    # mesure principale uniquement (vol d'oiseau) : la mesure par la route est biaisée là où le réseau
    # routier publié n'est pas connecté (ex. Mô, Kpendjal) ; elle reste une borne haute, hors indice
    d["eloignement"] = norm(c.part_hab_5km)
    hc = c.hab_par_centre.where(~c.aucun_centre)          # aucun centre -> pire rang
    hp = c.hab_par_personnel
    # personnel = 0 alors que le canton a des centres : donnée manquante probable (pas un vrai zéro) ;
    # la capacité ne retient alors que les habitants par centre. Sans centre ni personnel : pire rang.
    manque_perso = c.personnel.fillna(0).eq(0) & (c.nb_centres > 0)
    rc, rp = norm(hc), norm(hp)
    d["capacite"] = ((rc + rp) / 2).where(~manque_perso, rc)
    d["electricite"] = norm(100 - c.pct_hab_reseau_bt)
    return d


def indice(d: pd.DataFrame, poids: dict[str, float]) -> pd.Series:
    tot = sum(poids.values())
    return sum(d[k] * w for k, w in poids.items()) / tot


def nommer_groupes(prof: pd.DataFrame) -> dict[int, str]:
    """Nom descriptif attribué par règle, valable quel que soit k :
    - le groupe à la densité médiane la plus forte -> « Villes » ;
    - pour les autres, le nom liste les dimensions dont le score moyen dépasse 50 (situation plus
      défavorable que la moitié des cantons)."""
    noms = {}
    ville = prof.densite_mediane.idxmax()
    lib = {"dim_eloignement": "éloignés des soins", "dim_capacite": "sous-équipés",
           "dim_electricite": "loin du réseau électrique"}
    for g in prof.index:
        handicaps = [lib[d] for d in lib if prof.loc[g, d] > 50]
        if g == ville:
            noms[g] = "Villes bien desservies" if not handicaps else "Villes : " + ", ".join(handicaps)
        elif not handicaps:
            noms[g] = "Cantons ruraux proches et dotés"
        elif len(handicaps) == 3:
            noms[g] = "Cantons cumulant éloignement, sous-équipement et absence de réseau"
        else:
            noms[g] = "Cantons " + " et ".join(handicaps)
    return noms


def main() -> None:
    CHIFFRES.mkdir(parents=True, exist_ok=True)
    c = pd.read_parquet(DATA / "indicateurs_cantons.parquet")
    d = dimensions(c)
    ref = {"eloignement": 1, "capacite": 1, "electricite": 1}
    c[["dim_eloignement", "dim_capacite", "dim_electricite"]] = d.values
    c["indice_priorite"] = indice(d, ref)
    c["rang_priorite"] = c.indice_priorite.rank(ascending=False, method="min").astype(int)

    variantes = {
        "éloignement renforcé (50/25/25)": (d, {"eloignement": 2, "capacite": 1, "electricite": 1}),
        "sans électricité (50/50/0)": (d, {"eloignement": 1, "capacite": 1}),
        "capacité renforcée (25/50/25)": (d, {"eloignement": 1, "capacite": 2, "electricite": 1}),
        "normalisation min-max (égale)": (dimensions(c, minmax), ref),
    }
    top_ref = set(c.nlargest(20, "indice_priorite").canton_id)
    sens = []
    for nom, (dd, w) in variantes.items():
        v = indice(dd, w)
        top = set(c.loc[v.nlargest(20).index, "canton_id"])
        sens.append({"variante": nom, "rho_spearman_avec_reference": round(float(spearmanr(v, c.indice_priorite).statistic), 3),
                     "top20_communs_avec_reference": len(top & top_ref)})
    sens = pd.DataFrame(sens)
    sens.to_csv(CHIFFRES / "sensibilite_indice.csv", index=False, encoding="utf-8")
    # Robustesse par canton : nombre de variantes (sur 5, référence incluse) où il est dans le top 20
    presence = pd.Series(0, index=c.index)
    for dd, w in [(d, ref), *variantes.values()]:
        presence[indice(dd, w).nlargest(20).index] += 1
    c["top20_nb_variantes"] = presence

    # Typologie
    X = StandardScaler().fit_transform(np.column_stack([d.values, np.log10(c.densite_hab_km2)]))
    choix = []
    for k in range(3, 7):
        km = KMeans(n_clusters=k, n_init=50, random_state=GRAINE).fit(X)
        choix.append({"k": k, "silhouette": round(float(silhouette_score(X, km.labels_)), 3), "inertie": round(float(km.inertia_), 1),
                      "taille_min_groupe": int(np.bincount(km.labels_).min())})
    choix = pd.DataFrame(choix)
    choix.to_csv(CHIFFRES / "typologie_choix_k.csv", index=False, encoding="utf-8")
    # Règle : plus petit k dont la silhouette est à moins de 0,01 du maximum (les écarts plus fins ne
    # sont pas significatifs avec 396 cantons ; moins de groupes = typologie plus lisible)
    k = int(choix[choix.silhouette >= choix.silhouette.max() - 0.01].k.min())
    km = KMeans(n_clusters=k, n_init=50, random_state=GRAINE).fit(X)
    c["groupe"] = km.labels_
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import adjusted_rand_score
    graines = [adjusted_rand_score(km.labels_, KMeans(n_clusters=k, n_init=50, random_state=g).fit(X).labels_)
               for g in range(1, 11)]
    ward = AgglomerativeClustering(n_clusters=k, linkage="ward").fit(X).labels_
    pd.DataFrame([{"k": k, "silhouette_kmeans": round(float(silhouette_score(X, km.labels_)), 3),
                   "ari_min_10_graines": round(min(graines), 3),
                   "silhouette_ward": round(float(silhouette_score(X, ward)), 3),
                   "ari_kmeans_ward": round(float(adjusted_rand_score(km.labels_, ward)), 3)}])         .to_csv(CHIFFRES / "typologie_stabilite.csv", index=False, encoding="utf-8")
    prof = c.groupby("groupe").agg(
        cantons=("canton_id", "size"), population=("population_2022", "sum"),
        densite_mediane=("densite_hab_km2", "median"), part_hab_5km_med=("part_hab_5km", "median"),
        part_hab_5km_geodata_med=("part_hab_5km_geodata", "median"),
        part_loc_5km_med=("part_loc_5km", "median"), dist_route_med_km=("dist_route_med_km", "median"),
        hab_par_centre_med=("hab_par_centre", "median"), hab_par_personnel_med=("hab_par_personnel", "median"),
        pct_hab_reseau_bt_med=("pct_hab_reseau_bt", "median"), indice_moyen=("indice_priorite", "mean"),
        dim_eloignement=("dim_eloignement", "mean"), dim_capacite=("dim_capacite", "mean"),
        dim_electricite=("dim_electricite", "mean")).round(1)
    noms = nommer_groupes(prof)
    prof.insert(0, "nom_groupe", prof.index.map(noms))
    c["nom_groupe"] = c.groupe.map(noms)
    prof.to_csv(CHIFFRES / "typologie_profils.csv", encoding="utf-8")

    c.to_parquet(DATA / "indice_cantons.parquet", index=False)
    cols = ["rang_priorite", "canton_id", "canton", "commune", "prefecture", "region", "population_2022",
            "indice_priorite", "dim_eloignement", "dim_capacite", "dim_electricite", "part_hab_5km_geodata",
            "part_loc_5km", "dist_route_med_km", "hab_par_centre", "hab_par_personnel", "pct_hab_reseau_bt",
            "pop_5km_geodata", "top20_nb_variantes", "groupe", "nom_groupe"]
    c.sort_values("rang_priorite")[cols].round(2).to_csv(CHIFFRES / "indice_classement_cantons.csv", index=False, encoding="utf-8")
    print(choix.to_string()); print("k retenu :", k)
    print(sens.to_string()); print(prof.T.to_string())


if __name__ == "__main__":
    main()
