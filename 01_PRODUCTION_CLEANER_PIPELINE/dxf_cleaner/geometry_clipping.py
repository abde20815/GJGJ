# -*- coding: utf-8 -*-
"""
engines/dxf_cleaner/geometry_clipping.py — Découpage géométrique au cadre du plan (Cadre)
========================================================================================
Assure que toutes les entités graphiques (textes, polylignes, éléments linéaires)
sont rigoureusement tronquées ou réinsérées à l'intérieur du cadre cadastral.
"""

import logging
from typing import Optional

import ezdxf.bbox as _ceb
import ezdxf.math as _em3
from shapely.geometry import box as _cbox, Point as _cPt, LineString as _LS3, MultiLineString

from engines.dxf_cleaner.constants import LAYOUT_RE

logger = logging.getLogger("dxf_cleaner.geometry_clipping")


def _is_layout_text(e, core_mod) -> bool:
    """Détermine si un texte appartient à la mise en page (cartouche, bordure, coordonnées)."""
    try:
        if core_mod._is_frame_label(e):
            return True
    except Exception:
        pass
    try:
        txt = core_mod.get_text_content(e)
    except Exception:
        return False
    if any("\u0600" <= c <= "\u06ff" for c in txt):
        return True
    if LAYOUT_RE.match(txt.strip()):
        return True
    _stripped = txt.strip().replace(" ", "").replace(".", "").replace(",", "")
    if _stripped.lstrip("-").isdigit() and len(_stripped) >= 5:
        return True
    return False


def clip_frame_texts_complement(msp, frame, core_mod) -> int:
    """Recadre les textes coupés par le cadre interne."""
    _ccache = core_mod._bbox_cache
    _frame_box = _cbox(*frame.bounds)
    _frame_inner = frame.buffer(-0.1)
    if _frame_inner.geom_type == "MultiPolygon":
        _frame_inner = max(_frame_inner.geoms, key=lambda g: g.area)

    _clip_moved = 0
    for _ce in list(msp):
        if _ce.dxftype() not in ["TEXT", "MTEXT"]:
            continue
        try:
            _ctx = core_mod.get_text_content(_ce)
        except Exception:
            continue
        if _is_layout_text(_ce, core_mod):
            continue
        try:
            _cx0, _cy0 = core_mod.get_insert(_ce)
        except Exception:
            continue
        _ccache.invalidate([_ce])
        _craw = _ceb.extents([_ce], cache=_ccache)
        if _craw is None:
            continue
        _cbbox = _cbox(_craw.extmin.x, _craw.extmin.y, _craw.extmax.x, _craw.extmax.y)
        if _frame_box.contains(_cbbox):
            continue
        if not _frame_inner.contains(_cPt(_cx0, _cy0)):
            continue
        _bminx, _bminy, _bmaxx, _bmaxy = _cbbox.bounds
        _fminx, _fminy, _fmaxx, _fmaxy = frame.bounds
        _ddx = _ddy = 0.0
        if _bminx < _fminx:
            _ddx = _fminx - _bminx + 0.05
        elif _bmaxx > _fmaxx:
            _ddx = _fmaxx - _bmaxx - 0.05
        if _bminy < _fminy:
            _ddy = _fminy - _bminy + 0.05
        elif _bmaxy > _fmaxy:
            _ddy = _fmaxy - _bmaxy - 0.05
        if abs(_ddx) < 1e-06 and abs(_ddy) < 1e-06:
            continue
        _nx0, _ny0 = _cx0 + _ddx, _cy0 + _ddy
        if not frame.contains(_cPt(_nx0, _ny0)):
            continue
        try:
            core_mod.move_dxf_text(_ce, _ddx, _ddy)
            _ccache.invalidate([_ce])
            _clip_moved += 1
        except Exception:
            pass

    if _clip_moved:
        logger.info("clip_frame complement: %d texte(s) recadrés.", _clip_moved)
    return _clip_moved


def clip_frame_lines_complement(msp, frame) -> int:
    """Tronque proprement les polylignes linéaires dépassant du cadre extérieur."""
    _fminx3, _fminy3, _fmaxx3, _fmaxy3 = frame.bounds
    _clip_inner3 = frame.buffer(-0.05)
    if _clip_inner3.geom_type == "MultiPolygon":
        _clip_inner3 = max(_clip_inner3.geoms, key=lambda g: g.area)

    _clipped_lin = 0

    def _pt_outside(x, y, margin=0.5):
        return x < _fminx3 - margin or x > _fmaxx3 + margin or y < _fminy3 - margin or y > _fmaxy3 + margin

    def _longest_ls3(geom):
        if geom is None or geom.is_empty:
            return None
        if geom.geom_type == "LineString":
            return geom if geom.length > 1e-09 else None
        parts = []
        if geom.geom_type == "MultiLineString":
            parts = list(geom.geoms)
        elif hasattr(geom, "geoms"):
            for g in geom.geoms:
                if g.geom_type == "LineString":
                    parts.append(g)
                elif g.geom_type == "MultiLineString":
                    parts.extend(g.geoms)
        parts = [g for g in parts if not g.is_empty and g.length > 1e-09]
        return max(parts, key=lambda g: g.length) if parts else None

    for _le in list(msp):
        _lt = _le.dxftype()
        if _lt == "LWPOLYLINE":
            _pts = list(_le.get_points())
            if len(_pts) < 2:
                continue
            _coords = [(_p[0], _p[1]) for _p in _pts]
            if not any(_pt_outside(x, y) for x, y in _coords):
                continue
            _seg = _LS3(_coords)
            _inter = _seg.intersection(_clip_inner3)
            if _inter.is_empty:
                continue
            _best = _longest_ls3(_inter)
            if _best is None:
                continue
            _new_coords = list(_best.coords)
            if len(_new_coords) < 2:
                continue
            _sw0 = _pts[0][2] if len(_pts[0]) > 2 else 0
            _ew0 = _pts[0][3] if len(_pts[0]) > 3 else 0
            _le.set_points([(_c[0], _c[1], _sw0, _ew0, 0) for _c in _new_coords])
            _clipped_lin += 1
        elif _lt == "POLYLINE":
            if getattr(_le, "is_3d_polyline", False) or getattr(_le, "is_polygon_mesh", False):
                continue
            _verts = list(_le.vertices)
            _coords = [(_v.dxf.location.x, _v.dxf.location.y) for _v in _verts]
            if len(_coords) < 2:
                continue
            if not any(_pt_outside(x, y) for x, y in _coords):
                continue
            _seg = _LS3(_coords)
            _inter = _seg.intersection(_clip_inner3)
            if _inter.is_empty:
                continue
            _best = _longest_ls3(_inter)
            if _best is None:
                continue
            _new_coords = list(_best.coords)
            if len(_new_coords) < 2:
                continue
            for _i, _nc in enumerate(_new_coords):
                if _i < len(_verts):
                    _verts[_i].dxf.location = _em3.Vec3(_nc[0], _nc[1], 0)
            _clipped_lin += 1

    if _clipped_lin:
        logger.info("clip_frame complement (lignes): %d recoupée(s).", _clipped_lin)
    return _clipped_lin
