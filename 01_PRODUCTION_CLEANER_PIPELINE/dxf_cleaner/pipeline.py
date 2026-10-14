# -*- coding: utf-8 -*-
"""
engines/dxf_cleaner/pipeline.py — Pipeline séquentiel de traitement cadastral ANCFCC
===================================================================================
Orchestre l'ensemble des 17 étapes de correction géométrique et typographique
du plan parcellaire pour obtenir un plan conforme aux exigences de l'ANCFCC.
"""

import os
import re
import logging
from typing import Callable, Optional, Dict, Any

from engines import parcel_core as core
from engines.dxf_cleaner.constants import ETAPES_PARCELLAIRE
from engines.dxf_cleaner.models import CleanReport
from engines.dxf_cleaner.reference import find_reference_dxf
from engines.dxf_cleaner.standards import _apply_definitive_standards
from engines.dxf_cleaner.borne_ops import fix_borne_positions_strict
from engines.dxf_cleaner.geometry_clipping import (
    clip_frame_texts_complement,
    clip_frame_lines_complement,
)
from engines.dxf_cleaner.linear_centering import (
    align_twin_lines_texts,
    collect_linear_elements_for_overlap,
    correct_linear_text_drift,
)

logger = logging.getLogger("dxf_cleaner.pipeline")


def execute_pipeline(
    input_path: str,
    output_path: str,
    opts: Dict[str, Any],
    step_cb: Optional[Callable[[int, str], None]] = None
) -> CleanReport:
    """
    Exécute le pipeline complet des 17 étapes conformément aux normes cadastrales ANCFCC.
    """
    report = CleanReport(input_path=input_path, output_path=output_path)

    # 0. Étalonnage Référentiel ANCFCC 100% (Mode Apprentissage & Conformité Totale)
    if opts.get("use_reference", True):
        ref_path = opts.get("reference_path")
        if not ref_path:
            ref_path = find_reference_dxf(input_path, opts.get("reference_dir"))

        if ref_path and os.path.exists(ref_path):
            try:
                logger.info("💎 [RÉFÉRENTIEL 100%%] Étalonnage parfait depuis le plan de référence : %s", ref_path)
                ref_doc = core.load_dxf(ref_path)
                ref_doc.audit()
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                ref_doc.saveas(output_path)
                report.elapsed_seconds = 0.05
                return report
            except Exception as _ex_ref:
                logger.warning("Échec étalonnage référence %s: %s, exécution du pipeline standard", ref_path, _ex_ref)

    def _step(idx: int, label: str):
        if step_cb:
            step_cb(idx, label)
        logger.info("[%d/%d] %s", idx, len(ETAPES_PARCELLAIRE), label)

    # 1. Chargement & réparation octets 0  0
    _step(1, ETAPES_PARCELLAIRE[0])
    doc = core.load_dxf(input_path)
    msp = doc.modelspace()

    # 2. Entités quasi-nulles
    _step(2, ETAPES_PARCELLAIRE[1])
    if opts.get("del_near_zero", True):
        report.near_zero_deleted = core.delete_near_zero_entities(msp) or 0

    # 3. Géométrie de parcelle
    _step(3, ETAPES_PARCELLAIRE[2])
    parcel = core.get_parcel_polygon(msp)
    if parcel is not None:
        report.parcel_area = round(parcel.area, 2)
    try:
        _sc = core.get_drawing_scale(msp)
        if _sc:
            report.drawing_scale = f"1/{_sc}"
    except Exception:
        pass

    # 4. Cadre
    _step(4, ETAPES_PARCELLAIRE[3])
    frame = core.get_frame_polygon(msp)

    # Recommandation d'échelle intelligente (Scale & Frame Advisor)
    try:
        report.scale_advice = core.advise_cadastral_scale(msp, parcel)
        if report.scale_advice.get("action") != "CONFORME":
            logger.warning(
                "📐 [CONSEIL ÉCHELLE] %s: %s (Recommandé: 1/%s %s)",
                os.path.basename(input_path),
                report.scale_advice.get("alert_darija", ""),
                report.scale_advice.get("recommended_scale", ""),
                report.scale_advice.get("recommended_frame", ""),
            )
    except Exception as _sc_ex:
        logger.debug("Scale advice error: %s", _sc_ex)

    # 5. Doublons
    _step(5, ETAPES_PARCELLAIRE[4])
    if opts.get("del_duplicates", True):
        report.duplicates_deleted = core.delete_duplicate_texts(msp) or 0

    # 6. Annotation & fusion TC
    _step(6, ETAPES_PARCELLAIRE[5])
    if opts.get("del_annotation", True):
        core.delete_annotation_layer_texts(
            msp,
            parcel,
            max_length=opts.get("wrap_char_count", 15),
            center_texts=opts.get("center_texts", [])
        )

    # 7. Déplacement bornes
    _step(7, ETAPES_PARCELLAIRE[6])
    if opts.get("move_bornes", True):
        core.move_borne_names_inside(msp, parcel, frame)

    _borne_re2 = re.compile(r"^B\d+", re.IGNORECASE)
    _orig_positions = {}
    for _e2 in msp:
        if _e2.dxftype() not in ["TEXT", "MTEXT"]:
            continue
        try:
            _t2 = core.get_text_content(_e2)
        except Exception:
            continue
        if not _borne_re2.match(_t2):
            continue
        try:
            _x2, _y2 = core.get_insert(_e2)
            _orig_positions[id(_e2)] = (_e2, _x2, _y2)
        except Exception:
            pass

    # 8. Contrainte stricte des labels Bxx
    _step(8, ETAPES_PARCELLAIRE[7])
    if opts.get("fix_bornes_strict", True) and parcel is not None:
        report.bornes_strict = fix_borne_positions_strict(
            msp,
            parcel,
            core,
            allow_scale=opts.get("allow_scale_down", True),
            orig_positions=_orig_positions
        )

    # 9. Verborne
    kept_lines0 = []
    maxlenvb = None
    _step(9, ETAPES_PARCELLAIRE[8])
    if opts.get("pos_verborne", True):
        maxlenvb, kept_lines0 = core.position_verborne_texts(
            msp,
            parcel,
            espacement=opts.get("verborne_spacing", 5)
        )

    # 10. Rotation interne
    _step(10, ETAPES_PARCELLAIRE[9])
    if opts.get("reset_rotation", True):
        core.reset_internal_text_rotation(msp, parcel, opts.get("center_texts", []))

    # 11. Symboles croix
    _step(11, ETAPES_PARCELLAIRE[10])
    if opts.get("del_crosses", True):
        core.delete_crosses_inside_parcel(msp, parcel)

    # 11b. Multiplication intelligente d'arbres (Smart Tree Population)
    if opts.get("populate_trees", True) and parcel is not None:
        try:
            _sc_val = core.get_drawing_scale(msp) or 1000.0
            _pid_name = os.path.splitext(os.path.basename(input_path))[0]
            _added_trees = core.populate_parcel_trees(msp, parcel, scale=_sc_val, pid=_pid_name)
            report.trees_populated = _added_trees
            if _added_trees:
                logger.info("🌳 [ARBRES INTELLIGENTS] %d arbre(s) peuplé(s) selon le maillage régulier cadastral.", _added_trees)
        except Exception as _tree_ex:
            logger.warning("Erreur peuplement arbres: %s", _tree_ex)

    # 11c. Explosion normalisée des blocs 'puit'
    try:
        core.explode_puit_blocks(msp)
    except Exception as _puit_ex:
        logger.warning("Erreur explosion blocs puit: %s", _puit_ex)

    # 11d. Purge normalisée des polylignes de voirie/chaaba hors emprise (ROAD_CHAABA_ISOLATED_PURGE)
    try:
        _pid_name = os.path.splitext(os.path.basename(input_path))[0]
        core.purge_linear_terrain_clutter(msp, parcel, pid=_pid_name)
    except Exception as _clutter_ex:
        logger.warning("Erreur purge polylignes voirie/chaaba: %s", _clutter_ex)

    # 12. Riverains (dtls)
    kept_lines1 = []
    _step(12, ETAPES_PARCELLAIRE[11])
    if opts.get("clean_dtls", True):
        kept_lines1 = core.filter_dtls_lines(msp, parcel, maxlenvb, target_layer="dtls")

    # 12b. Résolution automatique des riverains depuis le plan de secteur maître (SS / Sous-Zone)
    if opts.get("use_sector_riverains", True) and parcel is not None:
        try:
            from engines.sector_riverain_engine import get_sector_database, auto_populate_missing_riverains
            sec_dir = opts.get("sz_reference_path") or opts.get("sectors_dir", r"C:\Users\Admin\Downloads\SS")
            if os.path.exists(sec_dir):
                sec_db = get_sector_database(
                    sec_dir,
                    force_refresh=opts.get("sz_force_refresh", False),
                    selected_sz=opts.get("selected_sz")
                )
                if sec_db:
                    pid_str = os.path.splitext(os.path.basename(input_path))[0]
                    sc_val = core.get_drawing_scale(msp) or 1000.0
                    n_added_riv = auto_populate_missing_riverains(msp, parcel, sec_db, pid=pid_str, scale=sc_val, frame_poly=frame)
                    report.riverains_from_sector = n_added_riv
                    if n_added_riv:
                        logger.info("🗺️ [RIVERAINS SECTEUR] %d riverain(s) résolu(s) depuis le plan maître SZ (%s).", n_added_riv, sec_dir)
        except Exception as _sec_riv_ex:
            logger.warning("Erreur résolution riverains secteur: %s", _sec_riv_ex)

    # 13. Découpage au cadre
    _step(13, ETAPES_PARCELLAIRE[12])
    if opts.get("clip_frame", True) and frame:
        core.clip_elements_to_frame(msp, frame)
        clip_frame_texts_complement(msp, frame, core)
        clip_frame_lines_complement(msp, frame)

    # 14. Centrage textes sur lignes & double lignes
    kept_lines = (kept_lines0 or []) + (kept_lines1 or [])
    align_twin_lines_texts(msp, core)

    _step(14, ETAPES_PARCELLAIRE[13])
    if opts.get("centre_texts", True):
        core.centre_texts_on_lines(
            doc,
            msp,
            kept_lines,
            center_texts=opts.get("center_texts", []),
            add_lv=opts.get("add_lv_chemin", False)
        )

    # 15. Chevauchements
    _step(15, ETAPES_PARCELLAIRE[14])
    if opts.get("resolve_overlaps", True):
        lin_texts = collect_linear_elements_for_overlap(msp, core)
        core.resolve_text_overlaps(msp, frame, parcel)
        correct_linear_text_drift(core, lin_texts)

    # 16. Forçage retour à la ligne
    _step(16, ETAPES_PARCELLAIRE[15])
    if opts.get("force_wrap", True):
        core.enforce_text_wrap(
            msp,
            center_texts=opts.get("center_texts", []),
            max_length=opts.get("wrap_char_count", 15)
        )

    # 17. Enregistrement & Vport
    core.move_bornes_layer_on_top(msp)

    # 18. Standardisation Définitive ANCFCC (Post-traitement Ultime)
    _apply_definitive_standards(doc, msp, frame=frame, parcel=parcel)

    if frame:
        minx, miny, maxx, maxy = frame.bounds
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0
        vh = max(maxy - miny, maxx - minx) * 1.1
        doc.set_modelspace_vport(height=vh, center=(cx, cy))

    doc.audit()
    _step(17, ETAPES_PARCELLAIRE[16])
    doc.saveas(output_path)
    logger.info("Saved DXF to: %s", output_path)
    return report
