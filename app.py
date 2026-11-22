"""Tableau de bord — L'accès aux soins au Togo (Projet 2, Data Challenge Togo AI Lab).

Lancement local : python dashboard/app.py  ->  http://127.0.0.1:8050
Production (Render) : gunicorn --chdir dashboard app:server
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))  # theme.py, quel que soit le mode de lancement
import theme as T  # noqa: E402

ICI = Path(__file__).resolve().parent
D = ICI / "donnees"

# ---------------------------------------------------------------------------- données
CANTONS = pd.read_csv(D / "cantons.csv", dtype={"canton_id": str, "prefecture_id": str})
PREFS = pd.read_csv(D / "prefectures.csv", dtype={"prefecture_id": str})
CENTRES = pd.read_csv(D / "centres.csv")
GROUPES = pd.read_csv(D / "groupes.csv")
SENS = pd.read_csv(D / "sensibilite_indice.csv")
COMP = pd.read_csv(D / "comparaison_mesures_distance.csv")
SOURCES = pd.read_csv(D / "sources_utilisees.csv")
META = json.loads((D / "meta.json").read_text(encoding="utf-8"))
SIM_SITES = pd.read_csv(D / "solutions_simulateur_sites.csv")
SIM_PREFS = pd.read_csv(D / "solutions_simulateur_prefectures.csv", dtype={"prefecture_id": str})
SIM_LOC = pd.read_csv(D / "solutions_localites.csv")
SANS_CENTRE = pd.read_csv(D / "solutions_cantons_sans_centre.csv")
SOLAIRE = pd.read_csv(D / "solutions_priorite_solaire.csv")
SOLAIRE_RES = pd.read_csv(D / "solutions_priorite_solaire_resume.csv").iloc[0]
DECOMP = pd.read_csv(D / "decomposition_distances.csv")
STAB = pd.read_csv(D / "typologie_stabilite.csv").iloc[0]
NAT = META["national"]
GEO_CANTONS = json.loads((D / "cantons.geojson").read_text(encoding="utf-8"))
GEO_PREFS = json.loads((D / "prefectures.geojson").read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------- charte
# Toutes les couleurs viennent de theme.py (aucune valeur hexadécimale ici)
ENCRE, ENCRE2, ENCRE3, BORDURE = T.ENCRE, T.ENCRE_2, T.ENCRE_3, T.BORDURE
CARTE_BLANC, SURFACE = T.CARTE, T.SURFACE
HAUTEUR_CARTE, HAUTEUR_NUAGE, HAUTEUR_PROFILS, HAUTEUR_COURBE = 600, 480, 400, 300
# Groupes rangés par indice moyen croissant -> rampe ordinale verte (validée)
ORDRE_GROUPES = GROUPES.sort_values("indice_moyen").nom_groupe.tolist()
COULEUR_GROUPE = dict(zip(ORDRE_GROUPES, T.COULEURS_GROUPES_PAR_RANG))
SYMBOLE_GROUPE = dict(zip(ORDRE_GROUPES, T.SYMBOLES_GROUPES_PAR_RANG))
POLICE = '"Source Sans 3", "Segoe UI", Arial, sans-serif'
SOURCE_STD = "Source : geodata.gouv.tg (campagne PRISE 2021-2022) ; INSEED, RGPH-5 2022 (opendata.gouv.tg) ; calculs de l'équipe."

INDICATEURS = {
    "indice_priorite": {"lib": "Indice de priorité d'accès aux soins (0-100)", "fmt": ".1f", "unite": "", "canton_seul": True,
                        "sens": "haut = plus prioritaire"},
    "part_hab_5km": {"lib": "Habitants à plus de 5 km d'une USP, d'un CMS ou d'un hôpital (%)", "fmt": ".1f", "unite": " %"},
    "pop_5km": {"lib": "Habitants à plus de 5 km d'une USP, d'un CMS ou d'un hôpital (nombre)", "fmt": ",.0f", "unite": ""},
    "part_hab_5km_geodata": {"lib": "Borne basse geodata : habitants à plus de 5 km (%)", "fmt": ".1f", "unite": " %"},
    "dist_route_med_km": {"lib": "Borne haute : distance médiane par la route au centre (km)", "fmt": ".1f", "unite": " km"},
    "dist_hopital_vol_med_km": {"lib": "Distance médiane à vol d'oiseau à l'hôpital le plus proche (km)", "fmt": ".1f", "unite": " km"},
    "hab_par_centre": {"lib": "Habitants par centre de santé (USP, CMS, hôpital)", "fmt": ",.0f", "unite": ""},
    "hab_par_personnel": {"lib": "Habitants par agent de santé", "fmt": ",.0f", "unite": ""},
    "pct_hab_reseau_bt": {"lib": "Habitants à moins de 50 m du réseau électrique BT (%)", "fmt": ".1f", "unite": " %",
                          "sens": "haut = mieux desservi"},
    "nom_groupe": {"lib": "Typologie des cantons (exploratoire)", "fmt": "", "unite": "", "canton_seul": True},
}
AXES_NUAGE = {k: v["lib"] for k, v in INDICATEURS.items() if k not in ("nom_groupe", "pop_5km")}
AXES_NUAGE["part_loc_5km"] = "Localités à plus de 5 km par la route d'un centre (%)"
AXES_NUAGE["densite_hab_km2"] = "Densité de population (hab./km²)"


def nb(x, dec: int = 0) -> str:
    """Format français : espace pour les milliers, virgule décimale."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n.d."
    s = f"{x:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",")


def gabarit(fig: go.Figure, hauteur: int = 420) -> go.Figure:
    fig.update_layout(
        height=hauteur, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor=CARTE_BLANC, plot_bgcolor=CARTE_BLANC,
        font=dict(family=POLICE, size=13, color=ENCRE), separators=", ",
        hoverlabel=dict(bgcolor=CARTE_BLANC, bordercolor=BORDURE, font=dict(family=POLICE, size=13, color=ENCRE)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=12, color=ENCRE2), bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=T.GRILLE, zeroline=False, linecolor=BORDURE, tickfont=dict(color=ENCRE2))
    fig.update_yaxes(showgrid=False, zeroline=False, linecolor=BORDURE, tickfont=dict(color=ENCRE2))
    return fig


def filtrer_cantons(regions, groupes) -> pd.DataFrame:
    c = CANTONS
    if regions:
        c = c[c.region.isin(regions)]
    if groupes:
        c = c[c.nom_groupe.isin(groupes)]
    return c


# ---------------------------------------------------------------------------- textes
def resume(sel: dict) -> tuple[list, str, str]:
    """Chiffres clés et phrase pour le territoire sélectionné (national, préfecture, canton).
    Mesure principale : habitants à plus de 5 km à vol d'oiseau d'une USP, d'un CMS ou d'un hôpital."""
    nat_part = NAT["pop_5km"] / NAT["population_2022"] * 100
    nat_hc = NAT["population_2022"] / NAT["nb_centres"]
    if sel.get("canton"):
        r = CANTONS.set_index("canton_id").loc[sel["canton"]]
        nom, niveau = r.canton, "canton"
        titre = f"Canton de {nom} ({r.prefecture}, {r.region})"
        dv, dr = r.dist_vol_med_km, r.dist_route_med_km
    elif sel.get("pref"):
        r = PREFS.set_index("prefecture_id").loc[sel["pref"]]
        nom, niveau = r.prefecture, "préfecture"
        titre = f"Préfecture de {nom} ({r.region})"
        dv, dr = r.dist_vol_med_km, r.dist_route_med_km
    else:
        r = None
        nom, niveau, titre = "Togo", "pays", "Ensemble du Togo"
        dv, dr = NAT["dist_vol_med_km"], NAT["dist_route_med_km"]
    if r is None:
        pop, pop5, part, hc = NAT["population_2022"], NAT["pop_5km"], nat_part, nat_hc
        dh, dhr, centres = NAT["dist_hopital_vol_med_km"], NAT["dist_hopital_med_km"], NAT["nb_centres"]
        bas, haut = NAT["pop_5km_geodata"] / pop * 100, NAT["pop_5km_route"] / pop * 100
    else:
        pop, pop5, part, hc = r.population_2022, r.pop_5km, r.part_hab_5km, r.hab_par_centre
        dh, dhr, centres = r.dist_hopital_vol_med_km, r.dist_hopital_med_km, r.nb_centres
        bas = r.part_hab_5km_geodata
        haut = (r.pop_5km_est / pop * 100) if "pop_5km_est" in r.index else r.part_loc_5km

    alerte_part = niveau != "pays" and part > 2 * nat_part
    alerte_hc = centres == 0 or (niveau != "pays" and hc > 2 * nat_hc)
    tuiles = [
        tuile(nb(pop5), "", "habitants à plus de 5 km d'une USP, d'un CMS ou d'un hôpital",
              f"{nb(part, 1)} % de la population ; fourchette {nb(bas, 1)} % (geodata) à {nb(haut, 1)} % (par la route)"
              + ("" if niveau == "pays" else f" ; Togo : {nb(nat_part, 1)} %"), alerte_part),
        tuile(nb(hc) if centres else "Aucun", "" if centres else "centre", "habitants par centre de santé (USP, CMS, hôpital)",
              f"{nb(centres)} centre{'s' if centres > 1 else ''}" + ("" if niveau == "pays" else f" ; Togo : {nb(nat_hc)} hab. par centre"),
              alerte_hc),
        tuile(nb(dv, 1), "km", "distance médiane à vol d'oiseau au centre le plus proche",
              f"par la route : {nb(dr, 1)} km (borne haute)", False),
        tuile(nb(dh, 1), "km", "distance médiane à vol d'oiseau à l'hôpital le plus proche",
              f"par la route : {nb(dhr, 1)} km" + ("" if niveau == "pays" else f" ; Togo : {nb(NAT['dist_hopital_vol_med_km'], 1)} km"),
              False),
    ]

    if niveau == "pays":
        phrase = (f"Au Togo, {nb(pop5)} habitants, soit {nb(part, 1)} % de la population, vivent à plus de 5 km à vol "
                  f"d'oiseau d'une USP, d'un CMS ou d'un hôpital. Un centre de santé dessert en moyenne {nb(hc)} habitants, "
                  f"et l'hôpital le plus proche est en médiane à {nb(dh, 1)} km à vol d'oiseau.")
    else:
        lieu = f"Dans le canton de {nom}" if niveau == "canton" else f"Dans la préfecture de {nom}"
        comp = "plus" if part > nat_part else "moins"
        p1 = (f"{lieu}, {nb(part, 1)} % des habitants ({nb(pop5)} personnes) vivent à plus de 5 km d'une USP, d'un CMS ou "
              f"d'un hôpital, {comp} qu'au niveau national ({nb(nat_part, 1)} %).")
        if centres == 0:
            p2 = " Il n'y a aucune USP, aucun CMS ni aucun hôpital sur ce territoire."
        else:
            rapport_hc = hc / nat_hc
            p2 = (f" Un centre y dessert {nb(hc)} habitants, soit {nb(rapport_hc, 1)} fois la moyenne nationale."
                  if rapport_hc >= 1.15 else
                  f" Un centre y dessert {nb(hc)} habitants, contre {nb(nat_hc)} en moyenne nationale.")
        p3 = ""
        if niveau == "canton":
            rang = int(r.rang_priorite)
            p3 = f" Ce canton se classe {rang}{'er' if rang == 1 else 'e'} sur 396 pour l'indice de priorité."
        phrase = p1 + p2 + p3
    return tuiles, phrase, titre


def tuile(valeur, unite, libelle, repere, alerte):
    return html.Div(className="chiffre alerte" if alerte else "chiffre", children=[
        html.Div([valeur, html.Span(unite, className="chiffre-unite") if unite else None], className="chiffre-valeur"),
        html.Div(libelle, className="chiffre-libelle"),
        html.Div([html.Span("Alerte", className="pastille-alerte") if alerte else None, repere], className="chiffre-repere"),
    ])


# ---------------------------------------------------------------------------- figures
def _bbox_geojson(geo: dict, cle: str) -> dict:
    """Emprise (lon min, lat min, lon max, lat max) de chaque territoire, calculée une fois au démarrage."""
    out = {}
    for f in geo["features"]:
        pts = []

        def parcourir(c):
            if isinstance(c[0], (int, float)):
                pts.append(c)
            else:
                for x in c:
                    parcourir(x)
        parcourir(f["geometry"]["coordinates"])
        a = np.array(pts)
        out[f["properties"][cle]] = (a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max())
    return out


BBOX = {**_bbox_geojson(GEO_CANTONS, "canton_id"), **_bbox_geojson(GEO_PREFS, "prefecture_id")}
RAPPORT_CADRE = 0.55   # largeur / hauteur visée du cadre (en degrés) : la carte remplit la hauteur disponible


def cadrer(fig: go.Figure, ids) -> None:
    """Fixe l'emprise de la carte sur les territoires affichés, pour qu'elle occupe toute la hauteur."""
    b = np.array([BBOX[i] for i in ids if i in BBOX])
    if not len(b):
        return
    lon0, lat0, lon1, lat1 = b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()
    dlat, dlon = (lat1 - lat0) * 1.04, (lon1 - lon0) * 1.04
    if dlon / dlat < RAPPORT_CADRE:      # territoire haut et étroit (le Togo) : on élargit le cadre
        dlon = dlat * RAPPORT_CADRE
    else:                                # territoire large : on agrandit la hauteur
        dlat = dlon / RAPPORT_CADRE
    clon, clat = (lon0 + lon1) / 2, (lat0 + lat1) / 2
    fig.update_geos(fitbounds=False, projection_type="mercator", visible=False, bgcolor=CARTE_BLANC,
                    lonaxis_range=[clon - dlon / 2, clon + dlon / 2], lataxis_range=[clat - dlat / 2, clat + dlat / 2])


def niveau_cle(vue_cantons: bool) -> str:
    return "canton" if vue_cantons else "pref"


def echelle_classes() -> list:
    """Échelle discrète : la valeur k + 0,5 (k = 0 à 4) tombe dans la bande de la classe k."""
    cs = []
    for i, c in enumerate(T.GRAVITE):
        cs += [[i / 5, c], [(i + 1) / 5, c]]
    return cs


def classes_de(df: pd.DataFrame, indicateur: str, niveau: str) -> pd.Series:
    return df[indicateur].map(lambda v: T.classer(v, indicateur, niveau))


def element_legende(couleur, texte, forme="carre", bord=None):
    style = {"background": couleur}
    if bord:
        style["border"] = f"2px solid {bord}"
    return html.Div(className="legende-ligne", children=[
        html.Span(className=f"legende-symbole legende-{forme}", style=style), html.Span(texte)])


FORMES_CSS = {"circle": "rond", "square": "carre", "triangle-up": "triangle", "diamond": "losange"}


def legende_groupes():
    """Légende HTML du nuage : même couleur ET même forme que les points (passe à la ligne sur mobile)."""
    lignes = []
    for g in ORDRE_GROUPES:
        forme = FORMES_CSS[SYMBOLE_GROUPE[g]]
        style = ({"borderBottomColor": COULEUR_GROUPE[g]} if forme == "triangle" else {"background": COULEUR_GROUPE[g]})
        lignes.append(html.Div(className="legende-ligne", children=[
            html.Span(className=f"legende-symbole legende-{forme}", style=style), html.Span(g)]))
    return html.Div(lignes, className="legende-nuage", **{"aria-label": "Légende des groupes"})


def legende_carte(indicateur, niveau, sans_centre, non_renseigne, centres):
    if indicateur == "nom_groupe":
        titre = "Groupe de cantons (lecture exploratoire)"
        lignes = [element_legende(COULEUR_GROUPE[g], g) for g in ORDRE_GROUPES]
    else:
        conf = T.CLASSES[indicateur]
        titre = conf["titre"]
        lib = T.libelles_classes(indicateur, niveau)
        lignes = [element_legende(T.GRAVITE[k], lib[k]) for k in range(4, -1, -1)]
        if non_renseigne:
            lignes.append(element_legende(T.NON_RENSEIGNE, "non renseigné"))
    if sans_centre:
        lignes.append(element_legende("transparent", "Canton sans centre de santé", bord=ENCRE))
    if centres:
        lignes += [element_legende(CARTE_BLANC, "USP ou CMS", forme="rond", bord=ENCRE),
                   element_legende(ENCRE, "Hôpital", forme="losange")]
    return [html.P(titre, className="legende-titre"), *lignes]


def figure_carte(sel, indicateur, niveau, regions, groupes, afficher_centres):
    canton_seul = INDICATEURS[indicateur].get("canton_seul", False)
    vue_cantons = niveau == "cantons" or canton_seul or bool(sel.get("pref")) or bool(sel.get("canton"))
    niv = niveau_cle(vue_cantons)
    fig = go.Figure()
    if vue_cantons:
        tous = CANTONS
        if sel.get("pref") or sel.get("canton"):
            pid = sel.get("pref") or CANTONS.set_index("canton_id").loc[sel["canton"], "prefecture_id"]
            tous = CANTONS[CANTONS.prefecture_id == pid]
        actifs = filtrer_cantons(regions, groupes)
        df = tous[tous.canton_id.isin(actifs.canton_id)]
        inactifs = tous[~tous.canton_id.isin(actifs.canton_id)]
        geo, cle, ids, noms = GEO_CANTONS, "properties.canton_id", "canton_id", "canton"
        info = df.prefecture
    else:
        df = PREFS if not regions else PREFS[PREFS.region.isin(regions)]
        inactifs = PREFS[~PREFS.prefecture_id.isin(df.prefecture_id)]
        geo, cle, ids, noms = GEO_PREFS, "properties.prefecture_id", "prefecture_id", "prefecture"
        info = df.region
    trait = dict(marker_line_color=CARTE_BLANC, marker_line_width=0.5)   # fines frontières blanches

    if len(inactifs):
        fig.add_trace(go.Choropleth(geojson=geo, featureidkey=cle, locations=inactifs[ids], z=[0] * len(inactifs),
                                    colorscale=[[0, T.INACTIF], [1, T.INACTIF]], showscale=False, hoverinfo="skip", **trait))
    non_renseigne = False
    sans = df.iloc[0:0]
    if indicateur == "nom_groupe":
        for g in ORDRE_GROUPES:
            s = df[df.nom_groupe == g]
            fig.add_trace(go.Choropleth(
                geojson=geo, featureidkey=cle, locations=s[ids], z=[1] * len(s), name=g,
                colorscale=[[0, COULEUR_GROUPE[g]], [1, COULEUR_GROUPE[g]]], showscale=False, **trait,
                customdata=np.stack([s[noms], s.prefecture, s.population_2022, s.nom_groupe], axis=-1),
                hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Groupe : %{customdata[3]}"
                              "<br>Habitants : %{customdata[2]:,.0f}<extra></extra>"))
    else:
        meta = INDICATEURS[indicateur]
        k = classes_de(df, indicateur, niv)
        ok, na = df[k >= 0], df[k < 0]
        non_renseigne = len(na) > 0
        lib = T.libelles_classes(indicateur, niv)
        valeurs = [("aucun" if pd.isna(v) else nb(v, 0 if "," in meta["fmt"] else 1) + meta["unite"]) for v in ok[indicateur]]
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey=cle, locations=ok[ids], z=k[k >= 0] + 0.5, zmin=0, zmax=5,
            colorscale=echelle_classes(), showscale=False, **trait,
            customdata=np.stack([ok[noms], info[k >= 0], ok.population_2022, valeurs, [lib[c] for c in k[k >= 0]]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>" + meta["lib"] + " : %{customdata[3]}"
                          "<br>Classe : %{customdata[4]}<br>Habitants : %{customdata[2]:,.0f}<extra></extra>"))
        if non_renseigne:
            fig.add_trace(go.Choropleth(geojson=geo, featureidkey=cle, locations=na[ids], z=[0] * len(na),
                                        colorscale=[[0, T.NON_RENSEIGNE], [1, T.NON_RENSEIGNE]], showscale=False, **trait,
                                        customdata=np.stack([na[noms]], axis=-1),
                                        hovertemplate="<b>%{customdata[0]}</b><br>non renseigné<extra></extra>"))
        if vue_cantons:
            sans = df[df.nb_centres == 0]
        if len(sans):  # cantons sans aucun centre : contour foncé, expliqué dans la légende
            fig.add_trace(go.Choropleth(geojson=geo, featureidkey=cle, locations=sans[ids], z=[0] * len(sans),
                                        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
                                        marker_line_color=ENCRE, marker_line_width=1.8, hoverinfo="skip"))
    choisi = sel.get("canton") if vue_cantons else sel.get("pref")
    if choisi:
        fig.add_trace(go.Choropleth(geojson=geo, featureidkey=cle, locations=[choisi], z=[0],
                                    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
                                    marker_line_color=T.VERT, marker_line_width=3, hoverinfo="skip"))
    # centres : affichés au niveau des cantons, masqués au niveau des préfectures (sauf si la case est cochée)
    montrer_centres = vue_cantons or afficher_centres
    if montrer_centres:
        cs = CENTRES[CENTRES.niveau.isin(["usp", "hopital"])]
        if vue_cantons:
            cs = cs[cs.canton_id.isin(df.canton_id)]
        for nv, nom_leg, taille, symbole, fond, opacite in [("usp", "USP ou CMS", 4, "circle", CARTE_BLANC, 0.6),
                                                             ("hopital", "Hôpital", 7, "diamond", ENCRE, 0.75)]:
            s = cs[cs.niveau == nv]
            fig.add_trace(go.Scattergeo(lon=s.lon, lat=s.lat, mode="markers", name=nom_leg,
                                        marker=dict(size=taille, color=fond, symbol=symbole, opacity=opacite,
                                                    line=dict(color=ENCRE, width=0.8)),
                                        customdata=np.stack([s.nom, s.type, s.secteur], axis=-1),
                                        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Secteur : %{customdata[2]}<extra></extra>"))
    cadrer(fig, list(df[ids]) + list(inactifs[ids]))
    gabarit(fig, HAUTEUR_CARTE)
    fig.update_layout(clickmode="event", margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
    legende = legende_carte(indicateur, niv, len(sans) > 0, non_renseigne, montrer_centres)
    return fig, vue_cantons, legende


def figure_classement(sel, indicateur, vue_cantons, regions, groupes):
    if indicateur == "nom_groupe":
        indicateur = "indice_priorite"
    meta = INDICATEURS[indicateur]
    niv = niveau_cle(vue_cantons)
    if vue_cantons:
        df = filtrer_cantons(regions, groupes)
        if sel.get("pref") or sel.get("canton"):
            pid = sel.get("pref") or CANTONS.set_index("canton_id").loc[sel["canton"], "prefecture_id"]
            df = df[df.prefecture_id == pid]
        ids, noms = "canton_id", "canton"
    else:
        df = PREFS if not regions else PREFS[PREFS.region.isin(regions)]
        ids, noms = "prefecture_id", "prefecture"
    inverse = T.CLASSES[indicateur].get("inverse", False)  # réseau électrique : les plus faibles sont prioritaires
    # sans centre (ou sans agent) : cas le plus grave, placé en tête avec la mention « aucun »
    manquants = df[df[indicateur].isna()] if indicateur in ("hab_par_centre", "hab_par_personnel") else df.iloc[0:0]
    df = df.dropna(subset=[indicateur]).sort_values(indicateur, ascending=inverse)
    plafond = float(df[indicateur].max()) if len(df) else 1.0
    classe_manquant = 4 if indicateur == "hab_par_centre" else -1
    manquants = manquants.assign(**{indicateur: plafond}).sort_values("population_2022", ascending=False)
    k = pd.concat([pd.Series(classe_manquant, index=manquants.index), classes_de(df, indicateur, niv)])
    df = pd.concat([manquants, df]).head(15)[::-1]
    k = k.loc[df.index] if len(df) else k
    vide = set(manquants[ids])
    choisi = sel.get("canton") if vue_cantons else sel.get("pref")
    couleurs = [T.NON_RENSEIGNE if c < 0 else T.GRAVITE[c] for c in k]
    bords = [T.VERT if i == choisi else "rgba(0,0,0,0)" for i in df[ids]]
    texte_aucun = "aucun centre" if indicateur == "hab_par_centre" else "aucun agent"
    textes = [texte_aucun if i in vide else nb(v, 0 if "," in meta["fmt"] else 1) for i, v in zip(df[ids], df[indicateur])]
    fig = go.Figure(go.Bar(
        x=df[indicateur], y=df[noms], orientation="h",
        marker=dict(color=couleurs, cornerradius=4, line=dict(color=bords, width=3)),
        customdata=np.stack([df[ids], df.population_2022, textes], axis=-1),
        hovertemplate="<b>%{y}</b><br>" + meta["lib"] + " : %{customdata[2]}" + meta["unite"] +
                      "<br>Habitants : %{customdata[1]:,.0f}<extra></extra>",
        text=textes, textposition="outside", cliponaxis=False, textfont=dict(color=ENCRE2, size=12)))
    gabarit(fig, HAUTEUR_CARTE)
    titre_vide = None
    if len(vide) and len(df):
        titre_vide = f"{len(vide)} canton{'s' if len(vide) > 1 else ''} n'{'ont' if len(vide) > 1 else 'a'} {texte_aucun} ; placé{'s' if len(vide) > 1 else ''} en tête"
    fig.update_layout(bargap=0.3, margin=dict(l=8, r=56, t=8, b=8))
    fig.update_xaxes(showgrid=False, showticklabels=False)
    if len(df):
        tete = df.iloc[-1]
        val = nb(tete[indicateur], 0 if "," in meta["fmt"] else 1) + meta["unite"]
        quoi = "le canton le moins proche" if vue_cantons else "la préfecture la moins proche"
        titre = (f"{tete[noms]} est {quoi} du réseau électrique ({val})" if inverse else
                 f"{tete[noms]} arrive en tête : {val}")
    else:
        titre = "Aucun territoire ne correspond aux filtres"
        fig = go.Figure()
        gabarit(fig, HAUTEUR_CARTE)
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        fig.add_annotation(text="Aucun territoire ne correspond aux filtres choisis", showarrow=False,
                           font=dict(size=14, color=ENCRE2), x=0.5, y=0.5, xref="paper", yref="paper")
    if titre_vide:
        titre = titre_vide
    return fig, titre


AXES_COURTS = {
    "indice_priorite": "l'indice de priorité", "part_hab_5km": "la part d'habitants éloignés",
    "part_hab_5km_geodata": "la part d'habitants éloignés (geodata)", "dist_route_med_km": "la distance par la route",
    "dist_hopital_vol_med_km": "la distance à l'hôpital", "hab_par_centre": "le nombre d'habitants par centre",
    "hab_par_personnel": "le nombre d'habitants par agent", "pct_hab_reseau_bt": "la proximité du réseau électrique",
    "part_loc_5km": "l'éloignement par la route", "densite_hab_km2": "la densité",
}


def figure_nuage(x, y, sel, regions, groupes):
    df = filtrer_cantons(regions, groupes).dropna(subset=[x, y])
    fig = go.Figure()
    for g in ORDRE_GROUPES:
        s = df[df.nom_groupe == g]
        fig.add_trace(go.Scatter(
            x=s[x], y=s[y], mode="markers", name=g,
            marker=dict(size=11, color=COULEUR_GROUPE[g], symbol=SYMBOLE_GROUPE[g], opacity=0.85,
                        line=dict(color=CARTE_BLANC, width=1)),
            customdata=np.stack([s.canton_id, s.canton, s.prefecture, s.population_2022], axis=-1),
            hovertemplate="<b>%{customdata[1]}</b> (%{customdata[2]})<br>" + AXES_NUAGE[x] + " : %{x:,.1f}<br>" +
                          AXES_NUAGE[y] + " : %{y:,.1f}<br>Habitants : %{customdata[3]:,.0f}<extra>" + g + "</extra>"))
    if sel.get("canton") and sel["canton"] in set(df.canton_id):
        r = df.set_index("canton_id").loc[sel["canton"]]
        fig.add_trace(go.Scatter(x=[r[x]], y=[r[y]], mode="markers+text", text=[r.canton], textposition="top center",
                                 marker=dict(size=16, color="rgba(0,0,0,0)", line=dict(color=T.VERT, width=3)),
                                 showlegend=False, hoverinfo="skip", textfont=dict(color=ENCRE, size=12)))
    gabarit(fig, HAUTEUR_NUAGE)
    fig.update_layout(margin=dict(l=8, r=8, t=8, b=8), showlegend=False)
    fig.update_xaxes(title=dict(text=AXES_NUAGE[x], font=dict(color=ENCRE2, size=12)), tickformat=",~r")
    fig.update_yaxes(title=dict(text=AXES_NUAGE[y], font=dict(color=ENCRE2, size=12)), showgrid=True, gridcolor=T.GRILLE,
                     tickformat=",~r")
    for axe, nom in (("x", x), ("y", y)):
        if nom in ("densite_hab_km2", "hab_par_centre", "hab_par_personnel"):
            fig.update_xaxes(type="log") if axe == "x" else fig.update_yaxes(type="log")
    if x == y:
        return fig, "Choisissez deux indicateurs différents", ""
    if len(df) >= 10:
        r = spearmanr(df[x], df[y])
        rho, p = r.statistic, r.pvalue
        force = "forte" if abs(rho) >= 0.6 else "modérée" if abs(rho) >= 0.3 else "faible"
        if p < 0.05:
            titre = (f"Plus {AXES_COURTS.get(x, 'x')} est élevé{'e' if AXES_COURTS.get(x, '').startswith('la ') else ''}, "
                     f"plus {AXES_COURTS.get(y, 'y')} {'augmente' if rho > 0 else 'diminue'}")
        else:
            titre = "Pas d'association nette entre ces deux indicateurs"
        sous_titre = f"rho de Spearman = {nb(rho, 2)} (association {force}) ; n = {nb(len(df))} cantons"
    else:
        titre, sous_titre = "Trop peu de cantons sélectionnés pour mesurer une association", f"n = {len(df)}"
    return fig, titre, sous_titre


def figure_profils():
    fig = go.Figure()
    g = GROUPES.set_index("nom_groupe").loc[ORDRE_GROUPES[::-1]]
    dims = list(T.DIMENSIONS.items())
    # tracés ajoutés en ordre inverse : dans un groupe de barres horizontales, le premier tracé est en bas
    for col, (lib, couleur) in reversed(dims):
        motif = dict(shape="/", fgcolor=CARTE_BLANC, size=6, solidity=0.25) if col == "dim_capacite" else None
        fig.add_trace(go.Bar(y=g.index, x=g[col], orientation="h", name=lib,
                             marker=dict(color=couleur, cornerradius=4, pattern=motif),
                             texttemplate="%{x:.0f}", textposition="outside", cliponaxis=False,
                             textfont=dict(color=ENCRE2, size=11),
                             hovertemplate="%{y}<br>" + lib + " : %{x:.1f} / 100<extra></extra>"))
    gabarit(fig, HAUTEUR_PROFILS)
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, margin=dict(l=8, r=40, t=48, b=8),
                      legend=dict(traceorder="reversed", orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom",
                                  font=dict(size=12, color=ENCRE)))
    fig.update_xaxes(range=[0, 105], title=dict(text="Score moyen du groupe (0 = meilleure situation, 100 = plus défavorable)",
                                                font=dict(size=12, color=ENCRE2)))
    return fig


# ---------------------------------------------------------------------------- mise en page
def panneau(titre_id, aide, contenu, source=SOURCE_STD, titre=None):
    return html.Div(className="panneau", children=[
        html.H3(titre, id=titre_id), html.P(aide, className="aide") if aide else None, *contenu,
        html.P(source, className="source")])


COLONNES_TABLE = [
    ("rang_priorite", "Rang", "nombre", ""), ("canton", "Canton", "texte", ""), ("prefecture", "Préfecture", "texte", ""),
    ("region", "Région", "texte", ""), ("population_2022", "Habitants 2022", "nombre", ",.0f"),
    ("indice_priorite", "Indice", "nombre", ".1f"), ("nom_groupe", "Groupe", "texte", ""),
    ("part_hab_5km", "Hab. > 5 km (%)", "nombre", ".1f"), ("pop_5km", "Hab. > 5 km", "nombre", ",.0f"),
    ("dist_vol_med_km", "Distance au centre (km)", "nombre", ".1f"), ("dist_hopital_vol_med_km", "Distance à l'hôpital (km)", "nombre", ".1f"),
    ("nb_centres", "Centres", "nombre", ""), ("hab_par_centre", "Hab. par centre", "nombre", ",.0f"),
    ("hab_par_personnel", "Hab. par agent", "nombre", ",.0f"), ("pct_hab_reseau_bt", "Hab. près réseau BT (%)", "nombre", ".1f"),
    ("top20_nb_variantes", "Top 20 (sur 5 variantes)", "nombre", ""),
]


def table_html(df: pd.DataFrame, nombres=()) -> html.Table:
    return html.Table(className="simple", children=[
        html.Thead(html.Tr([html.Th(c) for c in df.columns])),
        html.Tbody([html.Tr([html.Td(v, className="nombre" if c in nombres else None) for c, v in zip(df.columns, r)])
                    for r in df.itertuples(index=False)])])


def onglet_methode():
    comp = COMP.copy()
    comp["population"] = comp.population.map(nb)
    comp["part_pct"] = comp.part_pct.map(lambda v: nb(v, 1))
    comp["rho_avec_geodata_par_canton"] = comp.rho_avec_geodata_par_canton.map(lambda v: nb(v, 2))
    comp.columns = ["Mesure", "Habitants", "%", "rho avec geodata"]
    sens = SENS.copy()
    sens["rho_spearman_avec_reference"] = sens.rho_spearman_avec_reference.map(lambda v: nb(v, 3))
    sens.columns = ["Variante de l'indice", "Corrélation de rang avec la référence", "Cantons communs dans le top 20"]
    src = SOURCES.copy()
    src["fichier"] = src.fichier.str.split("/").str[-1]
    src.columns = ["Fichier", "Jeu de données", "Plateforme", "Téléchargé le", "Licence"]
    m = META
    return html.Div(className="texte-methode", children=[
        html.H4("Question"),
        html.P("Quelles populations sont les plus éloignées d'un centre de santé, et où faudrait-il agir en priorité ? "
               "Unité d'analyse : les 396 cantons, agrégés en 39 préfectures."),
        html.H4("Centres de santé retenus"),
        html.P(f"Unités de soins périphériques (USP), centres médico-sociaux (CMS) et hôpitaux : {nb(NAT['nb_centres'])} "
               "établissements géolocalisés (geodata, PRISE 2021-2022). Les cases de santé et infirmeries sont exclues "
               "car leur offre est plus limitée."),
        html.H4("Distance par la route"),
        html.P(f"Le réseau routier publié (48 008 km) n'est pas topologique : il a été découpé à ses intersections "
               f"({nb(m['segments_apres_decoupage'])} segments) et les impasses ont été raccordées aux nœuds situés à moins de "
               f"{m['tolerance_raccord_m']} m ({nb(m['raccords_ajoutes'])} raccords). La composante principale couvre "
               f"{nb(m['part_longueur_composante_principale'] * 100, 1)} % de la longueur. Pour chacune des {nb(m['origines'])} "
               "localités : trajet en ligne droite jusqu'au réseau, plus court chemin, trajet jusqu'au centre."),
        html.H4("Chiffre principal et bornes pour l'éloignement"),
        html.P("Chiffre principal : distance à vol d'oiseau des localités au centre le plus proche (norme du « rayon d'action "
               "théorique de 5 km » publiée sur geodata), population du canton répartie également entre ses localités. "
               "Il est recalculable de bout en bout et sert de base au simulateur."),
        table_html(comp, nombres=("Habitants", "%", "rho avec geodata")),
        html.P("La borne basse (geodata) pondère par la population mais mesure à vol d'oiseau. La borne haute mesure par "
               "la route mais suppose des localités de même taille. Notre calcul à vol d'oiseau est très proche de celui "
               "de geodata (rho = 0,90 entre cantons), ce qui valide la chaîne de calcul."),
        html.H4("Indice de priorité (0-100)"),
        html.P("Moyenne de trois dimensions exprimées en rangs centiles : éloignement (les deux bornes), capacité "
               "(habitants par centre, habitants par agent de santé), électricité (habitants loin du réseau basse "
               "tension). Pondération égale. Test de sensibilité :"),
        table_html(sens, nombres=("Corrélation de rang avec la référence", "Cantons communs dans le top 20")),
        html.H4("Typologie"),
        html.P("k-means sur les trois dimensions et la densité (logarithme), graine fixée. Le nombre de groupes (4) est le "
               "plus petit dont le score de silhouette est à moins de 0,01 du meilleur ; la silhouette reste modeste "
               "(0,28) : les groupes sont des repères, pas des frontières nettes."),
        html.H4("Limites"),
        html.Ul([html.Li(t) for t in [
            "Années différentes : équipements 2021-2022, population 2022, électricité 2021.",
            "La population n'est connue qu'au canton : pas de grille fine publiée.",
            f"Pour {nb(m['part_origines_acces_reseau_sup_2km'] * 100, 1)} % des localités, le trajet jusqu'au réseau routier dépasse 2 km ; les sentiers ne sont pas cartographiés.",
            "Aucun temps de trajet ni état saisonnier des routes n'est publié.",
            "La présence d'un centre ne dit rien de son fonctionnement (personnel présent, médicaments, horaires).",
            "L'électrification des centres eux-mêmes est absente des fichiers publiés.",
            "Associations statistiques seulement : aucune relation de cause à effet n'est établie.",
        ]]),
        html.H4("Sources (100 % opendata.gouv.tg et geodata.gouv.tg)"),
        table_html(src),
    ])


# ---------------------------------------------------------------------------- solutions
LIMITE_SIM = ("Un centre construit sans personnel ni médicaments ne sert à rien. La population est supposée répartie de "
              "façon égale entre les chefferies d'un même canton, et la distance est mesurée à vol d'oiseau. Les sites sont "
              "choisis un par un (algorithme glouton : solution approchée) ; le coût et l'accès par la route ne sont pas pris "
              "en compte.")


def bloc_solution(impact, territoires, limite):
    return html.Div(className="solution-cadre", children=[
        html.Div([html.Span("Impact", className="solution-etiquette"), html.Div(impact)]),
        html.Div([html.Span("Territoires visés", className="solution-etiquette"), html.Div(territoires)]),
        html.Div([html.Span("Limite", className="solution-etiquette solution-limite"), html.Div(limite)]),
    ])


def figure_simulateur(n: int) -> go.Figure:
    etat = SIM_PREFS[SIM_PREFS.n_centres_ajoutes == n]
    fig = go.Figure(go.Choropleth(
        geojson=GEO_PREFS, featureidkey="properties.prefecture_id", locations=etat.prefecture_id,
        z=etat.part_plus_5km_pct.map(lambda v: T.classer(v, "part_hab_5km", "pref")) + 0.5, zmin=0, zmax=5,
        colorscale=echelle_classes(), showscale=False, marker_line_color=CARTE_BLANC, marker_line_width=0.5,
        text=etat.part_plus_5km_pct.map(lambda v: nb(v, 1)),
        customdata=np.stack([etat.prefecture, etat.habitants_plus_5km], axis=-1),
        hovertemplate="<b>%{customdata[0]}</b><br>Habitants à plus de 5 km après les nouveaux centres : %{text} %"
                      "<br>soit %{customdata[1]:,.0f} habitants<extra></extra>"))
    gagnees = SIM_LOC[(SIM_LOC.rang_couverture > 0) & (SIM_LOC.rang_couverture <= n)]
    fig.add_trace(go.Scattergeo(lon=gagnees.lon, lat=gagnees.lat, mode="markers", name="Localité passée sous les 5 km",
                                marker=dict(size=5, color=T.VERT, opacity=0.8, line=dict(color=CARTE_BLANC, width=0.5)),
                                customdata=np.stack([gagnees.nom_localite, gagnees.canton, gagnees["pop"]], axis=-1),
                                hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Environ %{customdata[2]:,.0f} habitants"
                                              "<extra>gagnée</extra>"))
    sites = SIM_SITES[SIM_SITES.rang <= n]
    fig.add_trace(go.Scattergeo(lon=sites.lon, lat=sites.lat, mode="markers+text", name="Nouveau centre proposé",
                                text=sites.rang.astype(str), textposition="top center", textfont=dict(size=10, color=ENCRE),
                                marker=dict(size=11, symbol="diamond", color=ENCRE, line=dict(color=CARTE_BLANC, width=1.5)),
                                customdata=np.stack([sites.nom_localite, sites.canton, sites.prefecture, sites.habitants_gagnes], axis=-1),
                                hovertemplate="<b>Site n° %{text} : %{customdata[0]}</b><br>%{customdata[1]} (%{customdata[2]})"
                                              "<br>Habitants gagnés : %{customdata[3]:,.0f}<extra></extra>"))
    cadrer(fig, list(etat.prefecture_id))
    gabarit(fig, HAUTEUR_CARTE)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
    return fig


def legende_simulateur():
    lib = T.libelles_classes("part_hab_5km", "pref")
    return [html.P("Habitants à plus de 5 km après les nouveaux centres (%)", className="legende-titre"),
            *[element_legende(T.GRAVITE[k], lib[k]) for k in range(4, -1, -1)],
            element_legende(T.VERT, "Localité passée sous les 5 km", forme="rond"),
            element_legende(ENCRE, "Nouveau centre proposé (numéro = ordre)", forme="losange")]


def figure_courbe(n: int) -> go.Figure:
    s = SIM_SITES
    fig = go.Figure(go.Scatter(x=s.rang, y=s.habitants_gagnes_cumules, mode="lines", line=dict(color=T.VERT, width=2),
                               hovertemplate="%{x} centres : %{y:,.0f} habitants gagnés<extra></extra>", name="Habitants gagnés"))
    r = s[s.rang == n].iloc[0]
    fig.add_trace(go.Scatter(x=[n], y=[r.habitants_gagnes_cumules], mode="markers", showlegend=False, hoverinfo="skip",
                             marker=dict(size=11, color=T.JAUNE, line=dict(color=ENCRE, width=1.5))))
    gabarit(fig, HAUTEUR_COURBE)
    fig.update_layout(showlegend=False, margin=dict(l=8, r=8, t=8, b=8))
    fig.update_xaxes(title=dict(text="Nombre de nouveaux centres", font=dict(size=12, color=ENCRE2)), showgrid=False)
    fig.update_yaxes(title=dict(text="Habitants passés sous les 5 km", font=dict(size=12, color=ENCRE2)),
                     showgrid=True, gridcolor=T.GRILLE, rangemode="tozero", tickformat=",d")
    return fig


def onglet_solutions():
    sc = SANS_CENTRE
    usp = sc[sc.proposition == "Nouvelle USP"]
    t_sans = pd.DataFrame({
        "Canton": sc.canton + sc.population_estimee.map({True: " *", False: ""}), "Préfecture": sc.prefecture,
        "Habitants": sc.population_2022.map(nb), "Autres formations": sc.formations_autres.map(nb),
        "Hab. > 5 km (%)": sc.part_hab_5km.map(lambda v: nb(v, 1)), "Proposition": sc.proposition,
        "Couvert par le simulateur dès le site n°": sc.simulateur_premier_rang.map(lambda v: "—" if pd.isna(v) else nb(v)),
    })
    so = SOLAIRE_RES
    return [
        panneau("titre-sim", None, [
            html.P("Choisissez le nombre de nouveaux centres : les sites sont choisis parmi les chefferies géolocalisées, un par "
                   "un, là où ils font passer le plus d'habitants sous les 5 km.", className="aide"),
            html.Div(className="controles-panneau", children=[
                html.Label("Nombre de nouveaux centres de santé", htmlFor="n-centres", className="etiquette"),
                html.Div(style={"flex": "1 1 320px", "minWidth": "260px"}, children=[
                    dcc.Slider(id="n-centres", min=1, max=50, step=1, value=10,
                               marks={i: str(i) for i in (1, 10, 20, 30, 40, 50)},
                               tooltip={"placement": "bottom", "always_visible": False})]),
            ]),
            html.Div(id="sim-chiffres", className="chiffres"),
            html.Div(className="grille-2", style={"marginTop": "16px"}, children=[
                html.Div(className="carte-et-legende", children=[
                    dcc.Graph(id="sim-carte", style={"height": f"{HAUTEUR_CARTE}px"}, className="carte-graphe",
                              config={"displaylogo": False, "scrollZoom": False, "toImageButtonOptions": {"format": "png", "scale": 2}}),
                    html.Div(legende_simulateur(), className="legende-carte")]),
                html.Div([
                    html.H4("Chaque centre ajouté rapporte de moins en moins", className="sous-titre-panneau"),
                    dcc.Graph(id="sim-courbe", style={"height": f"{HAUTEUR_COURBE}px"},
                              config={"displaylogo": False, "displayModeBar": False}),
                    html.H4("Préfectures qui gagnent le plus", className="sous-titre-panneau"),
                    html.Div(id="sim-prefs"),
                    html.Div(className="controles-panneau", children=[
                        html.Button("Exporter les sites en CSV", id="export-sites", className="bouton bouton-plein", n_clicks=0)]),
                ]),
            ]),
            html.Div(id="sim-cadre"),
        ], titre="Des centres bien placés réduisent fortement l'éloignement", source=SOURCE_STD),
        html.Div(style={"height": "24px"}),
        panneau("titre-sans", None, [
            bloc_solution(
                f"{nb(len(sc))} cantons, {nb(sc.population_2022.sum())} habitants : {nb(len(usp))} nouvelles USP "
                f"({nb(usp.population_2022.sum())} habitants) et des cliniques mobiles pour les {nb(len(sc) - len(usp))} autres.",
                ", ".join(usp.canton + " (" + usp.prefecture + ")") + " pour une USP ; voir le tableau pour les autres.",
                "Règle simple : une USP si la population atteint la moyenne nationale d'habitants par centre et que plus de la "
                "moitié vit à plus de 5 km ; sinon cliniques mobiles. Sans personnel affecté, une USP ne sert à rien. "
                "* population estimée."),
            table_html(t_sans, nombres=("Habitants", "Autres formations", "Hab. > 5 km (%)", "Couvert par le simulateur dès le site n°")),
        ], titre=f"{nb(len(sc))} cantons n'ont ni USP, ni CMS, ni hôpital ({nb(int((sc.formations_autres == 0).sum()))} n'ont aucune formation sanitaire)",
            source=SOURCE_STD),
        html.Div(style={"height": "24px"}),
        panneau("titre-solaire", None, [
            bloc_solution(
                f"{nb(so.formations_sanitaires)} formations sanitaires ({nb(so.dont_usp_cms)} USP ou CMS, {nb(so.dont_publiques)} "
                f"publiques) servant {nb(so.population_cantons_cibles)} habitants.",
                f"{nb(so.cantons_cibles)} cantons où aucun habitant ne vit à moins de 50 m du réseau basse tension, dans "
                f"{nb(so.prefectures_concernees)} préfectures.",
                "L'électrification de chaque centre n'est pas publiée : certains ont peut-être déjà un panneau solaire ou un "
                "groupe électrogène. L'indicateur mesure la proximité du réseau pour les habitants, pas pour le centre."),
            html.Div(className="controles-panneau", children=[
                html.Button("Exporter la liste en CSV", id="export-solaire", className="bouton bouton-plein", n_clicks=0)]),
            dash_table.DataTable(
                data=SOLAIRE[["nom", "type", "secteur", "canton", "prefecture", "population_canton"]].to_dict("records"),
                columns=[{"name": n, "id": c, **({"type": "numeric", "format": {"specifier": ",.0f"}} if c == "population_canton" else {})}
                         for c, n in [("nom", "Formation sanitaire"), ("type", "Type"), ("secteur", "Secteur"), ("canton", "Canton"),
                                      ("prefecture", "Préfecture"), ("population_canton", "Habitants du canton")]],
                page_size=10, sort_action="native", filter_action="native", style_table={"overflowX": "auto"},
                style_cell={"fontFamily": POLICE, "fontSize": 13, "padding": "6px 8px", "color": ENCRE,
                            "border": f"1px solid {BORDURE}", "whiteSpace": "normal", "height": "auto", "textAlign": "left"},
                style_header={"backgroundColor": SURFACE, "fontWeight": 600, "color": ENCRE2},
                filter_options={"placeholder_text": "Filtrer…"}),
        ], titre=f"{nb(so.formations_sanitaires)} formations sanitaires à équiper en priorité en solaire", source=SOURCE_STD),
        dcc.Download(id="telechargement-solutions"),
    ]


app = Dash(__name__, title="Accès aux soins au Togo", update_title=None, compress=True,
           external_stylesheets=["https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap"],
           meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"},
                      {"name": "description", "content": "Où vivent les Togolais les plus éloignés d'un centre de santé, et où agir en priorité."}])
server = app.server
app.index_string = app.index_string.replace("{%css%}", "{%css%}<style>" + T.variables_css() + "</style>")

REGIONS = ["Savanes", "Kara", "Centrale", "Plateaux", "Maritime"]


def titre_section_carte() -> str:
    """Titre-conclusion calculé : régions des 5 préfectures où la part d'habitants éloignés est la plus forte."""
    top = PREFS.nlargest(5, "part_hab_5km")
    regs = list(dict.fromkeys(top.region))
    noms = {"Savanes": "les Savanes", "Kara": "la Kara", "Centrale": "la région Centrale",
            "Plateaux": "les Plateaux", "Maritime": "la région Maritime"}
    liste = ", ".join(noms[r] for r in regs[:-1]) + (" et " if len(regs) > 1 else "") + noms[regs[-1]]
    return f"Les cinq préfectures les plus éloignées des soins sont dans {liste}"


TITRE_CARTE = titre_section_carte()
PART_NAT = NAT["pop_5km"] / NAT["population_2022"] * 100
TITRE_PAGE = f"Un Togolais sur {round(100 / PART_NAT)} vit à plus de 5 km d'un centre de santé"

app.layout = html.Div([
    dcc.Store(id="selection", data={"pref": None, "canton": None}),
    dcc.Download(id="telechargement"),
    html.Header(className="entete", children=[
        html.Div(className="bandeau-drapeau", children=[html.Span(style={"background": T.VERT}), html.Span(style={"background": T.JAUNE}),
                                                          html.Span(style={"background": T.VERT}), html.Span(style={"background": T.JAUNE}),
                                                          html.Span(style={"background": T.VERT})]),
        html.Div(className="entete-interieur", children=[
            html.Div([
                html.P("Data Challenge Togo AI Lab · Édition spéciale", className="surtitre"),
                html.H1(TITRE_PAGE),
                html.P("Où sont les populations les plus éloignées des soins, et où agir en priorité ? "
                       "Cliquez sur la carte pour explorer une préfecture, puis un canton.", className="sous-titre"),
            ]),
        ]),
    ]),
    html.Main(className="page", children=[
        html.Div(className="filtres", role="search", children=[
            html.Div(className="filtre", children=[html.Label("Région", htmlFor="filtre-region"),
                                                   dcc.Dropdown(id="filtre-region", options=REGIONS, multi=True, placeholder="Toutes les régions")]),
            html.Div(className="filtre filtre-large", children=[html.Label("Groupe de cantons (typologie)", htmlFor="filtre-groupe"),
                                                                dcc.Dropdown(id="filtre-groupe", options=ORDRE_GROUPES[::-1], multi=True,
                                                                             placeholder="Tous les groupes")]),
            html.Div(className="filtre filtre-large", children=[html.Label("Indicateur affiché sur la carte", htmlFor="indicateur"),
                                                                dcc.Dropdown(id="indicateur", value="part_hab_5km", clearable=False,
                                                                             options=[{"label": v["lib"], "value": k} for k, v in INDICATEURS.items()])]),
        ]),
        html.Div(className="fil", children=[
            html.Span(id="fil-texte", className="fil-texte"),
            html.Button("Retour au niveau national", id="retour", className="bouton", n_clicks=0),
        ]),

        html.Section(className="section", **{"aria-label": "Chiffres clés"}, children=[
            html.H2("En bref", className="section-titre"),
            html.Div(id="chiffres", className="chiffres"),
            html.P(id="phrase", className="phrase", **{"aria-live": "polite"}),
            html.P("Chiffre principal : distance à vol d'oiseau des localités (chefferies) au centre le plus proche, population du "
                   "canton répartie également entre ses localités. Fourchette : indicateur geodata (borne basse) et distance par la "
                   "route (borne haute). Source : geodata.gouv.tg (PRISE 2021-2022) ; INSEED, RGPH-5 2022 ; calculs de l'équipe.",
                   className="source"),
        ]),

        html.Section(className="section", **{"aria-label": "Carte et classement"}, children=[
            html.H2(TITRE_CARTE, className="section-titre"),
            html.P("La carte filtre tout le tableau de bord. Un clic sur une préfecture affiche ses cantons ; un clic sur un "
                   "canton le sélectionne.", className="section-chapo"),
            html.Div(className="grille-2", children=[
                panneau("titre-carte", None, [
                    html.Div(className="controles-panneau", children=[
                        dcc.RadioItems(id="niveau", value="prefectures", className="radio-ligne", inline=True,
                                       options=[{"label": "Préfectures", "value": "prefectures"}, {"label": "Cantons", "value": "cantons"}]),
                        dcc.Checklist(id="centres", value=[], className="coches", inline=True,
                                      options=[{"label": "Afficher les centres de santé", "value": "oui"}]),
                    ]),
                    html.Div(className="carte-et-legende", children=[
                    dcc.Graph(id="carte", style={"height": f"{HAUTEUR_CARTE}px"}, className="carte-graphe",
                              config={"displaylogo": False, "scrollZoom": False,
                                                  "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                                                  "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "carte_acces_soins"}}),
                    html.Div(id="legende-carte", className="legende-carte", **{"aria-label": "Légende de la carte"})]),
                ]),
                panneau("titre-classement", "Cliquez sur une barre pour sélectionner le territoire.", [
                    dcc.Graph(id="classement", style={"height": f"{HAUTEUR_CARTE}px"},
                              config={"displaylogo": False, "displayModeBar": False}),
                    html.P("Les barres prennent la couleur de la classe du territoire sur la carte.", className="aide"),
                ]),
            ]),
        ]),

        html.Section(className="section", **{"aria-label": "Analyses détaillées"}, children=[
            html.H2("Pour aller plus loin", className="section-titre"),
            dcc.Tabs(className="onglets", parent_className="onglets", value="nuage", children=[
                dcc.Tab(label="Croisements", value="nuage", className="tab", selected_className="tab--selected", children=[
                    html.Div(className="onglets-contenu", children=[panneau("titre-nuage", None, [
                        html.P(id="sous-titre-nuage", className="sous-titre"),
                        html.Div(className="controles-panneau", children=[
                            html.Div(className="filtre filtre-large", children=[html.Label("Axe horizontal", htmlFor="axe-x"),
                                     dcc.Dropdown(id="axe-x", value="part_hab_5km", clearable=False,
                                                  options=[{"label": v, "value": k} for k, v in AXES_NUAGE.items()])]),
                            html.Div(className="filtre filtre-large", children=[html.Label("Axe vertical", htmlFor="axe-y"),
                                     dcc.Dropdown(id="axe-y", value="pct_hab_reseau_bt", clearable=False,
                                                  options=[{"label": v, "value": k} for k, v in AXES_NUAGE.items()])]),
                        ]),
                        legende_groupes(),
                        dcc.Graph(id="nuage", style={"height": f"{HAUTEUR_NUAGE}px"},
                                  config={"displaylogo": False, "displayModeBar": False}),
                        html.P("Chaque point est un canton ; la couleur indique son groupe. rho : corrélation de rang de Spearman. "
                               "Une association n'est pas une relation de cause à effet.", className="aide"),
                    ])]),
                ]),
                dcc.Tab(label="Typologie (exploratoire)", value="typo", className="tab", selected_className="tab--selected", children=[
                    html.Div(className="onglets-contenu", children=[panneau("titre-typo", None, [
                        dcc.Graph(id="profils", figure=figure_profils(), style={"height": f"{HAUTEUR_PROFILS}px"},
                                  config={"displaylogo": False, "displayModeBar": False}),
                        html.Div(id="table-groupes"),
                        html.P(f"Lecture exploratoire : la séparation des groupes est faible (silhouette {nb(STAB.silhouette_kmeans, 2)}) "
                               f"et une autre méthode (Ward) ne retrouve qu'en partie les mêmes groupes (indice de Rand ajusté "
                               f"{nb(STAB.ari_kmeans_ward, 2)}). Les groupes sont des repères de lecture, pas des catégories d'action.",
                               className="aide"),
                    ], titre="Un groupe de cantons cumule éloignement, sous-équipement et absence de réseau (lecture exploratoire)")]),
                ]),
                dcc.Tab(label="Classement des cantons", value="table", className="tab", selected_className="tab--selected", children=[
                    html.Div(className="onglets-contenu", children=[panneau("titre-table", None, [
                        html.Div(className="controles-panneau", children=[
                            html.Button("Exporter en CSV", id="export", className="bouton bouton-plein", n_clicks=0),
                            html.Span("L'export suit les filtres et le territoire sélectionné.", className="aide"),
                        ]),
                        dash_table.DataTable(
                            id="table", page_size=15, sort_action="native", filter_action="native",
                            sort_by=[{"column_id": "rang_priorite", "direction": "asc"}],
                            columns=[{"name": n, "id": c, "type": "numeric" if t == "nombre" else "text",
                                      **({"format": {"specifier": f}} if f else {})} for c, n, t, f in COLONNES_TABLE],
                            style_table={"overflowX": "auto"},
                            style_cell={"fontFamily": POLICE, "fontSize": 13, "padding": "6px 8px", "color": ENCRE,
                                        "border": f"1px solid {BORDURE}", "whiteSpace": "normal", "height": "auto"},
                            style_header={"backgroundColor": SURFACE, "fontWeight": 600, "color": ENCRE2},
                            style_data_conditional=[{"if": {"filter_query": "{nb_centres} = 0", "column_id": "nb_centres"},
                                                     "backgroundColor": T.ROUGE_PALE, "color": T.ROUGE_TEXTE, "fontWeight": 700}]
                            + [{"if": {"filter_query": '{nom_groupe} = "' + g + '"', "column_id": "nom_groupe"},
                                "borderLeft": f"8px solid {COULEUR_GROUPE[g]}"} for g in ORDRE_GROUPES],
                            filter_options={"placeholder_text": "Filtrer…"}),
                    ], titre="Classement des cantons selon l'indice de priorité")]),
                ]),
                dcc.Tab(label="Solutions", value="solutions", className="tab", selected_className="tab--selected",
                        children=[html.Div(className="onglets-contenu", children=onglet_solutions())]),
                dcc.Tab(label="Méthode et sources", value="methode", className="tab", selected_className="tab--selected", children=[
                    html.Div(className="onglets-contenu", children=[panneau("titre-methode", None, [onglet_methode()],
                                                                            titre="Méthode, limites et sources")]),
                ]),
            ]),
        ]),
        html.Footer(className="pied", children=[
            html.P("Projet 2 du Data Challenge « Édition spéciale » du Togo AI Lab. Données : opendata.gouv.tg et "
                   "geodata.gouv.tg. Tous les chiffres sont recalculables à partir des scripts du dépôt."),
        ]),
    ]),
])


# ---------------------------------------------------------------------------- interactions
@app.callback(Output("selection", "data"),
              Input("carte", "clickData"), Input("classement", "clickData"), Input("nuage", "clickData"),
              Input("retour", "n_clicks"), State("selection", "data"), State("niveau", "value"),
              State("indicateur", "value"), prevent_initial_call=True)
def selectionner(clic_carte, clic_barre, clic_nuage, _retour, sel, niveau, indicateur):
    declencheur = ctx.triggered_id
    if declencheur == "retour":
        return {"pref": None, "canton": None}
    canton_seul = INDICATEURS[indicateur].get("canton_seul", False)
    vue_cantons = niveau == "cantons" or canton_seul or bool(sel.get("pref")) or bool(sel.get("canton"))
    if declencheur == "carte" and clic_carte:
        loc = clic_carte["points"][0].get("location")
    elif declencheur == "classement" and clic_barre:
        loc = clic_barre["points"][0]["customdata"][0]
    elif declencheur == "nuage" and clic_nuage:
        loc = clic_nuage["points"][0].get("customdata", [None])[0]
        vue_cantons = True
    else:
        return no_update
    if not loc:
        return no_update
    if vue_cantons and loc in set(CANTONS.canton_id):
        pid = CANTONS.set_index("canton_id").loc[loc, "prefecture_id"]
        return {"pref": pid, "canton": None if sel.get("canton") == loc else loc}
    if loc in set(PREFS.prefecture_id):
        return {"pref": loc, "canton": None}
    return no_update


@app.callback(Output("carte", "figure"), Output("legende-carte", "children"), Output("titre-carte", "children"),
              Output("classement", "figure"),
              Output("titre-classement", "children"), Output("chiffres", "children"), Output("phrase", "children"),
              Output("fil-texte", "children"), Output("retour", "disabled"),
              Input("selection", "data"), Input("indicateur", "value"), Input("niveau", "value"),
              Input("filtre-region", "value"), Input("filtre-groupe", "value"), Input("centres", "value"))
def actualiser(sel, indicateur, niveau, regions, groupes, centres):
    carte, vue_cantons, legende = figure_carte(sel, indicateur, niveau, regions, groupes, "oui" in (centres or []))
    classement, titre_classement = figure_classement(sel, indicateur, vue_cantons, regions, groupes)
    tuiles, phrase, titre = resume(sel)
    lib = INDICATEURS[indicateur]["lib"]
    portee = ("cantons de la préfecture" if (sel.get("pref") or sel.get("canton")) else
              "cantons" if vue_cantons else "préfectures")
    titre_carte = f"{lib} — {portee}"
    fil = ["Territoire affiché : ", html.Strong(titre)]
    return carte, legende, titre_carte, classement, titre_classement, tuiles, phrase, fil, not (sel.get("pref") or sel.get("canton"))


@app.callback(Output("nuage", "figure"), Output("titre-nuage", "children"), Output("sous-titre-nuage", "children"),
              Input("axe-x", "value"), Input("axe-y", "value"), Input("selection", "data"),
              Input("filtre-region", "value"), Input("filtre-groupe", "value"))
def actualiser_nuage(x, y, sel, regions, groupes):
    return figure_nuage(x, y, sel, regions, groupes)


def csv_excel(df: pd.DataFrame, nom: str) -> dict:
    """CSV lisible par Excel en français : point-virgule, virgule décimale, BOM UTF-8."""
    return dcc.send_string("\ufeff" + df.to_csv(index=False, sep=";", decimal=","), nom)


def table_filtree(sel, regions, groupes) -> pd.DataFrame:
    df = filtrer_cantons(regions, groupes)
    if sel.get("pref"):
        df = df[df.prefecture_id == sel["pref"]]
    return df.sort_values("rang_priorite")


@app.callback(Output("table", "data"), Output("table-groupes", "children"),
              Input("selection", "data"), Input("filtre-region", "value"), Input("filtre-groupe", "value"))
def actualiser_table(sel, regions, groupes):
    df = table_filtree(sel, regions, groupes)
    g = GROUPES.set_index("nom_groupe").loc[ORDRE_GROUPES[::-1]].reset_index()
    t = pd.DataFrame({
        "Groupe": [html.Span([html.Span(className="pastille-groupe", style={"background": COULEUR_GROUPE[n]}), n])
                   for n in g.nom_groupe], "Cantons": g.cantons.map(nb), "Habitants": g.population.map(nb),
        "Densité médiane (hab./km²)": g.densite_mediane.map(nb),
        "Hab. à plus de 5 km (%, médiane)": g.part_hab_5km_med.map(lambda v: nb(v, 1)),
        "Distance par la route (km, médiane)": g.dist_route_med_km.map(lambda v: nb(v, 1)),
        "Hab. par centre (médiane)": g.hab_par_centre_med.map(nb),
        "Hab. près du réseau BT (%, médiane)": g.pct_hab_reseau_bt_med.map(lambda v: nb(v, 1)),
    })
    return df[[c for c, *_ in COLONNES_TABLE]].round(2).to_dict("records"), \
        table_html(t, nombres=tuple(t.columns[1:]))


@app.callback(Output("telechargement", "data"), Input("export", "n_clicks"),
              State("table", "derived_virtual_data"), prevent_initial_call=True)
def exporter(_n, lignes):
    """Exporte exactement les lignes visibles du tableau (filtres, sélection et tri compris)."""
    df = pd.DataFrame(lignes or [], columns=[c for c, *_ in COLONNES_TABLE])
    for c, _n2, t, f in COLONNES_TABLE:
        if t == "nombre":
            df[c] = pd.to_numeric(df[c], errors="coerce").round(0 if ("," in f or f == "") else 1)
    df.columns = [n for _, n, *_ in COLONNES_TABLE]
    return csv_excel(df, "acces_soins_cantons.csv")


@app.callback(Output("sim-carte", "figure"), Output("sim-courbe", "figure"), Output("sim-chiffres", "children"),
              Output("sim-prefs", "children"), Output("sim-cadre", "children"), Input("n-centres", "value"))
def simuler(n):
    n = int(n or 10)
    r = SIM_SITES[SIM_SITES.rang == n].iloc[0]
    avant = SIM_PREFS[SIM_PREFS.n_centres_ajoutes == 0].set_index("prefecture_id")
    apres = SIM_PREFS[SIM_PREFS.n_centres_ajoutes == n].set_index("prefecture_id")
    gain = (avant.habitants_plus_5km - apres.habitants_plus_5km).sort_values(ascending=False)
    gain = gain[gain > 0.5].head(8)
    t = pd.DataFrame({"Préfecture": avant.loc[gain.index, "prefecture"], "Avant (%)": avant.loc[gain.index, "part_plus_5km_pct"].map(lambda v: nb(v, 1)),
                      "Après (%)": apres.loc[gain.index, "part_plus_5km_pct"].map(lambda v: nb(v, 1)), "Habitants gagnés": gain.map(nb)})
    sites = SIM_SITES[SIM_SITES.rang <= n]
    tuiles = [
        tuile(nb(r.habitants_gagnes_cumules), "", "habitants passent sous les 5 km",
              f"avec {n} nouveau{'x' if n > 1 else ''} centre{'s' if n > 1 else ''}", False),
        tuile(nb(r.part_nationale_plus_5km_pct, 1), "%", "d'habitants encore à plus de 5 km",
              f"contre {nb(r.part_nationale_initiale_pct, 1)} % aujourd'hui", False),
        tuile(nb(sites.prefecture.nunique()), "", "préfecture" + ("s reçoivent" if sites.prefecture.nunique() > 1 else " reçoit")
              + " au moins un centre", f"{nb(sites.canton.nunique())} canton{'s' if sites.canton.nunique() > 1 else ''}", False),
        tuile(nb(sites.iloc[-1].habitants_gagnes), "", f"habitants gagnés par le {n}e centre",
              f"le 1er en gagne {nb(SIM_SITES.iloc[0].habitants_gagnes)}", False),
    ]
    cadre = bloc_solution(
        f"{nb(r.habitants_gagnes_cumules)} habitants passent sous les 5 km ; la part nationale d'habitants éloignés passe de "
        f"{nb(r.part_nationale_initiale_pct, 1)} % à {nb(r.part_nationale_plus_5km_pct, 1)} %.",
        ", ".join(f"{k} ({v})" for k, v in sites.prefecture.value_counts().head(6).items())
        + (" …" if sites.prefecture.nunique() > 6 else ""), LIMITE_SIM)
    return figure_simulateur(n), figure_courbe(n), tuiles, table_html(t, nombres=("Avant (%)", "Après (%)", "Habitants gagnés")), cadre


@app.callback(Output("telechargement-solutions", "data"), Input("export-sites", "n_clicks"), Input("export-solaire", "n_clicks"),
              State("n-centres", "value"), prevent_initial_call=True)
def exporter_solutions(_a, _b, n):
    if ctx.triggered_id == "export-sites":
        df = SIM_SITES[SIM_SITES.rang <= int(n or 10)][["rang", "nom_localite", "canton", "prefecture", "region", "lon", "lat",
                                                         "habitants_gagnes", "habitants_gagnes_cumules", "part_nationale_plus_5km_pct"]]
        return csv_excel(df.round(1), f"sites_proposes_{int(n or 10)}_centres.csv")
    return csv_excel(SOLAIRE, "priorite_solaire_formations_sanitaires.csv")


if __name__ == "__main__":
    import os
    app.run(debug=False, host="127.0.0.1", port=int(os.environ.get("PORT", "8050")))
