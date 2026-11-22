"""Projet 2 — Distance par la route de chaque localité à la formation sanitaire la plus proche.

Réseau : couche geodata « Routes - Réseau routier » (48 008 km). La couche n'est pas topologique
(les tronçons se croisent sans nœud commun). Reconstruction :
  1. découpage de toutes les lignes à leurs intersections (shapely.union_all) ;
  2. raccordement de chaque extrémité en impasse (degré 1) aux nœuds situés à moins de
     TOLERANCE_M mètres (raccords de saisie) ;
  3. conservation de la plus grande composante connexe.
Origines : localités géolocalisées (couche « Chefferie traditionnelle », 7 938 points) ; pour les
cantons sans localité (cantons urbains), le point représentatif du polygone.
Destinations (3 niveaux) : toute formation sanitaire ; USP/CMS ou hôpital ; hôpital seulement.
Distance = trajet hors réseau en ligne droite (origine -> nœud le plus proche) + chemin le plus
court sur le réseau + trajet hors réseau (nœud -> formation sanitaire). La distance à vol d'oiseau
est calculée en parallèle pour comparaison.

Sorties : data/distances_localites.parquet, data/distances_parametres.json
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

DATA = Path(__file__).resolve().parents[1] / "data"
CRS_M = "EPSG:32631"
TOLERANCE_M = 50
DESTINATIONS = {
    "fs": lambda f: f.index == f.index,                       # toute formation sanitaire
    "soins": lambda f: f.niveau_soins.isin(["usp", "hopital"]),  # USP/CMS ou hôpital
    "hopital": lambda f: f.niveau_soins == "hopital",
}


def construire_graphe() -> tuple[nx.Graph, dict]:
    r = gpd.read_parquet(DATA / "routes.parquet").to_crs(CRS_M)
    morceaux = shapely.get_parts(shapely.union_all(r.geometry.values))
    g = nx.Graph()
    for ligne in morceaux:
        cs = shapely.get_coordinates(ligne)
        a, b = tuple(np.round(cs[0], 1)), tuple(np.round(cs[-1], 1))
        if a != b:
            w = float(ligne.length)
            if not g.has_edge(a, b) or g[a][b]["w"] > w:
                g.add_edge(a, b, w=w)
    longueur_init = sum(d["w"] for *_, d in g.edges(data=True))
    noeuds = np.array(list(g.nodes))
    degre = np.array([g.degree(tuple(n)) for n in noeuds])
    raccords = 0
    for i, j in cKDTree(noeuds).query_pairs(TOLERANCE_M):
        if degre[i] == 1 or degre[j] == 1:
            g.add_edge(tuple(noeuds[i]), tuple(noeuds[j]), w=float(np.linalg.norm(noeuds[i] - noeuds[j])))
            raccords += 1
    principale = max(nx.connected_components(g), key=len)
    gp = g.subgraph(principale).copy()
    stats = {
        "tronçons_sources": int(len(r)), "segments_apres_decoupage": int(len(morceaux)),
        "tolerance_raccord_m": TOLERANCE_M, "raccords_ajoutes": raccords,
        "noeuds_composante_principale": gp.number_of_nodes(),
        "part_longueur_composante_principale": round(sum(d["w"] for *_, d in gp.edges(data=True)) / longueur_init, 4),
    }
    return gp, stats


def origines() -> gpd.GeoDataFrame:
    loc = gpd.read_parquet(DATA / "localites.parquet").to_crs(CRS_M)
    loc = loc[loc.canton_id.notna()][["canton_id", "localite_type", "geometry"]].assign(origine="localité")
    cantons = gpd.read_parquet(DATA / "limites_canton.parquet").to_crs(CRS_M)
    vides = cantons[~cantons.canton_id.isin(loc.canton_id)].copy()
    vides["geometry"] = vides.geometry.representative_point()
    vides = vides.assign(localite_type=None, origine="point représentatif du canton")[loc.columns]
    return pd.concat([loc, vides], ignore_index=True).pipe(gpd.GeoDataFrame, crs=CRS_M)


def main() -> None:
    g, stats = construire_graphe()
    noeuds = np.array(list(g.nodes))
    arbre = cKDTree(noeuds)
    org = origines()
    xy_o = shapely.get_coordinates(org.geometry.values)
    leg_o, idx_o = arbre.query(xy_o)
    out = org.drop(columns="geometry").copy()
    out["x"], out["y"] = xy_o[:, 0], xy_o[:, 1]
    out["acces_reseau_m"] = leg_o

    fs = gpd.read_parquet(DATA / "formations_sanitaires.parquet").to_crs(CRS_M)
    for nom, filtre in DESTINATIONS.items():
        dest = fs[filtre(fs)]
        xy_d = shapely.get_coordinates(dest.geometry.values)
        leg_d, idx_d = arbre.query(xy_d)
        h = g.copy()
        source = ("SOURCE",)
        for n_i, leg in zip(idx_d, leg_d):
            n = tuple(noeuds[n_i])
            if not h.has_edge(source, n) or h[source][n]["w"] > leg:
                h.add_edge(source, n, w=float(leg))
        dist = nx.single_source_dijkstra_path_length(h, source, weight="w")
        d_res = np.array([dist.get(tuple(noeuds[i]), np.inf) for i in idx_o])
        out[f"dist_route_km_{nom}"] = (d_res + leg_o) / 1000
        out[f"dist_vol_km_{nom}"] = cKDTree(xy_d).query(xy_o)[0] / 1000
        stats[f"destinations_{nom}"] = int(len(dest))
        print(f"{nom}: {len(dest)} destinations ; distance route médiane {np.median(out[f'dist_route_km_{nom}']):.2f} km")

    stats["origines"] = int(len(out))
    stats["origines_points_representatifs"] = int((out.origine != "localité").sum())
    stats["part_origines_acces_reseau_sup_2km"] = round(float((out.acces_reseau_m > 2000).mean()), 4)
    stats["rapport_median_route_sur_vol_soins"] = round(float(np.median(out.dist_route_km_soins / out.dist_vol_km_soins.clip(lower=0.05))), 3)
    out.to_parquet(DATA / "distances_localites.parquet", index=False)
    (DATA / "distances_parametres.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
