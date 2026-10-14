# -*- coding: utf-8 -*-
"""
engines/dxf_cleaner/models.py — Modèles de données et rapports d'exécution
==========================================================================
Définit la structure CleanReport et ses méthodes de génération de bilans
techniques et statistiques en Darija et français.
"""

import os
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any


@dataclass
class CleanReport:
    """Rapport d'exécution d'un fichier DXF cadastral."""
    input_path: str
    output_path: str = ""
    n_lines_repaired: int = 0
    near_zero_deleted: int = 0
    duplicates_deleted: int = 0
    annotation_deleted: int = 0
    bornes_moved: int = 0
    bornes_strict: Tuple[int, int, int] = (0, 0, 0)
    verborne_positioned: int = 0
    rotations_reset: int = 0
    crosses_deleted: int = 0
    dtls_filtered: int = 0
    frame_clipped: int = 0
    texts_centered: int = 0
    overlaps_resolved: int = 0
    texts_wrapped: int = 0
    trees_populated: int = 0
    riverains_from_sector: int = 0
    scale_advice: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    elapsed_seconds: float = 0.0
    parcel_area: float = 0.0
    drawing_scale: str = ""

    @property
    def ok(self) -> bool:
        """Indique si le fichier a été traité avec succès sans erreur."""
        return not self.error

    def summary_text(self) -> str:
        """ملخص إحصائي دقيق وتفصيلي بالعمليات المنجزة في البلان."""
        fname = os.path.basename(self.input_path)
        if not self.ok:
            return f"❌ خطأ في معالجة {fname}: {self.error}"

        parts = [f"✅ تم تنظيف وتصحيح: {fname}"]
        if self.parcel_area > 0:
            scale_str = f" (السلم: {self.drawing_scale})" if self.drawing_scale else ""
            parts.append(f"• مساحة البقعة: {self.parcel_area:,.2f} m²{scale_str}")
        if self.near_zero_deleted:
            parts.append(f"• الكيانات الشبحية المحذوفة: {self.near_zero_deleted}")
        if self.duplicates_deleted:
            parts.append(f"• النصوص المكررة المحذوفة: {self.duplicates_deleted}")
        if self.bornes_strict != (0, 0, 0):
            m, s, u = self.bornes_strict
            parts.append(f"• أنصاب Bxx: {m} منقولة، {s} مصغرة، {u} متطابقة")
        if self.verborne_positioned:
            parts.append(f"• أبعاد Verborne المنسقة: {self.verborne_positioned}")
        if self.crosses_deleted:
            parts.append(f"• صلبان الإحداثيات المحذوفة: {self.crosses_deleted}")
        if self.trees_populated:
            parts.append(f"• الأشجار المغروسة آلياً: {self.trees_populated} شجرة (نمط فلاحي منتظم)")
        if self.riverains_from_sector:
            parts.append(f"• الجيران المستخرجون من البلان العام: {self.riverains_from_sector} جار (شعبة/واد/تيتير/طريق/جيران)")
        if self.overlaps_resolved:
            parts.append(f"• حالات التراكب المحلولة: {self.overlaps_resolved}")
        if self.scale_advice and self.scale_advice.get("alert_darija"):
            parts.append(f"• {self.scale_advice['alert_darija']}")
        if self.elapsed_seconds > 0:
            parts.append(f"• مدة المعالجة: {self.elapsed_seconds:.2f}s")

        return "\n".join(parts)
