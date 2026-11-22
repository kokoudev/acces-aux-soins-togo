"""Projet 2 — Solutions chiffrées : simulateur d'implantation, cantons sans centre, priorité solaire,
et clarification du message sur les distances. Données déjà téléchargées uniquement.

Hypothèses communes (mesure principale) :
- un habitant est « couvert » si une USP, un CMS ou un hôpital est à 5 km ou moins à vol d'oiseau
  (norme du « rayon d'action théorique de 5 km » publiée sur geodata) ;
- la population de chaque canton (RGPH-5 2022) est répartie également entre ses localités
  géolocalisées (chefferies) — hypothèse forte, rappelée dans chaque limite.

1. Décomposition des distances : part de l'estimation haute (par la route) qui vient de localités
   éloignées même à vol d'oiseau, de localités loin du réseau routier connecté, ou de détours.
2. Simulateur glouton : à chaque étape, on ajoute un centre sur la chefferie qui fait passer le plus
   d'habitants encore non couverts sous les 5 km. Résultats précalculés pour N = 1 à 50.
   (Algorithme glouton : solution approchée, garantie d'au moins 63 % de l'optimum pour ce type de
   problème de couverture maximale.)
3. Cantons sans USP, CMS ni hôpital : proposition « nouvelle USP » ou « cliniques mobiles » selon une
   règle explicite (voir REGLE_USP).
4. Priorité solaire : formations sanitaires situées dans les cantons où aucun habitant (0 %) ne vit à
   moins de 50 m du réseau basse tension (indicateur geodata).

Sorties : data/solutions_*.parquet ; docs/chiffres/solutions_*.csv et decomposition_distances.csv
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial import cKDTree

RACINE = Path(__file__).resolve().parents[1]
DATA, CH = RACINE / "data", RACINE / "docs" / "chiffres"
RAYON_M = 5000
N_MAX = 50
SEUILS_RESEAU_M = [500, 1000, 2000]
SEUIL_RESEAU_REF_M = 1000
SEUIL_BT_PCT = 0  # cantons où 0 % des habitants vivent à moins de 50 m du réseau BT


def localites_ponderees() -> pd.DataFrame:
    d = pd.read_parquet(DATA / "distances_localites.parquet")
    c = pd.read_parquet(DATA / "indice_cantons.parquet")[["canton_id", "canton", "prefecture_id", "prefecture",
                                                           "region", "population_2022"]]
    n = d.groupby("canton_id").size().rename("nb_loc")
    d = d.merge(c, on="canton_id").merge(n, left_on="canton_id", right_index=True)
    d["pop"] = d.population_2022 / d.nb_loc
    d["couverte"] = d.dist_vol_km_soins <= RAYON_M / 1000
    loc = gpd.read_parquet(DATA / "localites.parquet").to_crs("EPSG:32631")
    loc = loc[loc.canton_id.notna()].reset_index(drop=True)
    # distances_localites conserve l'ordre et les coordonnées des localités : on récupère leur nom
    vides = {"", "n/a", "na", "nsp", "none", "nan"}

    def premier_nom(r):
        for col in ("village_nom", "quartier_nom", "ville_nom"):
            v = r[col]
            if v is not None and str(v).strip().lower() not in vides:
                return str(v).strip()
        return "localité sans nom"
    nom = loc.apply(premier_nom, axis=1)
    if len(loc) == len(d) and np.allclose(loc.geometry.x.values, d.x.values):
        d["nom_localite"] = nom.astype(str).values
    else:
        d["nom_localite"] = "localité"
    return d


def decomposition(d: pd.DataFrame) -> pd.DataFrame:
    tot = d["pop"].sum()
    route = d[d.dist_route_km_soins > 5]
    lignes = [
        ("Estimation haute : habitants à plus de 5 km par la route", route["pop"].sum(), "toutes"),
        ("… dont aussi à plus de 5 km à vol d'oiseau (éloignement réel)", route[route.dist_vol_km_soins > 5]["pop"].sum(), "toutes"),
    ]
    for s in SEUILS_RESEAU_M:
        nc = route[(route.dist_vol_km_soins <= 5) & (route.acces_reseau_m > s)]["pop"].sum()
        lignes.append((f"… dont à moins de 5 km à vol d'oiseau mais à plus de {s} m du réseau routier connecté", nc, f"seuil {s} m"))
    det = route[(route.dist_vol_km_soins <= 5) & (route.acces_reseau_m <= SEUIL_RESEAU_REF_M)]["pop"].sum()
    lignes.append((f"… dont à moins de 5 km à vol d'oiseau et à moins de {SEUIL_RESEAU_REF_M} m du réseau (détours du réseau)", det,
                   f"seuil {SEUIL_RESEAU_REF_M} m"))
    out = pd.DataFrame(lignes, columns=["composante", "habitants", "seuil"])
    out["part_population_pct"] = out.habitants / tot * 100
    out["part_estimation_haute_pct"] = out.habitants / route["pop"].sum() * 100
    out["habitants"] = out.habitants.round(0).astype(int)
    return out.round(2)


def simulateur(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    xy = d[["x", "y"]].to_numpy()
    voisins = cKDTree(xy).query_ball_point(xy, r=RAYON_M)
    lignes = np.repeat(np.arange(len(xy)), [len(v) for v in voisins])
    colonnes = np.concatenate(voisins)
    A = sparse.csr_matrix((np.ones(len(colonnes)), (lignes, colonnes)), shape=(len(xy), len(xy)))
    w = np.where(d.couverte, 0.0, d["pop"].to_numpy())
    pop_tot = d["pop"].sum()
    non_couverts0 = w.sum()
    prefs = d.groupby("prefecture_id").agg(prefecture=("prefecture", "first"), population=("pop", "sum"))
    pref_idx = d.prefecture_id.to_numpy()

    def etat_prefs(w_courant, n):
        nc = pd.Series(w_courant, index=d.index).groupby(pref_idx).sum()
        t = prefs.copy()
        t["n_centres_ajoutes"] = n
        t["habitants_plus_5km"] = nc.reindex(t.index).fillna(0)
        t["part_plus_5km_pct"] = t.habitants_plus_5km / t.population * 100
        return t.reset_index()

    sites, etats = [], [etat_prefs(w, 0)]
    cumul = 0.0
    # rang du site qui couvre la localité : 0 = déjà couverte, NaN = non couverte après N_MAX sites
    d["rang_couverture"] = np.where(d.couverte, 0.0, np.nan)
    for n in range(1, N_MAX + 1):
        gains = A @ w
        i = int(np.argmax(gains))
        gain = float(gains[i])
        couverts = A[i].indices
        nouveaux = couverts[w[couverts] > 0]
        cantons_touches = d.iloc[nouveaux].canton_id.nunique()
        d.iloc[nouveaux, d.columns.get_loc("rang_couverture")] = float(n)
        w[couverts] = 0.0
        cumul += gain
        r = d.iloc[i]
        sites.append({"rang": n, "nom_localite": r.nom_localite, "localite_type": r.localite_type, "canton_id": r.canton_id,
                      "canton": r.canton, "prefecture": r.prefecture, "region": r.region, "x": r.x, "y": r.y,
                      "habitants_gagnes": gain, "localites_gagnees": len(nouveaux), "cantons_touches": cantons_touches,
                      "habitants_gagnes_cumules": cumul, "habitants_plus_5km_restants": w.sum(),
                      "part_nationale_plus_5km_pct": w.sum() / pop_tot * 100})
        etats.append(etat_prefs(w, n))
    s = pd.DataFrame(sites)
    pts = gpd.GeoSeries(gpd.points_from_xy(s.x, s.y), crs="EPSG:32631").to_crs("EPSG:4326")
    s["lon"], s["lat"] = pts.x.round(5), pts.y.round(5)
    s.insert(0, "part_nationale_initiale_pct", non_couverts0 / pop_tot * 100)
    e = pd.concat(etats, ignore_index=True)
    return s.round(3), e.round(3)


def cantons_sans_centre(d: pd.DataFrame, sites: pd.DataFrame) -> pd.DataFrame:
    c = pd.read_parquet(DATA / "indice_cantons.parquet")
    hab_par_centre_nat = c.population_2022.sum() / c.nb_centres.sum()
    s = c[c.aucun_centre].copy()
    s["formations_autres"] = s.nb_fs  # cases de santé, infirmeries
    s["habitants_plus_5km"] = s.pop_5km
    s["proposition"] = np.where(
        (s.population_2022 >= hab_par_centre_nat) & (s.part_hab_5km > 50), "Nouvelle USP", "Cliniques mobiles (stratégie avancée)")
    s["justification"] = np.where(
        s.proposition == "Nouvelle USP",
        f"population ≥ {hab_par_centre_nat:.0f} (habitants par centre au niveau national) et plus de la moitié à plus de 5 km",
        np.where(s.part_hab_5km > 50, f"population < {hab_par_centre_nat:.0f} : trop faible pour un centre fixe à charge moyenne",
                 "la majorité des habitants a déjà un centre à moins de 5 km dans un canton voisin"))
    # Lien avec le simulateur : premier site (rang) qui fait passer des habitants du canton sous les 5 km,
    # et part des habitants éloignés du canton couverts par les 50 sites (le site peut être dans un canton voisin)
    loin = d[(~d.couverte) & d.canton_id.isin(s.canton_id)]
    s["simulateur_premier_rang"] = s.canton_id.map(loin.groupby("canton_id").rang_couverture.min())
    couv50 = loin[loin.rang_couverture.notna()].groupby("canton_id")["pop"].sum()
    s["simulateur_part_eloignes_couverts_n50_pct"] = (s.canton_id.map(couv50).fillna(0) /
                                                      s.habitants_plus_5km.replace(0, np.nan) * 100)
    cols = ["canton_id", "canton", "prefecture", "region", "population_2022", "population_estimee", "formations_autres",
            "part_hab_5km", "habitants_plus_5km", "dist_route_med_km", "proposition", "justification",
            "simulateur_premier_rang", "simulateur_part_eloignes_couverts_n50_pct"]
    return s[cols].sort_values("habitants_plus_5km", ascending=False).round(1)


def priorite_solaire() -> tuple[pd.DataFrame, pd.DataFrame]:
    c = pd.read_parquet(DATA / "indice_cantons.parquet")
    fs = gpd.read_parquet(DATA / "formations_sanitaires.parquet")
    cibles = c[c.pct_hab_reseau_bt <= SEUIL_BT_PCT]
    f = fs[fs.canton_id.isin(cibles.canton_id)].merge(
        c[["canton_id", "canton", "prefecture", "region", "population_2022", "pct_hab_reseau_bt"]], on="canton_id")
    f = pd.DataFrame({"nom": f.nom_fs, "type": f.type_harmonise, "niveau": f.niveau_soins, "secteur": f.secteur_harmonise,
                      "canton": f.canton, "prefecture": f.prefecture, "region": f.region,
                      "population_canton": f.population_2022.round(0), "pct_hab_reseau_bt": f.pct_hab_reseau_bt,
                      "lon": f.geometry.x.round(5), "lat": f.geometry.y.round(5)})
    f = f.sort_values(["niveau", "population_canton"], ascending=[True, False])
    resume = pd.DataFrame([{
        "cantons_cibles": len(cibles), "population_cantons_cibles": round(float(cibles.population_2022.sum())),
        "formations_sanitaires": len(f), "dont_usp_cms": int((f.niveau == "usp").sum()),
        "dont_hopitaux": int((f.niveau == "hopital").sum()), "dont_publiques": int((f.secteur == "Public").sum()),
        "prefectures_concernees": f.prefecture.nunique()}])
    return f, resume


def main() -> None:
    CH.mkdir(parents=True, exist_ok=True)
    d = localites_ponderees()
    dec = decomposition(d)
    dec.to_csv(CH / "decomposition_distances.csv", index=False, encoding="utf-8")
    sites, etats = simulateur(d)
    sites.to_csv(CH / "solutions_simulateur_sites.csv", index=False, encoding="utf-8")
    etats.to_csv(CH / "solutions_simulateur_prefectures.csv", index=False, encoding="utf-8")
    pts = gpd.GeoSeries(gpd.points_from_xy(d.x, d.y), crs="EPSG:32631").to_crs("EPSG:4326")
    pd.DataFrame({"lon": pts.x.round(5), "lat": pts.y.round(5), "nom_localite": d.nom_localite, "canton": d.canton,
                  "prefecture": d.prefecture, "pop": d["pop"].round(1), "rang_couverture": d.rang_couverture}) \
        .to_parquet(DATA / "solutions_localites.parquet", index=False)
    sc = cantons_sans_centre(d, sites)
    sc.to_csv(CH / "solutions_cantons_sans_centre.csv", index=False, encoding="utf-8")
    sol, sol_res = priorite_solaire()
    sol.to_csv(CH / "solutions_priorite_solaire.csv", index=False, encoding="utf-8")
    sol_res.to_csv(CH / "solutions_priorite_solaire_resume.csv", index=False, encoding="utf-8")
    print(dec.to_string())
    print(sites[["rang", "nom_localite", "canton", "prefecture", "habitants_gagnes", "habitants_gagnes_cumules",
                 "part_nationale_plus_5km_pct"]].iloc[[0, 1, 2, 4, 9, 19, 29, 49]].to_string())
    print(sc[["canton", "prefecture", "population_2022", "part_hab_5km", "proposition", "simulateur_premier_rang",
              "simulateur_part_eloignes_couverts_n50_pct"]].to_string())
    print(sol_res.to_string())


if __name__ == "__main__":
    main()
