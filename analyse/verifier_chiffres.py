"""Contrôle qualité : recalcule indépendamment les chiffres clés du rapport et vérifie leur présence.

Repart des données de base (data/base_cantons.parquet du dépôt commun, distances par localité,
formations sanitaires) sans passer par les fichiers de résultats (docs/chiffres/). Le simulateur
est recalculé par une implémentation distincte (boucle simple, sans matrice creuse).
Écrit docs/verification_chiffres.csv.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

RACINE = Path(__file__).resolve().parents[1]
DATA = RACINE / "data"


def fr(x, dec):
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def simulateur_independant(d: pd.DataFrame, n: int) -> float:
    xy = d[["x", "y"]].to_numpy()
    voisins = cKDTree(xy).query_ball_point(xy, r=5000)
    w = np.where(d.dist_vol_km_soins <= 5, 0.0, d["pop"].to_numpy())
    total = 0.0
    for _ in range(n):
        gains = np.array([w[v].sum() for v in voisins])
        i = int(gains.argmax())
        total += gains[i]
        w[voisins[i]] = 0.0
    return total


def main() -> None:
    b = pd.read_parquet(DATA / "base_cantons.parquet")
    d = pd.read_parquet(DATA / "distances_localites.parquet")
    fs = gpd.read_parquet(DATA / "formations_sanitaires.parquet")
    src = pd.read_csv(RACINE / "dashboard" / "donnees" / "sources_utilisees.csv")
    rapport = (RACINE / "docs" / "RAPPORT_COMPLET.md").read_text(encoding="utf-8")

    n_loc = d.groupby("canton_id").size()
    d = d.merge(b[["canton_id", "prefecture", "population_2022"]], on="canton_id")
    d["pop"] = d.population_2022 / d.canton_id.map(n_loc)
    pop = b.population_2022.sum()
    loin_vol = d[d.dist_vol_km_soins > 5]["pop"].sum()
    loin_route = d[d.dist_route_km_soins > 5]["pop"].sum()
    nc = d[(d.dist_route_km_soins > 5) & (d.dist_vol_km_soins <= 5) & (d.acces_reseau_m > 1000)]["pop"].sum()
    pop5_geo = (b.population_2022 * (100 - b.geodata_pct_hab_5km_usp_hopital) / 100).sum()
    centres = b.nb_fs_usp + b.nb_fs_hopital
    kp = b[b.prefecture == "Kpendjal"]
    sans = b[centres == 0]
    part_pref = d.assign(l=d.dist_vol_km_soins > 5).groupby("prefecture").apply(
        lambda g: (g["pop"] * g.l).sum() / g["pop"].sum() * 100, include_groups=False)
    bt0 = b[b.geodata_pct_hab_50m_reseau_bt <= 0]
    fs_bt0 = fs[fs.canton_id.isin(bt0.canton_id)]
    loc5 = d.groupby("canton_id").apply(lambda g: (g.dist_vol_km_soins > 5).mean() * 100, include_groups=False)
    m = b.set_index("canton_id").assign(l=loc5)
    rho_bt = spearmanr(m.l, m.geodata_pct_hab_50m_reseau_bt).statistic
    gain10, gain50 = simulateur_independant(d, 10), simulateur_independant(d, 50)

    controles = [
        ("Population totale 2022", pop, 0),
        ("Chiffre principal : habitants à plus de 5 km (vol d'oiseau)", loin_vol, 0),
        ("Chiffre principal : part nationale (%)", loin_vol / pop * 100, 1),
        ("Borne basse geodata (%)", pop5_geo / pop * 100, 1),
        ("Borne haute par la route : habitants", loin_route, 0),
        ("Borne haute par la route (%)", loin_route / pop * 100, 1),
        ("Effet du réseau non connecté (points de %)", nc / pop * 100, 1),
        ("Habitants par centre, Togo", pop / centres.sum(), 0),
        ("Part maximale par préfecture (%)", part_pref.max(), 1),
        ("Kpendjal : habitants par centre", kp.population_2022.sum() / centres[kp.index].sum(), 0),
        ("Cantons sans USP, CMS ni hôpital", len(sans), 0),
        ("Habitants des cantons sans centre", sans.population_2022.sum(), 0),
        ("rho éloignement (principal) / réseau BT", rho_bt, 2),
        ("Distance médiane à l'hôpital, vol d'oiseau (km)", d.dist_vol_km_hopital.median(), 1),
        ("Simulateur : habitants gagnés avec 10 centres", gain10, 0),
        ("Simulateur : habitants gagnés avec 50 centres", gain50, 0),
        ("Simulateur : part restante avec 50 centres (%)", (loin_vol - gain50) / pop * 100, 1),
        ("Solaire : formations sanitaires ciblées", len(fs_bt0), 0),
        ("Solaire : habitants des cantons ciblés", bt0.population_2022.sum(), 0),
        ("Part des sources issues des 2 plateformes (%)", src.plateforme.isin(["opendata.gouv.tg", "geodata.gouv.tg"]).mean() * 100, 0),
    ]
    lignes = []
    for nom, val, dec in controles:
        texte = fr(val, dec)
        lignes.append({"controle": nom, "valeur_recalculee": round(float(val), 4), "texte_attendu": texte,
                       "present_dans_rapport": texte in rapport})
    res = pd.DataFrame(lignes)
    res.to_csv(RACINE / "docs" / "verification_chiffres.csv", index=False, encoding="utf-8")
    print(res.to_string())
    print("TOUS PRÉSENTS" if res.present_dans_rapport.all() else "ÉCARTS À EXAMINER")


if __name__ == "__main__":
    main()
