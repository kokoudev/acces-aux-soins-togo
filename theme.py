"""Thème unique du tableau de bord : couleurs du drapeau togolais, classes de la carte.

Toutes les couleurs sont définies ICI une seule fois. Les graphiques importent ce module ; le CSS
reçoit les mêmes valeurs sous forme de variables (--...) injectées dans la page par app.py.
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------- couleurs de base
VERT = "#006A4E"          # accents, boutons, focus (vert du drapeau)
VERT_FONCE = "#004D38"
VERT_PALE = "#E6F2EE"
JAUNE = "#FFCE00"         # jaune du drapeau
ROUGE = "#D21034"         # rouge du drapeau : alertes uniquement (et classe grave)
ROUGE_PALE = "#FBE7EB"
ROUGE_TEXTE = "#8E0B23"   # rouge foncé lisible sur fond pâle (contraste AA)

ENCRE = "#1C1F1D"
ENCRE_2 = "#4A524D"
ENCRE_3 = "#5F6762"       # texte des sources : 5,9:1 sur blanc (AA)
SURFACE = "#FBFBF8"
CARTE = "#FFFFFF"
BORDURE = "#E2E5DF"
GRILLE = "#F0F1ED"
INACTIF = "#ECEEE9"       # territoire hors filtre
NON_RENSEIGNE = "#C9CCC6"

# ---------------------------------------------------------------- échelle de gravité (5 classes)
GRAVITE = ["#FFF6D5", "#FFCE00", "#E8892B", "#D21034", "#7A0A1E"]   # du meilleur au pire

# ---------------------------------------------------------------- typologie (exploratoire)
# Couleurs attribuées par rang de gravité du groupe (indice moyen croissant) :
# 1 = villes, 2 = meilleur groupe rural, 3 = intermédiaire, 4 = le plus défavorisé
COULEURS_GROUPES_PAR_RANG = ["#006A4E", "#6DBE8C", "#E0A800", "#D21034"]
SYMBOLES_GROUPES_PAR_RANG = ["circle", "square", "triangle-up", "diamond"]

# ---------------------------------------------------------------- dimensions de l'indice
DIMENSIONS = {
    "dim_eloignement": ("Éloignement", "#006A4E"),
    "dim_capacite": ("Capacité (habitants par centre et par agent)", "#4A5560"),
    "dim_electricite": ("Électricité (habitants loin du réseau)", "#E0A800"),
}

# ---------------------------------------------------------------- classes de la carte
# bornes (4 seuils -> 5 classes) ; « inverse » : une valeur haute est une bonne situation
# niveau « pref » ou « canton » quand les ordres de grandeur diffèrent
CLASSES = {
    "indice_priorite": {"bornes": [20, 40, 60, 80], "unite": "", "titre": "Indice de priorité (0 à 100)"},
    "part_hab_5km": {"bornes": [10, 20, 30, 40], "unite": " %", "titre": "Habitants à plus de 5 km (%)"},
    "part_hab_5km_geodata": {"bornes": [10, 20, 30, 40], "unite": " %", "titre": "Habitants à plus de 5 km, geodata (%)"},
    "pop_5km": {"bornes": {"canton": [500, 2000, 5000, 10000], "pref": [5000, 15000, 30000, 50000]}, "unite": "",
                "titre": "Habitants à plus de 5 km (nombre)"},
    "dist_route_med_km": {"bornes": [2.5, 5, 7.5, 10], "unite": " km", "titre": "Distance par la route (km)"},
    "dist_hopital_vol_med_km": {"bornes": [5, 10, 15, 20], "unite": " km", "titre": "Distance à l'hôpital (km)"},
    "hab_par_centre": {"bornes": [3000, 5000, 7500, 10000], "unite": "", "titre": "Habitants par centre de santé",
                       "manquant": "pire"},
    "hab_par_personnel": {"bornes": {"canton": [500, 1000, 1500, 2500], "pref": [500, 750, 1000, 1250]}, "unite": "",
                          "titre": "Habitants par agent de santé"},
    "pct_hab_reseau_bt": {"bornes": [5, 10, 20, 40], "unite": " %", "inverse": True,
                          "titre": "Habitants à moins de 50 m du réseau BT (%)"},
}


def fmt(x: float) -> str:
    """Nombre au format français, espace insécable fine pour les milliers."""
    if float(x).is_integer():
        return f"{int(x):,}".replace(",", " ")
    return f"{x:,.1f}".replace(",", " ").replace(".", ",")


def bornes(indicateur: str, niveau: str) -> list[float]:
    b = CLASSES[indicateur]["bornes"]
    return b[niveau] if isinstance(b, dict) else b


def classer(valeur, indicateur: str, niveau: str) -> int:
    """Classe 0 (meilleure) à 4 (pire) ; -1 si non renseigné."""
    conf = CLASSES[indicateur]
    if valeur is None or (isinstance(valeur, float) and math.isnan(valeur)):
        return 4 if conf.get("manquant") == "pire" else -1
    b = bornes(indicateur, niveau)
    k = sum(valeur >= s for s in b)
    return 4 - k if conf.get("inverse") else k


def libelles_classes(indicateur: str, niveau: str) -> list[str]:
    """Libellés des 5 classes, de la meilleure (0) à la pire (4)."""
    conf, b, u = CLASSES[indicateur], bornes(indicateur, niveau), CLASSES[indicateur]["unite"]
    croissant = [f"moins de {fmt(b[0])}{u}"] + [f"{fmt(b[i])} à {fmt(b[i + 1])}{u}" for i in range(3)] + [f"{fmt(b[3])}{u} et plus"]
    lib = croissant[::-1] if conf.get("inverse") else croissant
    if conf.get("manquant") == "pire":
        lib[4] += " ou aucun centre"
    return lib


def variables_css() -> str:
    """Bloc :root injecté dans la page : le CSS n'utilise que ces variables."""
    v = {
        "vert": VERT, "vert-fonce": VERT_FONCE, "vert-pale": VERT_PALE, "jaune": JAUNE, "rouge": ROUGE,
        "rouge-pale": ROUGE_PALE, "rouge-texte": ROUGE_TEXTE, "encre-1": ENCRE, "encre-2": ENCRE_2, "encre-3": ENCRE_3,
        "surface": SURFACE, "carte": CARTE, "bordure": BORDURE,
        **{f"gravite-{i}": c for i, c in enumerate(GRAVITE)},
        # composants Dash 4 (curseur, listes, cases) : vert au lieu du violet par défaut
        "Dash-Fill-Interactive-Strong": VERT, "Dash-Fill-Interactive-Weak": VERT_PALE,
        "Dash-Fill-Primary-Hover": VERT_PALE, "Dash-Fill-Primary-Active": VERT_PALE, "Dash-Text-Primary": VERT,
    }
    return ":root {" + "".join(f"--{k}: {c};" for k, c in v.items()) + "}"
