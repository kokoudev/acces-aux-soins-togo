# Santé à 5 km : cartographier l'accès aux soins au Togo pour mieux implanter les centres de santé

**Auteurs :** SOEDJE Kokou Ariel Caesar et TCHALIM Eyasama Brice

Un tableau de bord interactif qui mesure, pour chacun des 396 cantons du Togo, la part des habitants
vivant à plus de 5 km d'un centre de santé, et qui aide à choisir où implanter de nouveaux centres,
à partir des seules données publiques d'opendata.gouv.tg et de geodata.gouv.tg.

## Lancement (3 commandes)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux / macOS : .venv/bin/python -m pip ...
.venv/Scripts/python app.py                               # puis ouvrir http://127.0.0.1:8050
```

Python 3.11 ou plus récent (testé avec 3.13). Les présentations et la liste des jeux de données de la
soumission se trouvent dans le dossier `livrables/`.

## Présentation

Projet 2 du Data Challenge « Édition spéciale » du Togo AI Lab (Ministère de l'Efficacité du Service
Public et de la Transformation Numérique).

**Question :** quelles populations sont les plus éloignées d'un centre de santé, et où faudrait-il agir
en priorité ? Unité d'analyse : les 396 cantons du Togo, agrégés en 39 préfectures.

## Ce que montre le tableau de bord

1. **En bref** : quatre chiffres clés et une phrase en français simple pour le territoire choisi
   (Togo, préfecture ou canton).
2. **Carte cliquable** : un clic sur une préfecture affiche ses cantons, un clic sur un canton le
   sélectionne, et tout le tableau de bord suit. Le bouton « Retour au niveau national » remet à zéro.
   On choisit l'indicateur affiché sur la carte ; on peut afficher les centres de santé.
3. **Pour aller plus loin** : croisements entre indicateurs (corrélation de Spearman calculée en direct),
   profils de la typologie (exploratoire), classement complet des cantons avec **export CSV**, onglet
   **Solutions** (simulateur d'implantation de 1 à 50 nouveaux centres, cantons sans centre, priorité solaire),
   onglet **Méthode et sources**.

Chiffre principal : habitants à plus de 5 km **à vol d'oiseau** d'une USP, d'un CMS ou d'un hôpital (norme du
rayon d'action de 5 km publiée sur geodata), avec une fourchette : indicateur geodata (borne basse) et distance par
la route (borne haute). Les couleurs sont définies une seule fois dans `theme.py` (couleurs du drapeau).

Filtres croisés : région et groupe de cantons (typologie), appliqués à la carte, au classement,
aux croisements et au tableau.

## Sources

100 % des données viennent de **opendata.gouv.tg** et **geodata.gouv.tg** (liste détaillée dans
`donnees/sources_utilisees.csv`) :

| Donnée | Plateforme | Année |
|---|---|---|
| Formations sanitaires géolocalisées | geodata.gouv.tg | PRISE 2021-2022 |
| Réseau routier (48 008 km) | geodata.gouv.tg | PRISE 2021-2022 |
| Localités (chefferies) | geodata.gouv.tg | PRISE 2021-2022 |
| Limites administratives (régions à cantons) | geodata.gouv.tg | PRISE 2021-2022 |
| Indicateurs par canton (habitants à moins de 5 km, personnel, réseau BT) | geodata.gouv.tg | PRISE 2021-2022 |
| Population par canton, RGPH-5 (INSEED) | opendata.gouv.tg | 2022 |
| Taux d'accès à l'électricité par préfecture (INSEED) | opendata.gouv.tg | 2021 |

## Méthode (résumé)

- **Distance par la route** de chacune des 7 938 localités à la formation sanitaire la plus proche,
  sur le réseau routier reconstruit (découpage aux intersections, raccord des impasses à moins de 50 m).
- **Deux bornes d'éloignement** : borne basse geodata (vol d'oiseau, pondérée par la population) et
  borne haute par la route (population répartie également entre localités).
- **Indice de priorité** (0-100) : éloignement, capacité (habitants par centre et par agent),
  électricité ; rangs centiles, pondération égale, test de sensibilité sur 4 variantes.
- **Typologie** : k-means en 4 groupes (choix argumenté par le score de silhouette).

Détails, constats, recommandations et limites : `docs/analyse.md`. Chiffres clés : `docs/chiffres/`.
Les scripts d'analyse sont dans `analyse/` (ils nécessitent les données complètes du dépôt GitHub).

## Déploiement sur Render

Le fichier `render.yaml` décrit le service : `gunicorn app:server`. Étapes dans le README du dépôt.
