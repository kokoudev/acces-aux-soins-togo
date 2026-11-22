"""Projet 2 — Indicateurs d'accès aux soins par canton et par préfecture.

Définitions (numérateur / dénominateur / source) :
- hab_par_centre : population RGPH 2022 / nombre de formations « USP, CMS ou hôpital » (geodata PRISE)
- centres_10000 : nombre de ces formations pour 10 000 habitants
- dist_route_med_km : médiane, sur les localités du territoire, de la distance par la route à la
  formation « USP, CMS ou hôpital » la plus proche (analyse/distances.py)
- part_hab_5km / pop_5km (MESURE PRINCIPALE) : part et nombre d'habitants à plus de 5 km à vol d'oiseau
  d'une USP/CMS/hôpital, la population du canton étant répartie également entre ses localités
- part_loc_5km / part_loc_10km : part des localités à plus de 5 / 10 km par la route de cette formation
- dist_hopital_med_km : médiane de la distance par la route à l'hôpital le plus proche
- pop_5km_est : population du canton x part des localités à plus de 5 km (ESTIMATION : suppose une
  population égale entre les localités d'un canton)
- part_hab_5km_geodata : 100 - « proportion d'habitants à moins de 5 km d'un USP ou d'un hôpital »
  (indicateur publié par geodata, calculé avec la base de population de la plateforme, à vol d'oiseau)
- hab_par_personnel : population RGPH 2022 / (personnel des formations publiques + privées, geodata)
- pct_hab_reseau_bt : « proportion d'habitants à moins de 50 m du réseau BT » (geodata)
- taux_elec_pref_2021 : taux d'accès à l'électricité de la préfecture en 2021 (INSEED)

Sorties : data/indicateurs_cantons.parquet, data/indicateurs_prefectures.parquet
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"


def agreger_distances(d: pd.DataFrame, cle: str) -> pd.DataFrame:
    return d.groupby(cle).agg(
        nb_localites=("dist_route_km_soins", "size"),
        dist_route_med_km=("dist_route_km_soins", "median"),
        dist_vol_med_km=("dist_vol_km_soins", "median"),
        part_loc_5km=("dist_route_km_soins", lambda s: (s > 5).mean() * 100),
        part_loc_10km=("dist_route_km_soins", lambda s: (s > 10).mean() * 100),
        part_loc_5km_vol=("dist_vol_km_soins", lambda s: (s > 5).mean() * 100),
        dist_hopital_med_km=("dist_route_km_hopital", "median"),
        dist_hopital_vol_med_km=("dist_vol_km_hopital", "median"),
        part_loc_acces_reseau_2km=("acces_reseau_m", lambda s: (s > 2000).mean() * 100),
    )


def main() -> None:
    base = pd.read_parquet(DATA / "base_cantons.parquet")
    dist = pd.read_parquet(DATA / "distances_localites.parquet")
    fs = gpd.read_parquet(DATA / "formations_sanitaires.parquet")
    elec = pd.read_parquet(DATA / "electricite_prefecture.parquet")
    e21 = elec[elec.annee == 2021].set_index("prefecture_id")

    c = base[["canton_id", "canton", "commune_id", "commune", "prefecture_id", "prefecture", "region_id", "region",
              "superficie_km2", "population_2022", "population_estimee", "densite_hab_km2", "nb_fs",
              "nb_fs_usp", "nb_fs_hopital", "nb_fs_public", "nb_pharmacies", "km_total", "km_revetus",
              "geodata_pct_hab_5km_usp_hopital", "geodata_personnel_fs_publiques", "geodata_personnel_fs_privees",
              "geodata_pct_hab_50m_reseau_bt"]].copy()
    c["nb_centres"] = c.nb_fs_usp + c.nb_fs_hopital
    c["hab_par_centre"] = np.where(c.nb_centres > 0, c.population_2022 / c.nb_centres.replace(0, np.nan), np.nan)
    c["centres_10000"] = c.nb_centres / c.population_2022 * 1e4
    c["personnel"] = c.geodata_personnel_fs_publiques + c.geodata_personnel_fs_privees
    c["hab_par_personnel"] = c.population_2022 / c.personnel.replace(0, np.nan)
    c["personnel_10000"] = c.personnel / c.population_2022 * 1e4
    c["part_hab_5km_geodata"] = 100 - c.geodata_pct_hab_5km_usp_hopital
    c["pop_5km_geodata"] = c.population_2022 * c.part_hab_5km_geodata / 100
    c["pct_hab_reseau_bt"] = c.geodata_pct_hab_50m_reseau_bt
    c["km_route_km2"] = c.km_total / c.superficie_km2
    c = c.merge(agreger_distances(dist, "canton_id"), left_on="canton_id", right_index=True, how="left")
    c["pop_5km_est"] = c.population_2022 * c.part_loc_5km / 100
    # MESURE PRINCIPALE : à vol d'oiseau (norme « rayon d'action de 5 km » publiée sur geodata),
    # population du canton répartie également entre ses localités ; recalculable de bout en bout.
    c["part_hab_5km"] = c.part_loc_5km_vol
    c["pop_5km"] = c.population_2022 * c.part_hab_5km / 100
    c["taux_elec_pref_2021"] = c.prefecture_id.map(e21.taux_acces_pct)
    c["elec_valeur_de_zone"] = c.prefecture_id.map(e21.valeur_de_zone)
    c["aucun_centre"] = c.nb_centres == 0
    c.to_parquet(DATA / "indicateurs_cantons.parquet", index=False)

    # Préfectures : sommes puis ratios recalculés (pas de moyenne de ratios)
    s = c.groupby(["prefecture_id", "prefecture", "region"]).agg(
        population_2022=("population_2022", "sum"), superficie_km2=("superficie_km2", "sum"),
        nb_centres=("nb_centres", "sum"), nb_fs=("nb_fs", "sum"), nb_fs_hopital=("nb_fs_hopital", "sum"),
        personnel=("personnel", "sum"), pop_5km_geodata=("pop_5km_geodata", "sum"), pop_5km_est=("pop_5km_est", "sum"),
        pop_5km=("pop_5km", "sum"),
        km_total=("km_total", "sum"), nb_cantons=("canton_id", "size"),
        cantons_sans_centre=("aucun_centre", "sum")).reset_index()
    s["densite_hab_km2"] = s.population_2022 / s.superficie_km2
    s["hab_par_centre"] = s.population_2022 / s.nb_centres
    s["centres_10000"] = s.nb_centres / s.population_2022 * 1e4
    s["hab_par_personnel"] = s.population_2022 / s.personnel.replace(0, np.nan)
    s["personnel_10000"] = s.personnel / s.population_2022 * 1e4
    s["part_hab_5km_geodata"] = s.pop_5km_geodata / s.population_2022 * 100
    s["part_hab_5km"] = s.pop_5km / s.population_2022 * 100
    s["part_hab_5km_route"] = s.pop_5km_est / s.population_2022 * 100
    s["km_route_km2"] = s.km_total / s.superficie_km2
    dist_p = dist.merge(c[["canton_id", "prefecture_id"]], on="canton_id")
    s = s.merge(agreger_distances(dist_p, "prefecture_id"), left_on="prefecture_id", right_index=True, how="left")
    pref_bt = (c.pct_hab_reseau_bt * c.population_2022).groupby(c.prefecture_id).sum() / c.groupby("prefecture_id").population_2022.sum()
    s["pct_hab_reseau_bt"] = s.prefecture_id.map(pref_bt)  # moyenne pondérée par la population
    s["taux_elec_pref_2021"] = s.prefecture_id.map(e21.taux_acces_pct)
    s["elec_valeur_de_zone"] = s.prefecture_id.map(e21.valeur_de_zone)
    s.to_parquet(DATA / "indicateurs_prefectures.parquet", index=False)

    print(f"cantons : {len(c)} ; sans centre (USP/CMS/hôpital) : {int(c.aucun_centre.sum())} ; "
          f"population des cantons sans centre : {c.loc[c.aucun_centre, 'population_2022'].sum():,.0f}")
    print(f"population à plus de 5 km (geodata) : {c.pop_5km_geodata.sum():,.0f} "
          f"({c.pop_5km_geodata.sum() / c.population_2022.sum() * 100:.1f} %) ; "
          f"estimation localités > 5 km par la route : {c.pop_5km_est.sum():,.0f}")
    print(c[["hab_par_centre", "dist_route_med_km", "part_loc_5km", "hab_par_personnel", "part_hab_5km_geodata",
             "pct_hab_reseau_bt"]].describe().round(1).to_string())


if __name__ == "__main__":
    main()
