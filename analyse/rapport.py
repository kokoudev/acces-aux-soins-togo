"""Projet 2 — Constats, recommandations et docs/analyse.md, générés à partir des résultats.

Aucun chiffre n'est saisi à la main : chaque valeur est lue dans data/ ou docs/chiffres/.
Mesure principale : habitants à plus de 5 km à vol d'oiseau d'une USP, d'un CMS ou d'un hôpital
(population du canton répartie également entre ses localités). Bornes : geodata (basse), route (haute).
Prérequis : analyse/solutions.py exécuté.
Sorties : docs/chiffres/constats.csv, recommandations.csv, prefectures.csv, groupes.csv,
          cantons_sans_centre.csv, docs/analyse.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
DATA, CH = RACINE / "data", RACINE / "docs" / "chiffres"


def f0(x) -> str:
    return f"{x:,.0f}".replace(",", " ")


def f1(x) -> str:
    return f"{x:,.1f}".replace(",", " ").replace(".", ",")


def dec(x, n=2) -> str:
    return f"{x:.{n}f}".replace(".", ",")


def tableau(df: pd.DataFrame) -> str:
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    out += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(out)


def charger() -> dict:
    x = {
        "c": pd.read_parquet(DATA / "indice_cantons.parquet"),
        "p": pd.read_parquet(DATA / "indicateurs_prefectures.parquet"),
        "d": pd.read_parquet(DATA / "distances_localites.parquet"),
        "par": json.loads((DATA / "distances_parametres.json").read_text(encoding="utf-8")),
    }
    for nom in ["correlations_spearman", "comparaison_mesures_distance", "sensibilite_indice", "typologie_choix_k",
                "typologie_profils", "typologie_stabilite", "valeurs_aberrantes", "decomposition_distances",
                "solutions_simulateur_sites", "solutions_cantons_sans_centre", "solutions_priorite_solaire_resume"]:
        x[nom] = pd.read_csv(CH / f"{nom}.csv")
    return x


def paire(corr, a, b):
    return corr[((corr.variable_1 == a) & (corr.variable_2 == b)) | ((corr.variable_1 == b) & (corr.variable_2 == a))].iloc[0]


def main() -> None:
    x = charger()
    c, p, d, par = x["c"], x["p"], x["d"], x["par"]
    corr, comp, sens = x["correlations_spearman"], x["comparaison_mesures_distance"], x["sensibilite_indice"]
    choix, prof, stab = x["typologie_choix_k"], x["typologie_profils"], x["typologie_stabilite"].iloc[0]
    dec_d, sites, sc = x["decomposition_distances"], x["solutions_simulateur_sites"], x["solutions_cantons_sans_centre"]
    sol = x["solutions_priorite_solaire_resume"].iloc[0]

    pop = c.population_2022.sum()
    hab_centre_nat = pop / c.nb_centres.sum()
    pop5, pop5_geo = c.pop_5km.sum(), c.pop_5km_geodata.sum()
    haut = comp.iloc[2]
    nc = dec_d[dec_d.composante.str.contains("plus de 1000 m du réseau")].iloc[0]
    reel = dec_d.iloc[1]
    sans = c[c.aucun_centre].sort_values("population_2022", ascending=False)
    p_tri = p.sort_values("part_hab_5km", ascending=False)
    tete = p_tri[p_tri.part_hab_5km.round(1) == round(p_tri.part_hab_5km.iloc[0], 1)]
    top_pop = p.sort_values("pop_5km", ascending=False).head(4)
    kp = p.set_index("prefecture").loc["Kpendjal"]
    r_bt, r_dens = paire(corr, "part_hab_5km", "pct_hab_reseau_bt"), paire(corr, "densite_hab_km2", "part_hab_5km")
    hop_med, hop_route = d.dist_vol_km_hopital.median(), d.dist_route_km_hopital.median()
    hop_pire = p.sort_values("dist_hopital_vol_med_km", ascending=False).iloc[0]
    s10, s50 = sites.iloc[9], sites.iloc[49]
    usp, mob = sc[sc.proposition == "Nouvelle USP"], sc[sc.proposition != "Nouvelle USP"]
    # répartition de l'effet « réseau non connecté » (seuil 1 km) et préfectures au classement routier faussé
    dd = d.merge(c[["canton_id", "prefecture", "population_2022"]], on="canton_id")
    dd["pop"] = dd.population_2022 / dd.canton_id.map(dd.groupby("canton_id").size())
    m_nc = (dd.dist_route_km_soins > 5) & (dd.dist_vol_km_soins <= 5) & (dd.acces_reseau_m > 1000)
    nc_pref = (dd[m_nc].groupby("prefecture")["pop"].sum() / dd[m_nc]["pop"].sum() * 100).sort_values(ascending=False)
    loin_reseau = (dd.groupby("prefecture").acces_reseau_m.apply(lambda s: (s > 5000).mean() * 100)
                   .sort_values(ascending=False).head(2))
    r = pd.read_parquet(DATA / "routes.parquet", columns=["longueur_m", "surface"])
    km_terre = r[r.surface == "non revêtue"].longueur_m.sum() / r.longueur_m.sum() * 100

    constats = pd.DataFrame([
        {"n": 1, "constat": f"{f0(pop5)} habitants, soit {f1(pop5 / pop * 100)} % de la population, vivent à plus de 5 km "
                            f"à vol d'oiseau d'une USP, d'un CMS ou d'un hôpital (fourchette : {f1(pop5_geo / pop * 100)} % selon "
                            f"geodata, {f1(haut.part_pct)} % par la route).",
         "chiffre": round(pop5), "territoire": "Togo", "source": "comparaison_mesures_distance.csv",
         "graphique_suggere": "Barre principale avec la fourchette basse (geodata) et haute (route) en repère"},
        {"n": 2, "constat": f"{' et '.join(tete.prefecture)} ont la plus forte part d'habitants éloignés ({f1(tete.part_hab_5km.iloc[0])} %) ; "
                            f"Kpendjal cumule le sous-équipement : un centre y dessert {f0(kp.hab_par_centre)} habitants, contre "
                            f"{f0(hab_centre_nat)} en moyenne nationale.",
         "chiffre": round(float(tete.part_hab_5km.iloc[0]), 1), "territoire": ", ".join(tete.prefecture), "source": "prefectures.csv",
         "graphique_suggere": "Carte choroplèthe des préfectures (part d'habitants à plus de 5 km)"},
        {"n": 3, "constat": f"{len(sans)} cantons, où vivent {f0(sans.population_2022.sum())} habitants, n'ont aucune USP, aucun CMS "
                            f"ni aucun hôpital ({int((sans.nb_fs == 0).sum())} n'ont aucune formation sanitaire) ; le plus peuplé est "
                            f"{sans.iloc[0].canton} ({sans.iloc[0].prefecture}, {f0(sans.iloc[0].population_2022)} habitants).",
         "chiffre": len(sans), "territoire": f"{len(sans)} cantons", "source": "solutions_cantons_sans_centre.csv",
         "graphique_suggere": "Carte des cantons avec les centres de santé, cantons sans centre en jaune"},
        {"n": 4, "constat": f"50 nouveaux centres bien placés feraient passer {f0(s50.habitants_gagnes_cumules)} habitants sous les "
                            f"5 km : la part d'habitants éloignés descendrait de {f1(s50.part_nationale_initiale_pct)} % à "
                            f"{f1(s50.part_nationale_plus_5km_pct)} % (avec 10 centres : {f0(s10.habitants_gagnes_cumules)} habitants).",
         "chiffre": round(float(s50.habitants_gagnes_cumules)), "territoire": "Togo", "source": "solutions_simulateur_sites.csv",
         "graphique_suggere": "Courbe : habitants gagnés selon le nombre de centres ajoutés (1 à 50)"},
        {"n": 5, "constat": f"Depuis une localité, l'hôpital le plus proche est en médiane à {f1(hop_med)} km à vol d'oiseau "
                            f"({f1(hop_route)} km par la route) ; dans la préfecture de {hop_pire.prefecture}, il est à "
                            f"{f1(hop_pire.dist_hopital_vol_med_km)} km à vol d'oiseau.",
         "chiffre": round(float(hop_med), 1), "territoire": f"Togo (maximum : {hop_pire.prefecture})", "source": "prefectures.csv",
         "graphique_suggere": "Classement des préfectures par distance médiane à l'hôpital"},
    ])
    constats.to_csv(CH / "constats.csv", index=False, encoding="utf-8")

    pref_sites = sites.head(10).prefecture.value_counts()
    reco = pd.DataFrame([
        {"n": 1, "territoire": "10 premiers sites du simulateur : " + ", ".join(f"{k} ({v})" for k, v in pref_sites.items()),
         "recommandation": f"Implanter les nouveaux centres sur les sites proposés par le simulateur : les 10 premiers font passer "
                           f"{f0(s10.habitants_gagnes_cumules)} habitants sous les 5 km, les 50 premiers {f0(s50.habitants_gagnes_cumules)}.",
         "limite": "Un centre construit sans personnel ni médicaments ne sert à rien ; la population est supposée répartie de façon "
                   "égale entre les chefferies d'un même canton ; la distance est à vol d'oiseau ; le coût n'est pas pris en compte."},
        {"n": 2, "territoire": ", ".join(usp.canton + " (" + usp.prefecture + ")"),
         "recommandation": f"Créer une USP dans les {len(usp)} cantons sans centre assez peuplés et majoritairement éloignés "
                           f"({f0(usp.population_2022.sum())} habitants, dont {f0(usp.habitants_plus_5km.sum())} à plus de 5 km).",
         "limite": f"Règle de décision simple (population d'au moins {f0(hab_centre_nat)} habitants, soit la moyenne nationale "
                   "par centre, et plus de la moitié à plus de 5 km) ; même limite de personnel que la recommandation 1."},
        {"n": 3, "territoire": f"{len(mob)} autres cantons sans centre",
         "recommandation": f"Desservir par des cliniques mobiles (passages réguliers) les {len(mob)} autres cantons sans centre "
                           f"({f0(mob.population_2022.sum())} habitants), trop petits pour un centre fixe ou déjà proches d'un "
                           "centre voisin.",
         "limite": "La fréquence des passages et le coût des équipes ne peuvent pas être estimés avec les données publiées ; "
                   "la population de certains cantons est estimée."},
        {"n": 4, "territoire": f"{int(sol.cantons_cibles)} cantons sans habitant proche du réseau BT ({int(sol.prefectures_concernees)} préfectures)",
         "recommandation": f"Équiper en solaire en priorité les {int(sol.formations_sanitaires)} formations sanitaires de ces cantons "
                           f"({int(sol.dont_usp_cms)} USP ou CMS, {int(sol.dont_publiques)} publiques), qui servent "
                           f"{f0(sol.population_cantons_cibles)} habitants.",
         "limite": "L'électrification de chaque centre n'est pas publiée : certains ont peut-être déjà un panneau solaire, un "
                   "groupe électrogène ou le réseau à proximité ; l'indicateur mesure la proximité du réseau pour les habitants, pas "
                   "pour le centre ; le coût d'équipement n'est pas estimé."},
        {"n": 5, "territoire": ", ".join(top_pop.prefecture),
         "recommandation": "Renforcer les agents de santé communautaires là où le nombre d'habitants éloignés est le plus "
                           f"élevé : ces quatre préfectures en comptent {f0(top_pop.pop_5km.sum())}.",
         "limite": f"La distance ne tient compte ni de l'état des routes ({f1(km_terre)} % du linéaire non revêtu) ni de la "
                   "saison des pluies ; aucun temps de trajet n'est publié."},
    ])
    reco.to_csv(CH / "recommandations.csv", index=False, encoding="utf-8")

    cols_p = ["prefecture", "region", "population_2022", "nb_centres", "hab_par_centre", "hab_par_personnel",
              "part_hab_5km", "pop_5km", "part_hab_5km_geodata", "part_hab_5km_route", "dist_route_med_km",
              "dist_hopital_vol_med_km", "dist_hopital_med_km", "cantons_sans_centre", "pct_hab_reseau_bt",
              "taux_elec_pref_2021", "elec_valeur_de_zone"]
    p.sort_values("part_hab_5km", ascending=False)[cols_p].round(1).to_csv(CH / "prefectures.csv", index=False, encoding="utf-8")
    sans[["canton_id", "canton", "commune", "prefecture", "population_2022", "nb_fs", "part_hab_5km", "dist_route_med_km"]] \
        .round(1).to_csv(CH / "cantons_sans_centre.csv", index=False, encoding="utf-8")
    prof.to_csv(CH / "groupes.csv", index=False, encoding="utf-8")

    noyau = c[c.top20_nb_variantes == 5].sort_values("rang_priorite")
    top10 = c.sort_values("rang_priorite").head(10)[["rang_priorite", "canton", "prefecture", "population_2022",
                                                    "population_estimee", "indice_priorite", "top20_nb_variantes"]].copy()
    top10["canton"] = top10.canton + top10.population_estimee.map({True: " *", False: ""})
    top10["population_2022"] = top10.population_2022.map(f0)
    top10["indice_priorite"] = top10.indice_priorite.map(f1)
    top10 = top10.drop(columns="population_estimee")
    top10.columns = ["Rang", "Canton", "Préfecture", "Habitants", "Indice", "Top 20 (sur 5 variantes)"]
    gr = prof[["nom_groupe", "cantons", "population", "densite_mediane", "part_hab_5km_med", "hab_par_centre_med",
               "pct_hab_reseau_bt_med", "indice_moyen"]].sort_values("indice_moyen").copy()
    gr["population"] = gr.population.map(f0)
    gr.columns = ["Groupe (exploratoire)", "Cantons", "Habitants", "Densité méd.", "Hab. > 5 km (%, méd.)",
                  "Hab. par centre (méd.)", "Hab. près réseau BT (%, méd.)", "Indice moyen"]
    nb_fs = len(pd.read_parquet(DATA / "formations_sanitaires.parquet", columns=["canton_id"]))
    dec_t = dec_d[["composante", "habitants", "part_population_pct", "part_estimation_haute_pct"]].copy()
    dec_t["habitants"] = dec_t.habitants.map(f0)
    dec_t["part_population_pct"] = dec_t.part_population_pct.map(lambda v: dec(v, 1))
    dec_t["part_estimation_haute_pct"] = dec_t.part_estimation_haute_pct.map(lambda v: dec(v, 1))
    dec_t.columns = ["Composante", "Habitants", "% de la population", "% de l'estimation haute"]
    comp_t = pd.DataFrame({
        "Rôle": ["Borne basse", "Chiffre principal", "Borne haute"], "Mesure": comp.mesure,
        "Habitants": comp.population.map(f0), "%": comp.part_pct.map(lambda v: dec(v, 1)),
        "rho avec geodata (cantons)": comp.rho_avec_geodata_par_canton.map(lambda v: dec(v, 2))})

    md = f"""# Projet 2 — L'accès aux soins : analyse

Document généré par `analyse/rapport.py`. Tous les chiffres viennent des fichiers de `data/` et de
`docs/chiffres/`.

## Problématique

Quelles populations du Togo sont les plus éloignées d'un centre de santé, et où faudrait-il agir en
priorité ? Unité d'analyse : les **396 cantons** (agrégés en 39 préfectures pour la lecture).

## Données

| Donnée | Source | Année |
|---|---|---|
| Formations sanitaires ({f0(nb_fs)} points, type, secteur) | geodata.gouv.tg | PRISE 2021-2022 |
| Réseau routier ({f0(r.longueur_m.sum() / 1000)} km) | geodata.gouv.tg | PRISE 2021-2022 |
| Localités géolocalisées ({f0(par['origines'])} chefferies) | geodata.gouv.tg | PRISE 2021-2022 |
| Limites des cantons, communes, préfectures, régions | geodata.gouv.tg | PRISE 2021-2022 |
| Indicateurs par canton (habitants à moins de 5 km, personnel, réseau BT) | geodata.gouv.tg | PRISE 2021-2022 |
| Population résidente par canton (RGPH-5) | opendata.gouv.tg (INSEED) | 2022 |
| Taux d'accès à l'électricité par préfecture | opendata.gouv.tg (INSEED) | 2021 |

100 % des fichiers utilisés viennent de opendata.gouv.tg ou geodata.gouv.tg (liste exacte : `dashboard/donnees/sources_utilisees.csv` ; tous les fichiers téléchargés : `data/sources.csv`).

## Le chiffre principal sur les distances

**Chiffre principal : {f0(pop5)} habitants, soit {f1(pop5 / pop * 100)} %, vivent à plus de 5 km à vol d'oiseau d'une USP,
d'un CMS ou d'un hôpital.** Il est retenu parce que :
1. il applique la norme publiée sur geodata, le « rayon d'action théorique des USP (5 km) », qui est une distance en ligne droite ;
2. il est entièrement recalculable avec les données publiées (centres, localités, population RGPH 2022) ;
3. il est conforté par le calcul de geodata : corrélation de rang de {dec(comp.iloc[1].rho_avec_geodata_par_canton)} entre cantons ;
4. c'est la base que le simulateur de solutions peut faire évoluer.

Hypothèse : la population d'un canton est répartie de façon égale entre ses localités (chefferies).

**Les deux autres mesures sont des bornes :**

{tableau(comp_t)}

- Borne basse : geodata ({f1(pop5_geo / pop * 100)} %) pondère avec une base de population plus fine mais non publiée.
- Borne haute : par la route ({f1(haut.part_pct)} %). Elle est gonflée par le réseau routier publié, incomplet :

{tableau(dec_t)}

Sur les {f1(haut.part_pct)} points de la borne haute, {f1(reel.part_population_pct)} correspondent à des habitants éloignés même à vol
d'oiseau, et **{f1(nc.part_population_pct)} points ({f1(nc.part_estimation_haute_pct)} % de la borne haute) viennent de localités proches
d'un centre à vol d'oiseau mais à plus de 1 km du réseau routier connecté** : c'est l'effet du réseau non connecté
(seuil de 500 m : {f1(dec_d.iloc[2].part_estimation_haute_pct)} % ; seuil de 2 km : {f1(dec_d.iloc[4].part_estimation_haute_pct)} %). Cet
effet est réparti sur tout le pays (la préfecture la plus touchée, {nc_pref.index[0]}, n'en représente que
{f1(nc_pref.iloc[0])} %). Il fausse en revanche le classement par la route de {' et '.join(loin_reseau.index)} :
{' et '.join(f1(v) + ' %' for v in loin_reseau.values)} de leurs localités sont à plus de 5 km du réseau connecté,
alors que des routes existent à proximité, dans des tronçons non reliés au reste du réseau publié.

## Méthode

1. **Centres de santé** : USP, CMS et hôpitaux ({f0(c.nb_centres.sum())} établissements). Les cases de santé et
   infirmeries sont comptées à part (offre plus limitée).
2. **Distances** : à vol d'oiseau (mesure principale) et par la route (borne haute). Le réseau routier publié
   n'est pas topologique ; il a été découpé aux intersections ({f0(par['segments_apres_decoupage'])} segments) et les
   impasses raccordées aux nœuds à moins de {par['tolerance_raccord_m']} m ({f0(par['raccords_ajoutes'])} raccords). La plus
   grande composante connexe couvre {f1(par['part_longueur_composante_principale'] * 100)} % de la longueur.
3. **Indice de priorité (0-100)** : moyenne de trois dimensions en rangs centiles — éloignement (mesure principale),
   capacité (habitants par centre, habitants par agent de santé), électricité (habitants loin du réseau BT).
   Pondération égale. Un canton sans centre reçoit le pire rang de capacité ; un personnel nul dans un canton qui a
   des centres est traité comme une donnée manquante (la capacité ne retient alors que les habitants par centre).
   **Sensibilité** :

{tableau(sens.rename(columns={'variante': 'Variante', 'rho_spearman_avec_reference': 'rho avec la référence', 'top20_communs_avec_reference': 'Top 20 communs'}))}

   Le classement d'ensemble est stable (rho ≥ {dec(sens.rho_spearman_avec_reference.min(), 3)}), mais la composition exacte du top 20
   varie ({sens.top20_communs_avec_reference.min()} à {sens.top20_communs_avec_reference.max()} cantons communs). On retient donc un **noyau
   robuste de {len(noyau)} cantons**, présents dans le top 20 des cinq versions : {', '.join(noyau.canton)}.
4. **Corrélations** : Spearman sur 396 cantons, p-valeurs corrigées par la méthode de Holm (tests multiples) et rho
   partiel à densité égale. Les cantons voisins se ressemblent : les p-valeurs sont optimistes, seul l'ordre de
   grandeur des rho compte.

## Constats clés

{chr(10).join(f"{k.n}. {k.constat}" for k in constats.itertuples())}

Associations (Spearman, 396 cantons) : la densité est associée à un moindre éloignement
(rho = {dec(r_dens.rho)}). L'éloignement tend à aller avec un faible accès au réseau électrique (rho = {dec(r_bt.rho)}),
mais cette association est faible et s'explique en partie par le contraste ville / campagne (rho à densité égale :
{dec(r_bt.rho_partiel_densite)}). Ce sont des associations, pas des causes.

## Cantons prioritaires (indice)

{tableau(top10)}

\\* population estimée (unité RGPH répartie entre plusieurs cantons) : le rang de ces cantons est fragile.
Les cantons en tête de l'indice sont souvent peu peuplés : pour cibler les moyens, l'indice se lit avec le nombre
d'habitants éloignés (`docs/chiffres/prefectures.csv`) et avec le simulateur.

## Typologie (exploratoire)

Regroupement automatique (k-means, graine fixée) sur les trois dimensions de l'indice et la densité. **Il est
présenté à titre exploratoire** : la séparation des groupes est faible (silhouette de {dec(stab.silhouette_kmeans, 2)} ;
de k = 3 à 6 : {', '.join(f"{k.k} → {dec(k.silhouette, 3)}" for k in choix.itertuples())}), et une autre méthode
(classification hiérarchique de Ward) ne retrouve qu'en partie les mêmes groupes (indice de Rand ajusté de
{dec(stab.ari_kmeans_ward, 2)}). Les groupes sont stables d'un tirage à l'autre (indice de Rand ajusté ≥ {dec(stab.ari_min_10_graines, 2)} sur
10 graines), mais ce sont des repères de lecture, pas des catégories d'action. Les noms décrivent les dimensions où le
score moyen du groupe dépasse 50.

{tableau(gr)}

## Solutions et recommandations

Le détail des solutions (simulateur, cantons sans centre, priorité solaire) est dans
`docs/chiffres/solutions_*.csv` et dans l'onglet « Solutions » du tableau de bord.

{chr(10).join(f"{k.n}. **{k.territoire}** — {k.recommandation}" + chr(10) + f"   *Limite :* {k.limite}" for k in reco.itertuples())}

## Limites générales

1. **Années différentes** : équipements 2021-2022, population 2022, électricité 2021.
2. **Population localisée au canton** : sans grille de population publiée, elle est répartie également entre les localités.
3. **Réseau routier incomplet** : {f1(100 - par['part_longueur_composante_principale'] * 100)} % de la longueur hors composante principale ; c'est
   pourquoi la distance par la route n'est qu'une borne haute.
4. **Qualité de la route** : {f1(km_terre)} % du linéaire n'est pas revêtu ; aucune vitesse ni temps de trajet n'est publié.
5. **Offre de soins** : présence d'un établissement, pas son fonctionnement (horaires, personnel présent, médicaments).
6. **Électrification des centres absente** des fichiers publiés ; on utilise la proximité du réseau BT des habitants.
7. **Valeurs aberrantes** : {len(x['valeurs_aberrantes'])} signalements (`valeurs_aberrantes.csv`), conservés ; l'indice utilise des rangs.
8. **Typologie exploratoire** (silhouette {dec(stab.silhouette_kmeans, 2)}).
"""
    (RACINE / "docs" / "analyse.md").write_text(md, encoding="utf-8")
    print(constats.constat.to_string())
    print(reco[["territoire", "recommandation"]].to_string())


if __name__ == "__main__":
    main()
