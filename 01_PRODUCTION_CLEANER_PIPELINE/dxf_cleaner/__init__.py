# -*- coding: utf-8 -*-
"""
engines/dxf_cleaner — Package Modulaire de Traitement et Nettoyage Cadastral ANCFCC
==================================================================================
Package découplé et extensible regroupant l'ensemble des modules d'ingénierie DXF :
  - constants : Constantes, calques et regex topographiques
  - models : Rapport d'audit CleanReport
  - reference : Moteur de recherche universelle des plans de référence DEF
  - standards : Encodage Unicode AutoCAD et normalisation des textes
  - borne_ops : Repositionnement et contraintes strictes des bornes Bxx
  - geometry_clipping : Découpage géométrique au cadre du plan
  - linear_centering : Traitement et centrage des lignes jumelles et désignations
  - pipeline : Orchestrateur du pipeline séquentiel des 17 étapes
  - batch : Exécuteur de fichiers uniques et par lots (multithreading / in-place)
"""

from engines.dxf_cleaner.constants import ETAPES_PARCELLAIRE, DEFAULT_OPTIONS
from engines.dxf_cleaner.models import CleanReport
from engines.dxf_cleaner.reference import find_reference_dxf
from engines.dxf_cleaner.standards import (
    _encode_autocad_unicode,
    _apply_definitive_standards,
)
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
from engines.dxf_cleaner.pipeline import execute_pipeline
from engines.dxf_cleaner.batch import clean_file, clean_files_batch

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
