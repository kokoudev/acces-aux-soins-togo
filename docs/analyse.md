# Projet 2 — L'accès aux soins : analyse

Document généré par `analyse/rapport.py`. Tous les chiffres viennent des fichiers de `data/` et de
`docs/chiffres/`.

## Problématique

Quelles populations du Togo sont les plus éloignées d'un centre de santé, et où faudrait-il agir en
priorité ? Unité d'analyse : les **396 cantons** (agrégés en 39 préfectures pour la lecture).

## Données

| Donnée | Source | Année |
|---|---|---|
| Formations sanitaires (2 271 points, type, secteur) | geodata.gouv.tg | PRISE 2021-2022 |
| Réseau routier (48 008 km) | geodata.gouv.tg | PRISE 2021-2022 |
| Localités géolocalisées (7 938 chefferies) | geodata.gouv.tg | PRISE 2021-2022 |
| Limites des cantons, communes, préfectures, régions | geodata.gouv.tg | PRISE 2021-2022 |
| Indicateurs par canton (habitants à moins de 5 km, personnel, réseau BT) | geodata.gouv.tg | PRISE 2021-2022 |
| Population résidente par canton (RGPH-5) | opendata.gouv.tg (INSEED) | 2022 |
| Taux d'accès à l'électricité par préfecture | opendata.gouv.tg (INSEED) | 2021 |

100 % des fichiers utilisés viennent de opendata.gouv.tg ou geodata.gouv.tg (liste exacte : `dashboard/donnees/sources_utilisees.csv` ; tous les fichiers téléchargés : `data/sources.csv`).

## Le chiffre principal sur les distances

**Chiffre principal : 1 026 437 habitants, soit 12,7 %, vivent à plus de 5 km à vol d'oiseau d'une USP,
d'un CMS ou d'un hôpital.** Il est retenu parce que :
1. il applique la norme publiée sur geodata, le « rayon d'action théorique des USP (5 km) », qui est une distance en ligne droite ;
2. il est entièrement recalculable avec les données publiées (centres, localités, population RGPH 2022) ;
3. il est conforté par le calcul de geodata : corrélation de rang de 0,90 entre cantons ;
4. c'est la base que le simulateur de solutions peut faire évoluer.

Hypothèse : la population d'un canton est répartie de façon égale entre ses localités (chefferies).

**Les deux autres mesures sont des bornes :**

| Rôle | Mesure | Habitants | % | rho avec geodata (cantons) |
|---|---|---|---|---|
| Borne basse | geodata : habitants à plus de 5 km (vol d'oiseau, pondéré par la population) | 777 936 | 9,6 | 1,00 |
| Chiffre principal | localités à plus de 5 km à vol d'oiseau, population répartie également entre localités | 1 026 437 | 12,7 | 0,90 |
| Borne haute | localités à plus de 5 km par la route, population répartie également entre localités | 2 361 016 | 29,2 | 0,77 |

- Borne basse : geodata (9,6 %) pondère avec une base de population plus fine mais non publiée.
- Borne haute : par la route (29,2 %). Elle est gonflée par le réseau routier publié, incomplet :

| Composante | Habitants | % de la population | % de l'estimation haute |
|---|---|---|---|
| Estimation haute : habitants à plus de 5 km par la route | 2 361 016 | 29,2 | 100,0 |
| … dont aussi à plus de 5 km à vol d'oiseau (éloignement réel) | 1 026 437 | 12,7 | 43,5 |
| … dont à moins de 5 km à vol d'oiseau mais à plus de 500 m du réseau routier connecté | 826 591 | 10,2 | 35,0 |
| … dont à moins de 5 km à vol d'oiseau mais à plus de 1000 m du réseau routier connecté | 575 643 | 7,1 | 24,4 |
| … dont à moins de 5 km à vol d'oiseau mais à plus de 2000 m du réseau routier connecté | 272 718 | 3,4 | 11,6 |
| … dont à moins de 5 km à vol d'oiseau et à moins de 1000 m du réseau (détours du réseau) | 758 937 | 9,4 | 32,1 |

Sur les 29,2 points de la borne haute, 12,7 correspondent à des habitants éloignés même à vol
d'oiseau, et **7,1 points (24,4 % de la borne haute) viennent de localités proches
d'un centre à vol d'oiseau mais à plus de 1 km du réseau routier connecté** : c'est l'effet du réseau non connecté
(seuil de 500 m : 35,0 % ; seuil de 2 km : 11,6 %). Cet
effet est réparti sur tout le pays (la préfecture la plus touchée, Kéran, n'en représente que
6,7 %). Il fausse en revanche le classement par la route de Kpendjal et Mô :
90,6 % et 86,8 % de leurs localités sont à plus de 5 km du réseau connecté,
alors que des routes existent à proximité, dans des tronçons non reliés au reste du réseau publié.

## Méthode

1. **Centres de santé** : USP, CMS et hôpitaux (2 027 établissements). Les cases de santé et
   infirmeries sont comptées à part (offre plus limitée).
2. **Distances** : à vol d'oiseau (mesure principale) et par la route (borne haute). Le réseau routier publié
   n'est pas topologique ; il a été découpé aux intersections (187 237 segments) et les
   impasses raccordées aux nœuds à moins de 50 m (28 229 raccords). La plus
   grande composante connexe couvre 88,3 % de la longueur.
3. **Indice de priorité (0-100)** : moyenne de trois dimensions en rangs centiles — éloignement (mesure principale),
   capacité (habitants par centre, habitants par agent de santé), électricité (habitants loin du réseau BT).
   Pondération égale. Un canton sans centre reçoit le pire rang de capacité ; un personnel nul dans un canton qui a
   des centres est traité comme une donnée manquante (la capacité ne retient alors que les habitants par centre).
   **Sensibilité** :

| Variante | rho avec la référence | Top 20 communs |
|---|---|---|
| éloignement renforcé (50/25/25) | 0.975 | 18 |
| sans électricité (50/50/0) | 0.901 | 12 |
| capacité renforcée (25/50/25) | 0.976 | 18 |
| normalisation min-max (égale) | 0.96 | 11 |

   Le classement d'ensemble est stable (rho ≥ 0,901), mais la composition exacte du top 20
   varie (11 à 18 cantons communs). On retient donc un **noyau
   robuste de 9 cantons**, présents dans le top 20 des cinq versions : Fazao, Tambigou, Kountoire, Kamina-Akébou, Borgou, Bapuré, Glitto, Louanga, Nawaré.
4. **Corrélations** : Spearman sur 396 cantons, p-valeurs corrigées par la méthode de Holm (tests multiples) et rho
   partiel à densité égale. Les cantons voisins se ressemblent : les p-valeurs sont optimistes, seul l'ordre de
   grandeur des rho compte.

## Constats clés

1. 1 026 437 habitants, soit 12,7 % de la population, vivent à plus de 5 km à vol d'oiseau d'une USP, d'un CMS ou d'un hôpital (fourchette : 9,6 % selon geodata, 29,2 % par la route).
2. Mô et Kpendjal ont la plus forte part d'habitants éloignés (52,5 %) ; Kpendjal cumule le sous-équipement : un centre y dessert 22 091 habitants, contre 3 994 en moyenne nationale.
3. 16 cantons, où vivent 73 004 habitants, n'ont aucune USP, aucun CMS ni aucun hôpital (15 n'ont aucune formation sanitaire) ; le plus peuplé est Louanga (Tône, 11 434 habitants).
4. 50 nouveaux centres bien placés feraient passer 393 307 habitants sous les 5 km : la part d'habitants éloignés descendrait de 12,7 % à 7,8 % (avec 10 centres : 128 436 habitants).
5. Depuis une localité, l'hôpital le plus proche est en médiane à 11,5 km à vol d'oiseau (18,2 km par la route) ; dans la préfecture de Oti-Sud, il est à 28,4 km à vol d'oiseau.

Associations (Spearman, 396 cantons) : la densité est associée à un moindre éloignement
(rho = -0,54). L'éloignement tend à aller avec un faible accès au réseau électrique (rho = -0,31),
mais cette association est faible et s'explique en partie par le contraste ville / campagne (rho à densité égale :
-0,15). Ce sont des associations, pas des causes.

## Cantons prioritaires (indice)

| Rang | Canton | Préfecture | Habitants | Indice | Top 20 (sur 5 variantes) |
|---|---|---|---|---|---|
| 1 | Fazao | Sotouboua | 2 289 | 96,8 | 5 |
| 2 | Tambigou | Kpendjal | 9 361 | 96,6 | 5 |
| 3 | Kountoire | Oti-Sud | 13 450 | 92,5 | 5 |
| 4 | Kamina-Akébou | Akébou | 14 632 | 92,0 | 5 |
| 5 | Gouloungoussi | Cinkassé | 3 707 | 88,8 | 4 |
| 6 | Borgou | Kpendjal | 40 462 | 88,7 | 5 |
| 7 | Welly | Blitta | 10 170 | 88,4 | 3 |
| 8 | Ekéto * | Wawa | 6 805 | 87,8 | 3 |
| 9 | Bapuré | Dankpen | 25 428 | 87,8 | 5 |
| 10 | Nandouta | Dankpen | 14 114 | 87,7 | 3 |

\* population estimée (unité RGPH répartie entre plusieurs cantons) : le rang de ces cantons est fragile.
Les cantons en tête de l'indice sont souvent peu peuplés : pour cibler les moyens, l'indice se lit avec le nombre
d'habitants éloignés (`docs/chiffres/prefectures.csv`) et avec le simulateur.

## Typologie (exploratoire)

Regroupement automatique (k-means, graine fixée) sur les trois dimensions de l'indice et la densité. **Il est
présenté à titre exploratoire** : la séparation des groupes est faible (silhouette de 0,30 ;
de k = 3 à 6 : 3 → 0,268, 4 → 0,296, 5 → 0,295, 6 → 0,306), et une autre méthode
(classification hiérarchique de Ward) ne retrouve qu'en partie les mêmes groupes (indice de Rand ajusté de
0,59). Les groupes sont stables d'un tirage à l'autre (indice de Rand ajusté ≥ 0,98 sur
10 graines), mais ce sont des repères de lecture, pas des catégories d'action. Les noms décrivent les dimensions où le
score moyen du groupe dépasse 50.

| Groupe (exploratoire) | Cantons | Habitants | Densité méd. | Hab. > 5 km (%, méd.) | Hab. par centre (méd.) | Hab. près réseau BT (%, méd.) | Indice moyen |
|---|---|---|---|---|---|---|---|
| Villes bien desservies | 29 | 3 185 151 | 2025.7 | 0.0 | 3166.3 | 59.0 | 22.2 |
| Cantons ruraux proches et dotés | 124 | 1 450 536 | 106.4 | 0.0 | 3076.9 | 27.0 | 31.6 |
| Cantons sous-équipés et loin du réseau électrique | 95 | 1 222 190 | 188.9 | 0.0 | 6112.0 | 9.0 | 51.5 |
| Cantons cumulant éloignement, sous-équipement et absence de réseau | 148 | 2 237 621 | 63.6 | 33.3 | 7334.0 | 8.0 | 69.8 |

## Solutions et recommandations

Le détail des solutions (simulateur, cantons sans centre, priorité solaire) est dans
`docs/chiffres/solutions_*.csv` et dans l'onglet « Solutions » du tableau de bord.

1. **10 premiers sites du simulateur : Haho (2), Tchamba (2), Kpendjal-Ouest (1), Oti (1), Assoli (1), Kpendjal (1), Oti-Sud (1), Anié (1)** — Implanter les nouveaux centres sur les sites proposés par le simulateur : les 10 premiers font passer 128 436 habitants sous les 5 km, les 50 premiers 393 307.
   *Limite :* Un centre construit sans personnel ni médicaments ne sert à rien ; la population est supposée répartie de façon égale entre les chefferies d'un même canton ; la distance est à vol d'oiseau ; le coût n'est pas pris en compte.
2. **Tambigou (Kpendjal), M'Poti (Blitta)** — Créer une USP dans les 2 cantons sans centre assez peuplés et majoritairement éloignés (16 332 habitants, dont 14 658 à plus de 5 km).
   *Limite :* Règle de décision simple (population d'au moins 3 994 habitants, soit la moyenne nationale par centre, et plus de la moitié à plus de 5 km) ; même limite de personnel que la recommandation 1.
3. **14 autres cantons sans centre** — Desservir par des cliniques mobiles (passages réguliers) les 14 autres cantons sans centre (56 672 habitants), trop petits pour un centre fixe ou déjà proches d'un centre voisin.
   *Limite :* La fréquence des passages et le coût des équipes ne peuvent pas être estimés avec les données publiées ; la population de certains cantons est estimée.
4. **58 cantons sans habitant proche du réseau BT (19 préfectures)** — Équiper en solaire en priorité les 107 formations sanitaires de ces cantons (94 USP ou CMS, 81 publiques), qui servent 442 554 habitants.
   *Limite :* L'électrification de chaque centre n'est pas publiée : certains ont peut-être déjà un panneau solaire, un groupe électrogène ou le réseau à proximité ; l'indicateur mesure la proximité du réseau pour les habitants, pas pour le centre ; le coût d'équipement n'est pas estimé.
5. **Haho, Tchamba, Oti-Sud, Dankpen** — Renforcer les agents de santé communautaires là où le nombre d'habitants éloignés est le plus élevé : ces quatre préfectures en comptent 351 893.
   *Limite :* La distance ne tient compte ni de l'état des routes (94,3 % du linéaire non revêtu) ni de la saison des pluies ; aucun temps de trajet n'est publié.

## Limites générales

1. **Années différentes** : équipements 2021-2022, population 2022, électricité 2021.
2. **Population localisée au canton** : sans grille de population publiée, elle est répartie également entre les localités.
3. **Réseau routier incomplet** : 11,7 % de la longueur hors composante principale ; c'est
   pourquoi la distance par la route n'est qu'une borne haute.
4. **Qualité de la route** : 94,3 % du linéaire n'est pas revêtu ; aucune vitesse ni temps de trajet n'est publié.
5. **Offre de soins** : présence d'un établissement, pas son fonctionnement (horaires, personnel présent, médicaments).
6. **Électrification des centres absente** des fichiers publiés ; on utilise la proximité du réseau BT des habitants.
7. **Valeurs aberrantes** : 212 signalements (`valeurs_aberrantes.csv`), conservés ; l'indice utilise des rangs.
8. **Typologie exploratoire** (silhouette 0,30).
