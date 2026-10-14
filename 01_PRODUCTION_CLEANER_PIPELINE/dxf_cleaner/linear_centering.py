# -*- coding: utf-8 -*-
"""
engines/dxf_cleaner/linear_centering.py — Alignement et centrage sur lignes simples et jumelles
=============================================================================================
Module de traitement géométrique pour les désignations linéaires (Seguia, Oued, Piste, Route) :
  - Détection automatique des paires de lignes jumelles (twin lines)
  - Calcul de la médiane géométrique (midline) et projection du texte au centre
  - Prévention de la dérive excessive (drift correction) lors de la résolution de chevauchements
"""

import math
import logging
from typing import List, Tuple, Any

from shapely.geometry import LineString as _DLS, Point as _DPt
from engines.dxf_cleaner.constants import DBL_LAYERS, DBL_TEXT_RE, LINEAR_LAYERS, LINEAR_RE

logger = logging.getLogger("dxf_cleaner.linear_centering")


def _line_angle(ls: _DLS) -> float:
    c = ls.coords
    dx = c[-1][0] - c[0][0]
    dy = c[-1][1] - c[0][1]
    return math.atan2(dy, dx) % math.pi


def _lines_parallel(ls1: _DLS, ls2: _DLS, angle_tol: float = math.radians(20)) -> bool:
    da = abs(_line_angle(ls1) - _line_angle(ls2))
    if da > math.pi / 2:
        da = math.pi - da
    return da < angle_tol


def _lines_nearby(ls1: _DLS, ls2: _DLS, max_dist: float = 10.0) -> bool:
    return ls1.distance(ls2) < max_dist


def _midline(ls1: _DLS, ls2: _DLS) -> _DLS:
    n = max(10, int(ls1.length / 0.5))
    pts = []
    for i in range(n + 1):
        t = i / n
        p1 = ls1.interpolate(t, normalized=True)
        p2 = ls2.interpolate(ls2.project(p1), normalized=False)
        pts.append(((p1.x + p2.x) / 2, (p1.y + p2.y) / 2))
    if len(pts) >= 2:
        return _DLS(pts)
    return ls1


def align_twin_lines_texts(msp, core_mod) -> int:
    """Détecte les lignes jumelles et centre les étiquettes correspondantes sur la médiane."""
    try:
        dbl_lines = {}
        for dl in msp:
            dlt = dl.dxftype()
            dlayer = getattr(dl.dxf, "layer", "")
            if dlayer not in DBL_LAYERS:
                continue
            try:
                if dlt == "LINE":
                    s = dl.dxf.start
                    e_ = dl.dxf.end
                    dbl_lines.setdefault(dlayer, []).append((dl, _DLS([(s.x, s.y), (e_.x, e_.y)])))
                elif dlt in ("LWPOLYLINE", "POLYLINE"):
                    pts = [(p[0], p[1]) for p in dl.get_points()]
                    if len(pts) >= 2:
                        dbl_lines.setdefault(dlayer, []).append((dl, _DLS(pts)))
            except Exception:
                continue

        twin_pairs = []
        for layer, llist in dbl_lines.items():
            used = set()
            for i, (e1, ls1) in enumerate(llist):
                if i in used:
                    continue
                for j, (e2, ls2) in enumerate(llist):
                    if j <= i or j in used:
                        continue
                    if _lines_parallel(ls1, ls2) and _lines_nearby(ls1, ls2):
                        lsmid = _midline(ls1, ls2)
                        twin_pairs.append((lsmid, [e1, e2], ls1, ls2))
                        used.add(i)
                        used.add(j)
                        break

        dbl_done = 0
        for lsmid, line_ents, ls1, ls2 in twin_pairs:
            paired_texts = []
            for te in list(msp):
                if te.dxftype() not in ["TEXT", "MTEXT"]:
                    continue
                try:
                    tc = core_mod.get_text_content(te)
                except Exception:
                    continue
                if not DBL_TEXT_RE.match(tc.strip()):
                    continue
                try:
                    tx, ty = core_mod.get_insert(te)
                except Exception:
                    continue
                tpt = _DPt(tx, ty)
                d1 = ls1.distance(tpt)
                d2 = ls2.distance(tpt)
                dmin = min(d1, d2)
                if dmin < 8.0:
                    paired_texts.append((te, tc, tx, ty, dmin))

            if len(paired_texts) < 2:
                continue

            paired_texts.sort(key=lambda x: x[4])
            kept_text_ent = None
            seen_prefixes = set()
            to_del_txt = []
            for te, tc, tx, ty, td in paired_texts:
                prefix = tc.strip().lower()[:30]
                if prefix not in seen_prefixes:
                    seen_prefixes.add(prefix)
                    if kept_text_ent is None:
                        kept_text_ent = (te, tc, tx, ty)
                else:
                    to_del_txt.append(te)

            for te in to_del_txt:
                try:
                    if getattr(te, "is_alive", True):
                        te.destroy()
                except Exception:
                    continue

            if kept_text_ent is not None:
                te, tc, tx, ty = kept_text_ent
                if not getattr(te, "is_alive", True):
                    continue
                try:
                    tpt = _DPt(tx, ty)
                    t_on_mid = lsmid.project(tpt)
                    mid_pt = lsmid.interpolate(t_on_mid)
                    nmx, nmy = mid_pt.x, mid_pt.y
                    t_frac = t_on_mid / lsmid.length if lsmid.length > 0 else 0.5
                    t_frac = max(0.01, min(0.99, t_frac))
                    pt_a = lsmid.interpolate(t_frac - 0.01, normalized=True)
                    pt_b = lsmid.interpolate(t_frac + 0.01, normalized=True)
                    ang = math.atan2(pt_b.y - pt_a.y, pt_b.x - pt_a.x)
                    core_mod.set_insert(te, nmx, nmy)
                    try:
                        te.dxf.rotation = math.degrees(ang) % 360
                    except Exception:
                        pass
                    core_mod._bbox_cache.invalidate([te])
                    dbl_done += 1
                except Exception:
                    pass

        if dbl_done:
            logger.info("double_lines: %d label(s) centré(s) entre lignes jumelles.", dbl_done)
        return dbl_done
    except Exception as dbl_ex:
        logger.warning("double_lines: erreur non bloquante: %s", dbl_ex)
        return 0


def collect_linear_elements_for_overlap(msp, core_mod) -> List[Tuple[Any, float, float, Any, float]]:
    """Capture les positions et géométries des textes linéaires avant résolution des chevauchements."""
    lin_geoms = []
    for le in msp:
        if getattr(le.dxf, "layer", "") not in LINEAR_LAYERS:
            continue
        try:
            if le.dxftype() == "LINE":
                s = le.dxf.start
                e2 = le.dxf.end
                lin_geoms.append(_DLS([(s.x, s.y), (e2.x, e2.y)]))
            elif le.dxftype() in ["LWPOLYLINE", "POLYLINE"]:
                pts = [(p[0], p[1]) for p in le.get_points()]
                if len(pts) >= 2:
                    lin_geoms.append(_DLS(pts))
        except Exception:
            continue

    lin_texts = []
    for te in msp:
        if te.dxftype() not in ["TEXT", "MTEXT"]:
            continue
        try:
            tc = core_mod.get_text_content(te)
        except Exception:
            continue
        if not LINEAR_RE.match(tc):
            continue
        try:
            tx, ty = core_mod.get_insert(te)
        except Exception:
            continue
        tpt = _DPt(tx, ty)
        best_line = None
        best_d = float("inf")
        for lg in lin_geoms:
            d = lg.distance(tpt)
            if d < best_d:
                best_d = d
                best_line = lg
        lin_texts.append((te, tx, ty, best_line, best_d))
    return lin_texts


def correct_linear_text_drift(
    core_mod,
    lin_texts: List[Tuple[Any, float, float, Any, float]],
    max_drift: float = 5.0,
    side_offset: float = 0.5
) -> int:
    """Rétablit les textes linéaires qui ont dérivé trop loin de leur support géométrique."""
    n_corrected = 0
    for te, tx0, ty0, best_line, d0 in lin_texts:
        try:
            nx, ny = core_mod.get_insert(te)
        except Exception:
            continue
        drift = math.hypot(nx - tx0, ny - ty0)
        if drift <= max_drift:
            continue
        if best_line is not None:
            tpt_orig = _DPt(tx0, ty0)
            proj = best_line.interpolate(best_line.project(tpt_orig))
            pdx = tx0 - proj.x
            pdy = ty0 - proj.y
            plen = math.hypot(pdx, pdy) or 1.0
            off = max(d0, side_offset)
            rx = proj.x + pdx / plen * off
            ry = proj.y + pdy / plen * off
        else:
            rx, ry = tx0, ty0
        try:
            core_mod.set_insert(te, rx, ry)
            n_corrected += 1
        except Exception:
            pass
    return n_corrected
