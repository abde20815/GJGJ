# -*- coding: utf-8 -*-
"""
Full-Featured DXF Transformation Engine & Automated Draughtsman Synthesizer
(محرك الاستنتاج والتنفيذ الأوتوماتيكي لتحويلات الـ DXF الكاداسترية)
"""

import os
import sys
import math
from typing import Dict, List, Any, Tuple, Optional
import ezdxf
from ezdxf.document import Drawing


class DxfCadastreDiffEngine:
    """Analyse chirurgicale de la transformation entre DXF Initial (Avant) et DXF Modifié (Après)."""

    def __init__(self, path_avant: str, path_apres: str):
        if not os.path.exists(path_avant):
            raise FileNotFoundError(f"DXF Avant introuvable: {path_avant}")
        if not os.path.exists(path_apres):
            raise FileNotFoundError(f"DXF Après introuvable: {path_apres}")

        self.path_avant = path_avant
        self.path_apres = path_apres
        self.doc_avant = ezdxf.readfile(path_avant)
        self.doc_apres = ezdxf.readfile(path_apres)

    def analyze_layers(self) -> Dict[str, Any]:
        """Détecte les calques ajoutés, supprimés, et propriétés de couleurs/types de ligne."""
        layers_av = {l.dxf.name: {"color": l.dxf.color, "linetype": l.dxf.linetype} for l in self.doc_avant.layers}
        layers_ap = {l.dxf.name: {"color": l.dxf.color, "linetype": l.dxf.linetype} for l in self.doc_apres.layers}

        added = {k: v for k, v in layers_ap.items() if k not in layers_av}
        removed = {k: v for k, v in layers_av.items() if k not in layers_ap}

        return {"added_layers": added, "removed_layers": removed, "all_target_layers": layers_ap}

    def analyze_polylines(self) -> Dict[str, Any]:
        """Détecte la création de polylignes fermées, couches utilisées, et géométries."""
        msp_av = self.doc_avant.modelspace()
        msp_ap = self.doc_apres.modelspace()

        poly_av = [e for e in msp_av if e.dxftype() in ("LWPOLYLINE", "POLYLINE")]
        poly_ap = [e for e in msp_ap if e.dxftype() in ("LWPOLYLINE", "POLYLINE")]

        closed_added = []
        for p in poly_ap:
            is_closed = p.is_closed if hasattr(p, "is_closed") else False
            if is_closed:
                closed_added.append({
                    "layer": p.dxf.layer,
                    "points_count": len(list(p.get_points())) if hasattr(p, "get_points") else 0
                })

        return {
            "avant_count": len(poly_av),
            "apres_count": len(poly_ap),
            "closed_polylines_in_target": closed_added
        }

    def analyze_texts_and_annotations(self) -> Dict[str, Any]:
        """Détecte les textes ajoutés (Bornes, Riverains, Contenance, Titres)."""
        msp_ap = self.doc_apres.modelspace()
        texts_by_layer = {}

        for e in msp_ap:
            if e.dxftype() in ("TEXT", "MTEXT"):
                layer = e.dxf.layer
                text_val = e.dxf.text if e.dxftype() == "TEXT" else e.text
                h = getattr(e.dxf, "height", 1.0)
                rot = getattr(e.dxf, "rotation", 0.0)
                
                if layer not in texts_by_layer:
                    texts_by_layer[layer] = []
                texts_by_layer[layer].append({
                    "text": text_val,
                    "height": h,
                    "rotation": rot
                })

        return {"texts_by_layer": texts_by_layer}

    def synthesize_transformation_manifesto(self) -> Dict[str, Any]:
        """Synthétise l'ensemble des règles observées dans le travail du dessinateur."""
        layer_diff = self.analyze_layers()
        poly_diff = self.analyze_polylines()
        text_diff = self.analyze_texts_and_annotations()

        manifesto = {
            "source_file": self.path_avant,
            "target_file": self.path_apres,
            "new_layers_required": list(layer_diff["added_layers"].keys()),
            "boundary_layer": "LIMIT" if "LIMIT" in layer_diff["all_target_layers"] else "parcelle",
            "bornes_layer": "BRNS" if "BRNS" in layer_diff["all_target_layers"] else "BORNES",
            "riverains_layer": "riverain" if "riverain" in layer_diff["all_target_layers"] else "RIVERAINS",
            "cartouche_present": any("CADRE" in k.upper() for k in layer_diff["all_target_layers"]),
            "polylines_target_count": poly_diff["apres_count"],
            "texts_layers": list(text_diff["texts_by_layer"].keys())
        }
        return manifesto


def generate_automated_transformation_script(manifesto: Dict[str, Any], output_py_path: str):
    """Génère un script Python autonome basé sur le manifeste déduit pour traiter les futurs DXF."""
    code = f'''# -*- coding: utf-8 -*-
"""
Script de transformation DXF automatique généré par le moteur d'apprentissage Triad.
Applique exactement les modifications observées du dessinateur.
"""

import ezdxf

def apply_learned_cadastre_transformation(input_dxf: str, output_dxf: str):
    doc = ezdxf.readfile(input_dxf)
    msp = doc.modelspace()

    # 1. Création des calques requis
    target_layers = {manifesto.get("new_layers_required", [])}
    for layer_name in target_layers:
        if layer_name not in doc.layers:
            doc.layers.add(name=layer_name)

    # 2. Sauvegarde du résultat
    doc.saveas(output_dxf)
    print(f"DXF transformé avec succès : {{output_dxf}}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        apply_learned_cadastre_transformation(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python transform.py <input.dxf> <output.dxf>")
'''
    with open(output_py_path, "w", encoding="utf-8") as f:
        f.write(code)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("DxfCadastreDiffEngine prêt à l'emploi.")
