# -*- coding: utf-8 -*-
"""
engines/dxf_cleaner/borne_ops.py — Repositionnement strict et contrainte des bornes cadastrales
=============================================================================================
Module spécialisé dans le repositionnement optimal des labels de bornes (Bxx) :
  - Déplacement contraint à l'intérieur de la parcelle
  - Préservation des distances (déplacement maximal de 2.0 m vers le centroïde)
  - Évitement de chevauchement avec les autres bornes (Bounding Box R-Tree / Shapely)
  - Réduction d'échelle adaptative (95%, 90%, 85%) en cas d'encombrement géométrique
"""

import math
import re
import logging
from typing import Optional, Tuple, List, Dict

import ezdxf.bbox as _eb
from shapely.geometry import box as _box, Point as _Pt

logger = logging.getLogger("dxf_cleaner.borne_ops")


def fix_borne_positions_strict(
    msp,
    parcel,
    core_mod,
    allow_scale: bool = True,
    max_move: float = 2.0,
    min_scale: float = 0.85,
    orig_positions: Optional[dict] = None
) -> Tuple[int, int, int]:
    """
    Contrainte stricte des labels Bxx issue d'IFE Tools v4.0.7:
      - Point d'insertion ET bounding box entière strictement dans la parcelle
      - Sans chevauchement avec les autres bornes
      - Déplacement max 2.0 m vers le centroïde
      - Réduction d'échelle progressive (95%, 90%, 85%) si nécessaire
    """
    borne_re = re.compile(r"^B\d+", re.IGNORECASE)
    cache = core_mod._bbox_cache

    def _ins(e):
        return core_mod.get_insert(e)

    def _bbox_poly(e):
        cache.invalidate([e])
        raw = _eb.extents([e], cache=cache)
        if raw is None:
            return None
        return _box(raw.extmin.x, raw.extmin.y, raw.extmax.x, raw.extmax.y)

    def _translate_box(bp0, ix0, iy0, nx, ny):
        dx = nx - ix0
        dy = ny - iy0
        minx, miny, maxx, maxy = bp0.bounds
        return _box(minx + dx, miny + dy, maxx + dx, maxy + dy)

    def _entirely_inside(nx, ny, bp0, ix0, iy0):
        if not parcel.contains(_Pt(nx, ny)):
            return False
        return parcel.contains(_translate_box(bp0, ix0, iy0, nx, ny))

    bornes_info = []
    for e in msp:
        if e.dxftype() not in ["TEXT", "MTEXT"]:
            continue
        try:
            txt = core_mod.get_text_content(e)
        except Exception:
            continue
        if not borne_re.match(txt):
            continue
        try:
            if orig_positions and id(e) in orig_positions:
                _, x0, y0 = orig_positions[id(e)]
            else:
                x0, y0 = _ins(e)
            bornes_info.append((e, x0, y0))
        except Exception:
            continue

    if not bornes_info:
        return (0, 0, 0)

    bornes = [e for e, x0, y0 in bornes_info]
    # Précalculer les bboxes de toutes les bornes pour accélérer la détection de chevauchement
    borne_boxes: Dict[int, Optional[Any]] = {}
    for oe in bornes:
        try:
            borne_boxes[id(oe)] = _bbox_poly(oe)
        except Exception:
            borne_boxes[id(oe)] = None

    def _get_height(e):
        try:
            return e.dxf.height if e.dxftype() == "TEXT" else e.dxf.char_height
        except Exception:
            return None

    def _set_height(e, h):
        try:
            if e.dxftype() == "TEXT":
                e.dxf.height = h
            else:
                e.dxf.char_height = h
        except Exception:
            return None

    def _overlaps_others(e, nx, ny, bp0, ix0, iy0, other_boxes):
        tb = _translate_box(bp0, ix0, iy0, nx, ny)
        for ob in other_boxes:
            if ob is not None and tb.intersects(ob):
                return True
        return False

    def _candidates(ix0, iy0, max_d):
        cx0, cy0 = parcel.centroid.x, parcel.centroid.y
        ang_center = math.atan2(cy0 - iy0, cx0 - ix0)
        deltas_deg = [0, 20, -20, 40, -40, 60, -60, 80, -80, 100, -100, 120, -120, 140, -140, 160, -160, 180]
        angles = [ang_center + math.radians(d) for d in deltas_deg]
        cands = []
        dist = 0.1
        while dist <= max_d + 1e-09:
            for ang in angles:
                cands.append((dist * math.cos(ang), dist * math.sin(ang), dist))
            dist = round(dist + 0.1, 4)
        return cands

    def _best_position(e, ix0, iy0, max_d, other_boxes):
        bp0 = borne_boxes.get(id(e))
        if bp0 is None:
            bp0 = _bbox_poly(e)
            borne_boxes[id(e)] = bp0
        if bp0 is None:
            return (0.0, 0.0)
        if _entirely_inside(ix0, iy0, bp0, ix0, iy0) and not _overlaps_others(e, ix0, iy0, bp0, ix0, iy0, other_boxes):
            return (0.0, 0.0)
        for dx, dy, dist in _candidates(ix0, iy0, max_d):
            nx, ny = ix0 + dx, iy0 + dy
            if not _entirely_inside(nx, ny, bp0, ix0, iy0):
                continue
            if not _overlaps_others(e, nx, ny, bp0, ix0, iy0, other_boxes):
                return (dx, dy)
        return None

    moved = scaled = unchanged = 0
    for e, x0, y0 in bornes_info:
        core_mod.set_insert(e, x0, y0)
        cache.invalidate([e])
        borne_boxes[id(e)] = _bbox_poly(e)
        other_boxes = [b for eid, b in borne_boxes.items() if eid != id(e) and b is not None]

        result = _best_position(e, x0, y0, max_move, other_boxes)
        if result is not None:
            dx, dy = result
            if math.hypot(dx, dy) > 1e-06:
                core_mod.move_dxf_text(e, dx, dy)
                cache.invalidate([e])
                borne_boxes[id(e)] = _bbox_poly(e)
                moved += 1
        else:
            if allow_scale:
                h0 = _get_height(e)
                if h0 and h0 > 0:
                    placed = False
                    for factor in [0.95, 0.90, min_scale]:
                        _set_height(e, h0 * factor)
                        core_mod.set_insert(e, x0, y0)
                        cache.invalidate([e])
                        borne_boxes[id(e)] = _bbox_poly(e)
                        result = _best_position(e, x0, y0, max_move, other_boxes)
                        if result is not None:
                            dx, dy = result
                            if math.hypot(dx, dy) > 1e-06:
                                core_mod.move_dxf_text(e, dx, dy)
                                cache.invalidate([e])
                                borne_boxes[id(e)] = _bbox_poly(e)
                            scaled += 1
                            placed = True
                            break
                    if not placed:
                        _set_height(e, h0)
                        core_mod.set_insert(e, x0, y0)
                        cache.invalidate([e])
                        borne_boxes[id(e)] = _bbox_poly(e)
                        unchanged += 1
                else:
                    unchanged += 1
            else:
                unchanged += 1

    logger.info("fix_borne_positions_strict: %d déplacé(s), %d réduit(s), %d inchangé(s).", moved, scaled, unchanged)
    return (moved, scaled, unchanged)
