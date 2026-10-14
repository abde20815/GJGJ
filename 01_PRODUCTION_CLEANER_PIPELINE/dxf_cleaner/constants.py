# -*- coding: utf-8 -*-
"""
engines/dxf_cleaner/constants.py — Constantes et expressions régulières cadastrales ANCFCC
========================================================================================
Centralise les constantes de traitement parcellaire, les calques normalisés,
les expressions régulières de reconnaissance topographique et les paramètres par défaut.
"""

import re
from typing import Dict, Any, Tuple, Set

# Séquence officielle des 17 étapes de traitement cadastral (IFE Tools v4.0.7 & DAHBY PRO)
ETAPES_PARCELLAIRE: Tuple[str, ...] = (
    "Chargement du DXF",
    "Suppression entités quasi-nulles",
    "Détection géométrie de parcelle",
    "Détection cadre du plan",
    "Suppression textes en doublon",
    "Suppression textes d'annotation",
    "Déplacement noms de bornes",
    "Contrainte stricte des labels Bxx",
    "Positionnement textes verborne",
    "Réinitialisation rotation textes internes",
    "Suppression symboles croix",
    "Suppression des riverains",
    "Découpage au cadre",
    "Centrage textes sur lignes",
    "Gestion des chevauchements",
    "Forçage retour à la ligne",
    "Enregistrement",
)

# Calques de lignes doubles linéaires (voies, cours d'eau, limites mitoyennes)
DBL_LAYERS: Set[str] = {
    "SAGUIA", "SENTIER", "piste", "route", "MASREF", "limit", "CHAABA",
    "LE_BT", "masref", "seguia", "PISTE", "lemt", "saguia", "le_bt",
    "LEHT", "chaaba", "LIMITE", "SEGUIA", "LE_BT", "limite", "LE",
    "LIMIT", "leht", "sentier", "ROUTE"
}

# Regex pour identifier les textes associés aux doubles lignes
DBL_TEXT_RE: re.Pattern = re.compile(
    r"^(oued|seguia|saguia|sentier|piste|route|chaaba|masref|canal|berge|berm|haie|talus|lkhzaz|ounza|saguia\s+b[eé]ton|route\s+goudronn)",
    re.IGNORECASE
)

# Calques d'éléments linéaires pour calcul de dérive et accrochage
LINEAR_LAYERS: Set[str] = {
    "MASREF", "LEHT", "LE", "limite", "le_bt", "leht", "LEMT", "LIMIT",
    "ROUTE", "SENTIER", "route", "LIMITE", "lemt", "PISTE", "chaaba",
    "piste", "seguia", "sentier", "CHAABA", "limit", "masref"
}

# Regex pour identifier les désignations linéaires le long des limites
LINEAR_RE: re.Pattern = re.compile(
    r"^(oued|seguia|saguia|sentier|piste|route|chaaba|chaaба|masref|limit|saguia|canal|berge|berm|haie|talus)\b",
    re.IGNORECASE
)

# Regex pour identifier les textes de mise en page / cartouche hors emprise parcellaire
LAYOUT_RE: re.Pattern = re.compile(
    r"^(Propri|Situ[eé]|Titre|R[eé]quisition|Direction|ST\b|Echel|Plan|Limit|NORD|الشمال|Plle\s*[nN]|IFE|Mappe\s+de|Carte\s+topo|G[eé]om[eè]tre|Dessinateur|Contenance|superficie|Surface|Plan\s+[eé]tabli|Plan\s+Provisoire)",
    re.IGNORECASE
)

# Paramètres par défaut de l'algorithme de nettoyage
DEFAULT_OPTIONS: Dict[str, Any] = {
    "del_near_zero": True,
    "del_duplicates": True,
    "del_annotation": True,
    "move_bornes": True,
    "fix_bornes_strict": True,
    "allow_scale_down": True,
    "pos_verborne": True,
    "reset_rotation": True,
    "del_crosses": True,
    "clean_dtls": True,
    "clip_frame": True,
    "centre_texts": True,
    "add_lv_chemin": False,
    "resolve_overlaps": True,
    "force_wrap": True,
    "wrap_char_count": 15,
    "verborne_spacing": 5,
    "center_texts": [],
    "populate_trees": True,
    "use_sector_riverains": True,
    "sectors_dir": r"C:\Users\Admin\Downloads\SS",
    "sz_reference_path": r"C:\Users\Admin\Downloads\SS",
    "selected_sz": "AUTO",
    "sz_force_refresh": False,
    "use_rust": True,
    "reference_path": None,
    "use_reference": True,
}
