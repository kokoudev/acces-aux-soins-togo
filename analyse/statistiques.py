"""Projet 2 — Statistiques descriptives, corrélations de Spearman, valeurs aberrantes (cantons).

Corrélations : rho de Spearman, p-valeur, n (paires complètes). Formulation : « associé à ». Correction de Holm (tests multiples) et rho partiel à densité égale.
Réserve : les cantons voisins se ressemblent (dépendance spatiale), les p-valeurs sont optimistes.
Aberrants : règle de Tukey (au-delà de Q3 + 1,5 x IQR ou en deçà de Q1 - 1,5 x IQR). Ils sont
listés, pas supprimés.

Sorties : docs/chiffres/descriptif_cantons.csv, correlations_spearman.csv, valeurs_aberrantes.csv,
          comparaison_mesures_distance.csv
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RACINE = Path(__file__).resolve().parents[1]
DATA, CHIFFRES = RACINE / "data", RACINE / "docs" / "chiffres"

VARIABLES = {
    "densite_hab_km2": "Densité (hab./km²)",
    "part_hab_5km": "Habitants à plus de 5 km d'une USP, d'un CMS ou d'un hôpital (%, mesure principale)",
    "part_hab_5km_geodata": "Habitants à plus de 5 km d'une USP ou d'un hôpital (%, geodata)",
    "part_loc_5km": "Localités à plus de 5 km par la route (%)",
    "dist_route_med_km": "Distance médiane par la route (km)",
    "dist_hopital_med_km": "Distance médiane à l'hôpital (km)",
    "hab_par_centre": "Habitants par USP, CMS ou hôpital",
    "hab_par_personnel": "Habitants par agent de santé",
    "pct_hab_reseau_bt": "Habitants à moins de 50 m du réseau BT (%)",
    "km_route_km2": "Densité routière (km/km²)",
}


def main() -> None:
    CHIFFRES.mkdir(parents=True, exist_ok=True)
    c = pd.read_parquet(DATA / "indicateurs_cantons.parquet")
    d = pd.read_parquet(DATA / "distances_localites.parquet")

    desc = c[list(VARIABLES)].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).T
    desc.insert(0, "libelle", desc.index.map(VARIABLES))
    desc.round(2).to_csv(CHIFFRES / "descriptif_cantons.csv", encoding="utf-8")

    lignes = []
    for a, b in combinations(VARIABLES, 2):
        m = c[[a, b]].dropna()
        r = spearmanr(m[a], m[b])
        lignes.append({"variable_1": a, "variable_2": b, "libelle_1": VARIABLES[a], "libelle_2": VARIABLES[b],
                       "rho": round(float(r.statistic), 3), "p_valeur": float(r.pvalue), "n": len(m),
                       "significatif_5pct": bool(r.pvalue < 0.05)})
    corr = pd.DataFrame(lignes).sort_values("rho", key=abs, ascending=False)
    # correction de Holm pour tests multiples
    m = len(corr)
    ordre = corr.p_valeur.rank(method="first").astype(int)
    p_tri = corr.p_valeur.sort_values()
    holm = (p_tri * (m - np.arange(m))).cummax().clip(upper=1)
    corr["p_holm"] = holm.reindex(corr.index)
    corr["significatif_holm_5pct"] = corr.p_holm < 0.05
    # corrélation partielle de rang, à densité égale (résidus des rangs)
    def partielle(a, b):
        mm = c[[a, b, "densite_hab_km2"]].dropna().rank()
        res = lambda y: y - np.polyval(np.polyfit(mm.densite_hab_km2, y, 1), mm.densite_hab_km2)  # noqa: E731
        return float(np.corrcoef(res(mm[a]), res(mm[b]))[0, 1])
    corr["rho_partiel_densite"] = [round(partielle(a, b), 3) if "densite_hab_km2" not in (a, b) else None
                                   for a, b in zip(corr.variable_1, corr.variable_2)]
    corr.to_csv(CHIFFRES / "correlations_spearman.csv", index=False, encoding="utf-8")

    ab = []
    for v in VARIABLES:
        s = c[v].dropna()
        q1, q3 = s.quantile([0.25, 0.75])
        bas, haut = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        for _, r in c[(c[v] > haut) | (c[v] < bas)].iterrows():
            ab.append({"variable": v, "libelle": VARIABLES[v], "canton_id": r.canton_id, "canton": r.canton,
                       "prefecture": r.prefecture, "valeur": round(float(r[v]), 2),
                       "sens": "haut" if r[v] > haut else "bas", "seuil": round(float(haut if r[v] > haut else bas), 2)})
    pd.DataFrame(ab).to_csv(CHIFFRES / "valeurs_aberrantes.csv", index=False, encoding="utf-8")

    # Comparaison des mesures d'éloignement (borne basse / borne haute)
    vol = d.groupby("canton_id").dist_vol_km_soins.apply(lambda s: (s > 5).mean() * 100)
    c["part_loc_5km_vol"] = c.canton_id.map(vol)
    comp = pd.DataFrame([
        {"mesure": "geodata : habitants à plus de 5 km (vol d'oiseau, pondéré par la population)",
         "population": c.pop_5km_geodata.sum(), "part_pct": c.pop_5km_geodata.sum() / c.population_2022.sum() * 100},
        {"mesure": "localités à plus de 5 km à vol d'oiseau, population répartie également entre localités",
         "population": (c.population_2022 * c.part_loc_5km_vol / 100).sum(),
         "part_pct": (c.population_2022 * c.part_loc_5km_vol / 100).sum() / c.population_2022.sum() * 100},
        {"mesure": "localités à plus de 5 km par la route, population répartie également entre localités",
         "population": c.pop_5km_est.sum(), "part_pct": c.pop_5km_est.sum() / c.population_2022.sum() * 100},
    ])
    comp["population"] = comp.population.round(0).astype(int)
    comp["part_pct"] = comp.part_pct.round(1)
    r1 = spearmanr(c.part_loc_5km_vol, c.part_hab_5km_geodata)
    r2 = spearmanr(c.part_loc_5km, c.part_hab_5km_geodata)
    comp["rho_avec_geodata_par_canton"] = [1.0, round(float(r1.statistic), 3), round(float(r2.statistic), 3)]
    comp.to_csv(CHIFFRES / "comparaison_mesures_distance.csv", index=False, encoding="utf-8")
    print(comp.to_string())
    print(corr.head(12)[["variable_1", "variable_2", "rho", "p_valeur", "n"]].to_string())
    print("aberrants par variable :", pd.DataFrame(ab).variable.value_counts().to_dict())


if __name__ == "__main__":
    main()
