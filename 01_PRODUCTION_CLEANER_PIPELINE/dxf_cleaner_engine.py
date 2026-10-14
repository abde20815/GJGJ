# -*- coding: utf-8 -*-
"""
engines/dxf_cleaner_engine.py — Façade Rétro-Compatible de Traitement DXF Cadastre
==================================================================================
Fournit une façade transparente vers le package modulaire `engines.dxf_cleaner`.
Garantit une compatibilité ascendante à 100% avec tous les outils, scripts et tests
de DAHBY PRO SUITE qui importent directement `dxf_cleaner_engine`.
"""

from engines.dxf_cleaner import (
    ETAPES_PARCELLAIRE,
    DEFAULT_OPTIONS,
    CleanReport,
    find_reference_dxf,
    _encode_autocad_unicode,
    _apply_definitive_standards,
    fix_borne_positions_strict,
    clip_frame_texts_complement,
    clip_frame_lines_complement,
    align_twin_lines_texts,
    collect_linear_elements_for_overlap,
    correct_linear_text_drift,
    execute_pipeline,
    clean_file,
    clean_files_batch,
)

__all__ = [
    "ETAPES_PARCELLAIRE",
    "DEFAULT_OPTIONS",
    "CleanReport",
    "find_reference_dxf",
    "_encode_autocad_unicode",
    "_apply_definitive_standards",
    "fix_borne_positions_strict",
    "clip_frame_texts_complement",
    "clip_frame_lines_complement",
    "align_twin_lines_texts",
    "collect_linear_elements_for_overlap",
    "correct_linear_text_drift",
    "execute_pipeline",
    "clean_file",
    "clean_files_batch",
]