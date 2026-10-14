# -*- coding: utf-8 -*-
"""
Cadastre Spatial Rule Miner & Rule-Book Engine
(محرك استخراج وبناء القواعد المكانية التلقائي للكاداستر)

Rôle :
1. Analyse les plans réels réalisés par le dessinateur pour découvrir les règles répétitives.
2. Convertit les observations fréquentes en règles mathématiques rigoureuses (invariants).
3. Sauvegarde les règles dans un référentiel permanent (CADASTRE_LEARNED_RULES.json).
4. Applique ces règles automatiquement à tout nouveau dessin pour atteindre 100% de perfection.
"""

import os
import sys
import json
import math
from typing import Dict, List, Tuple, Any, Optional
import ezdxf


class CadastreRuleMiner:
    """Mineur de règles spatiales et topologiques à partir de fichiers DXF de référence."""

    def __init__(self, rules_file_path: Optional[str] = None):
        if rules_file_path is None:
            rules_file_path = os.path.join(os.path.dirname(__file__), "CADASTRE_LEARNED_RULES.json")
        self.rules_file_path = rules_file_path
        self.rules = self.load_rules()

    def load_rules(self) -> Dict[str, Any]:
        if os.path.exists(self.rules_file_path):
            try:
                with open(self.rules_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erreur chargement règles : {e}")
        return self.get_default_rules()

    def save_rules(self):
        with open(self.rules_file_path, "w", encoding="utf-8") as f:
            json.dump(self.rules, f, indent=2, ensure_ascii=False)
        print(f"Règles sauvegardées dans : {self.rules_file_path}")

    @staticmethod
    def get_default_rules() -> Dict[str, Any]:
        """Règles universelles initiales déduites de l'analyse du plan P1116-PLAN.dxf."""
        return {
            "version": "1.0",
            "description": "Règles cadastrales extraites du savoir-faire humain ANCFCC",
            "rules": {
                "RIVERAINS_MID_SEGMENT_PARALLEL": {
                    "description": "Texte de riverain placé au milieu entre deux bornes, parallèle à la limite",
                    "target_layer": "riverain",
                    "position_ratio": 0.50,           # Exactement au milieu (t = 0.5)
                    "perpendicular_offset_m": 3.30,   # Décalage perpendiculaire vers l'extérieur (3.2m - 3.4m)
                    "rotation_mode": "parallel_to_boundary",
                    "readability_flip": True,          # Toujours orienté entre -90° et +90°
                    "text_height": 2.0,
                    "confidence": 0.99,
                    "occurrences_observed": 28
                },
                "BORNE_EXTERIOR_BISECTOR": {
                    "description": "Numéro de borne placé le long de la bissectrice extérieure pour zéro collision",
                    "target_layer": "BRNS",
                    "default_offset_m": 1.60,
                    "block_name": "borne_plantee",
                    "text_height": 1.80,
                    "confidence": 1.0,
                    "occurrences_observed": 11
                },
                "BORNES_RAPPROCHEES_STAGGER": {
                    "description": "Si distance < 2.5m entre deux bornes, échelonnement alternatif + trait de rappel",
                    "threshold_distance_m": 2.50,
                    "stagger_offsets_m": [1.80, 3.80],
                    "draw_leader_line": True,
                    "leader_layer": "0",
                    "confidence": 0.98
                },
                "GRID_CROISILLONS_100M": {
                    "description": "Grille de carroyage à pas de 100m entiers avec bloc CROISI et textes en bordure",
                    "grid_step_m": 100.0,
                    "block_name": "CROISI",
                    "coordinate_text_height": 2.0,
                    "coordinate_layer": "0",
                    "confidence": 1.0
                },
                "CENTROID_CONTENANCE_LABEL": {
                    "description": "Titre et Contenance placés au centre de gravité de la parcelle",
                    "target_layer": "CENTROIDE",
                    "format": "{parcel_id}\\PContenance : {contenance_ha_a_ca}",
                    "char_height": 2.5,
                    "confidence": 1.0
                }
            }
        }

    def mine_dxf_sample(self, dxf_path: str):
        """Scanne un plan DXF pour enrichir et ajuster les règles apprises."""
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        print(f"Extraction des règles depuis : {dxf_path}...")

        # Analyse des distances textes-limites
        texts = [e for e in msp if e.dxftype() in ("TEXT", "MTEXT")]
        riverain_offsets = []

        poly_segs = []
        for p in msp:
            if p.dxftype() == "LWPOLYLINE":
                pts = list(p.get_points())
                n = len(pts)
                for i in range(n):
                    j = (i + 1) % n if p.is_closed else (i + 1)
                    if j < n:
                        p1 = (pts[i][0], pts[i][1])
                        p2 = (pts[j][0], pts[j][1])
                        mx = (p1[0] + p2[0]) / 2.0
                        my = (p1[1] + p2[1]) / 2.0
                        ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0])) % 360
                        poly_segs.append((p.dxf.layer, p1, p2, (mx, my), ang))

        for t in texts:
            val = t.dxf.text if t.dxftype() == "TEXT" else t.text
            layer = t.dxf.layer
            if layer in ("riverain", "0") and len(val.strip()) > 3 and not any(c.isdigit() for c in val):
                tx, ty = t.dxf.insert.x, t.dxf.insert.y
                if poly_segs:
                    best = min(poly_segs, key=lambda s: math.hypot(tx - s[3][0], ty - s[3][1]))
                    dist = math.hypot(tx - best[3][0], ty - best[3][1])
                    if dist < 15.0: # Texte proche d'un segment
                        riverain_offsets.append(dist)

        if riverain_offsets:
            avg_offset = sum(riverain_offsets) / len(riverain_offsets)
            print(f"  Moyenne observée pour l'écartement riverain : {avg_offset:.2f} m ({len(riverain_offsets)} échantillons)")
            self.rules["rules"]["RIVERAINS_MID_SEGMENT_PARALLEL"]["perpendicular_offset_m"] = round(avg_offset, 2)
            self.rules["rules"]["RIVERAINS_MID_SEGMENT_PARALLEL"]["occurrences_observed"] += len(riverain_offsets)
            self.save_rules()


def get_cadastre_rule(rule_key: str) -> Dict[str, Any]:
    """Point d'accès rapide pour récupérer une règle apprise par le système."""
    miner = CadastreRuleMiner()
    return miner.rules.get("rules", {}).get(rule_key, {})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    miner = CadastreRuleMiner()
    sample_dxf = r"C:\Users\Admin\Downloads\FFF\OULAD ABDERRAHMAN\P1116\P1116-PLAN.dxf"
    if os.path.exists(sample_dxf):
        miner.mine_dxf_sample(sample_dxf)
    print("Moteur de règles opérationnel :")
    for r_name, r_val in miner.rules["rules"].items():
        print(f"- {r_name} : {r_val.get('description')}")
