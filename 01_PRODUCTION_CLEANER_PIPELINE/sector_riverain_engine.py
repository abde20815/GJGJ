# -*- coding: utf-8 -*-
"""
engines/sector_riverain_engine.py — Moteur Cadastral de Résolution des Riverains par Secteurs (SS)
==================================================================================================
Utilise les plans parcellaires d'ensemble par secteur (PLAN-TOT-SECTEUR dans C:\\Users\\Admin\\Downloads\\SS)
comme base de référence spatiale maîtresse (Marji3) pour :
1. Découvrir et positionner automatiquement les riverains réels (JIRAN) le long de chaque limite :
   - Parcelles voisines (Plle xxxx TC) et leurs limites rayonnantes sur calque 'parcelle'
   - Titres Fonciers et Réquisitions (T.xxxx/xx TC ou R.xxxx/xx TC)
   - Châaba (Chaâbat sur calque 0)
   - Pistes et Voies publiques (piste de 10 m / Route goudronnée de 15m)
   - Propriétaires nommés du calque riverain (Nom Prénom sur calque 0)
   - Bornes de rattachement extérieures (Bxxxx) et verbornes (v.Bxxxx)
2. Corriger et garantir le numéro de parcelle interne conforme (Plle {id} TC) et éliminer les faux labels (ex: Plle 255 TC).
"""
import os
import sys
import math
import logging
import re
from typing import Dict, List, Optional, Tuple, Any, Set
import shapely.geometry as sg
from shapely.ops import nearest_points, linemerge

import ezdxf
from engines import parcel_core as core

logger = logging.getLogger("sector_riverain_engine")


class SectorDatabase:
    """
    Base spatiale maîtresse chargeant et indexant les plans d'ensemble des Sous-Zones (SZ1 à SZ5).
    Supporte :
    1. Un dossier complet contenant les DXF des sous-zones (ex: C:\\Users\\Admin\\Downloads\\SS)
    2. Un fichier DXF unique d'une Sous-Zone spécifique (ex: PLAN-TOT-SECTEUR_...dxf)
    3. Rechargement dynamique (force_refresh) lors de modifications récentes du plan maître
    4. Filtrage par Sous-Zone (SZ1, SZ2, SZ3, SZ4, SZ5 ou Auto)
    """
    def __init__(
        self,
        sectors_dir: str = r"C:\Users\Admin\Downloads\SS",
        force_refresh: bool = False,
        selected_sz: Optional[str] = None
    ):
        self.sectors_dir = sectors_dir
        self.sectors_path = sectors_dir
        self.force_refresh = force_refresh
        self.selected_sz = selected_sz
        self.sectors_data: List[Dict[str, Any]] = []
        self._load_all_sectors()

    def _load_all_sectors(self):
        if not os.path.exists(self.sectors_dir):
            logger.warning("Chemin du référentiel Sous-Zone introuvable: %s", self.sectors_dir)
            return

        is_file = os.path.isfile(self.sectors_dir)
        base_dir = os.path.dirname(os.path.abspath(self.sectors_dir)) if is_file else self.sectors_dir

        cache_path = os.path.join(base_dir, ".sector_cache.pkl") if not is_file else None

        # Vérification du cache disque si non forcé
        if not self.force_refresh and cache_path and os.path.exists(cache_path):
            try:
                cache_mtime = os.path.getmtime(cache_path)
                dxf_files = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.lower().endswith(".dxf")]
                any_newer = any(os.path.getmtime(df) > cache_mtime for df in dxf_files)
                if not any_newer:
                    import pickle
                    with open(cache_path, "rb") as f:
                        all_data = pickle.load(f)
                    self.sectors_data = self._filter_by_sz(all_data, self.selected_sz)
                    logger.info("⚡ [CACHE HIT] Secteurs cadastraux chargés depuis le cache disque (%d secteur(s)).", len(self.sectors_data))
                    return
                else:
                    logger.info("🔄 [PLAN MODIFIÉ] Fichiers DXF du secteur plus récents que le cache. Re-synchronisation...")
            except Exception as ex:
                logger.warning("Cache des secteurs illisible, ré-indexation: %s", ex)

        # Indexation des fichiers
        if is_file:
            files_to_load = [self.sectors_dir]
        else:
            files_to_load = [os.path.join(base_dir, f) for f in sorted(os.listdir(base_dir)) if f.lower().endswith(".dxf")]

        logger.info("Chargement et indexation de %d plan(s) maître(s) Sous-Zone...", len(files_to_load))

        indexed = []
        for idx, fpath in enumerate(files_to_load, start=1):
            fn = os.path.basename(fpath)
            sz_tag = f"SZ{idx}"
            m_sz = re.search(r'SZ[_\s-]*(\d+)|Sous[_\s-]*Zone[_\s-]*(\d+)', fn, re.IGNORECASE)
            if m_sz:
                num = m_sz.group(1) or m_sz.group(2)
                sz_tag = f"SZ{int(num)}"

            try:
                doc = core.load_dxf(fpath)
                msp = doc.modelspace()
                s_data = self._index_single_sector(msp, fn)
                s_data["sz_tag"] = sz_tag
                s_data["filepath"] = fpath
                indexed.append(s_data)
                logger.info(
                    "[%s] Plan maître %s indexé : %d polygones parcelles, %d titres, %d chaabas, %d riverains.",
                    sz_tag, fn, len(s_data["parcel_polygons"]), len(s_data["titres"]),
                    len(s_data["chaabas"]), len(s_data["riverains"])
                )
            except Exception as ex:
                logger.error("Erreur lors du chargement du secteur %s: %s", fn, ex)

        if not is_file and indexed and cache_path:
            try:
                import pickle
                with open(cache_path, "wb") as f:
                    pickle.dump(indexed, f)
                logger.info("💾 Cache des secteurs cadastraux sauvegardé avec succès.")
            except Exception as ex:
                logger.warning("Impossible de sauvegarder le cache des secteurs: %s", ex)

        self.sectors_data = self._filter_by_sz(indexed, self.selected_sz)

    def _filter_by_sz(self, sectors: List[Dict[str, Any]], selected_sz: Optional[str]) -> List[Dict[str, Any]]:
        if not selected_sz or selected_sz.upper() in ("AUTO", "TOUT", "ALL", ""):
            return sectors
        clean_target = selected_sz.upper().replace(" ", "").replace("_", "").replace("-", "")
        m = re.search(r'(\d+)', clean_target)
        if m:
            target_num = m.group(1)
            filtered = [s for s in sectors if target_num in s.get("sz_tag", "") or f"SZ{target_num}" in s.get("sz_tag", "")]
            if filtered:
                return filtered
        return sectors

    def _index_single_sector(self, msp, filename: str) -> Dict[str, Any]:
        raw_polys = []
        raw_labels = []
        titres = []
        chaabas = []
        oueds = []
        pistes = []
        routes = []
        riverains = []
        bornes = []
        borne_blocks = {}
        limit_lines = []
        minx, miny, maxx, maxy = 1e9, 1e9, -1e9, -1e9

        for e in msp:
            t = e.dxftype()
            lay = e.dxf.layer.lower()

            if t in ("TEXT", "MTEXT"):
                try:
                    txt = core.get_text_content(e).strip()
                    if not txt:
                        continue
                    tx, ty = core.get_insert(e)
                    pt = sg.Point(tx, ty)

                    minx = min(minx, tx)
                    miny = min(miny, ty)
                    maxx = max(maxx, tx)
                    maxy = max(maxy, ty)

                    if "titre" in lay:
                        titres.append((pt, txt))
                    elif "chaaba" in lay:
                        chaabas.append((pt, txt))
                    elif "oued" in lay:
                        oueds.append((pt, txt))
                    elif "riverain" in lay:
                        riverains.append((pt, txt))
                    elif "piste" in lay:
                        pistes.append((pt, txt))
                    elif "route" in lay:
                        routes.append((pt, txt))
                    elif "plle" in lay or "parcelle" in lay:
                        raw_labels.append((pt, txt))
                    else:
                        clean_b = txt.replace("(", "").replace(")", "").replace("v.", "").strip().upper()
                        if "borne" in lay or (clean_b.startswith("B") and len(clean_b) > 1 and clean_b[1:].isdigit()):
                            bornes.append((pt, clean_b))
                except Exception:
                    pass

            elif t == "INSERT":
                try:
                    bname = getattr(e.dxf, "name", "")
                    if "borne" in bname.lower():
                        ins = getattr(e.dxf, "insert", None)
                        if ins:
                            borne_blocks[(round(ins.x, 2), round(ins.y, 2))] = bname
                except Exception:
                    pass

            elif t in ("LINE", "LWPOLYLINE"):
                pts = []
                is_closed = False
                if t == "LWPOLYLINE":
                    pts = list(e.get_points())
                    is_closed = getattr(e, "is_closed", False)
                else:
                    pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]

                if len(pts) >= 2:
                    coords = [(p[0], p[1]) for p in pts]
                    ls = sg.LineString(coords)
                    limit_lines.append((ls, lay, coords))
                    bx = ls.bounds
                    minx = min(minx, bx[0])
                    miny = min(miny, bx[1])
                    maxx = max(maxx, bx[2])
                    maxy = max(maxy, bx[3])

                    if "chaaba" in lay:
                        chaabas.append((ls, "Chaâbat"))
                    elif "oued" in lay:
                        oueds.append((ls, "Oued"))
                    elif "piste" in lay:
                        pistes.append((ls, "piste de 8 m"))
                    elif "route" in lay:
                        routes.append((ls, "Route goudronnée de 15m"))

                    if is_closed and len(pts) >= 3 and lay in ("plle", "parcelle"):
                        try:
                            poly = sg.Polygon(coords)
                            if poly.is_valid and poly.area > 5.0:
                                raw_polys.append(poly)
                        except Exception:
                            pass

        # Apparier les polygones parcellaires avec leurs labels de numéro
        parcel_polygons: List[Tuple[sg.Polygon, str]] = []
        for poly in raw_polys:
            matched_lbl = None
            min_dist = 1e9
            for lpt, ltxt in raw_labels:
                if poly.contains(lpt):
                    matched_lbl = ltxt
                    break
                d = poly.distance(lpt)
                if d < min_dist and d < 45.0:
                    min_dist = d
                    matched_lbl = ltxt
            if matched_lbl:
                clean_pid = re.sub(r'^[Pp]lle|^[Pp]', '', matched_lbl.strip()).strip()
                parcel_polygons.append((poly, clean_pid))

        bbox = sg.box(minx, miny, maxx, maxy) if minx < maxx else sg.box(0, 0, 0, 0)
        return {
            "filename": filename,
            "bbox": bbox,
            "parcel_polygons": parcel_polygons,
            "titres": titres,
            "chaabas": chaabas,
            "oueds": oueds,
            "pistes": pistes,
            "routes": routes,
            "riverains": riverains,
            "bornes": bornes,
            "borne_blocks": borne_blocks,
            "limit_lines": limit_lines,
        }

    def get_sector_for_parcel(self, parcel_poly: sg.Polygon, pid: str = "") -> Optional[Dict[str, Any]]:
        """Trouve le secteur contenant la parcelle."""
        if not parcel_poly or parcel_poly.is_empty:
            return None
        c = parcel_poly.centroid

        candidates = [s for s in self.sectors_data if s["bbox"].contains(c)]
        if not candidates:
            candidates = self.sectors_data
        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        if pid:
            base_p = re.sub(r'[-_]plan.*$', '', os.path.basename(pid), flags=re.IGNORECASE)
            clean_target = re.sub(r'^[Pp]lle|^[Pp]', '', base_p).strip()
            for s in candidates:
                for poly, spid in s["parcel_polygons"]:
                    if spid == clean_target and poly.distance(c) < 80.0:
                        return s

        best_sec = candidates[0]
        max_nearby = -1
        buf = parcel_poly.buffer(60.0)
        for s in candidates:
            cnt = sum(1 for poly, _ in s["parcel_polygons"] if buf.intersects(poly))
            if cnt > max_nearby:
                max_nearby = cnt
                best_sec = s

        return best_sec


def get_facing_segment_tangent(parcel_poly: sg.Polygon, pt: sg.Point) -> Tuple[float, float]:
    """
    Calcule le vecteur directeur unitaire (ux, uy) du segment de limite de la parcelle
    le plus proche du point pt.
    Normalisé pour être lisible de gauche à droite / de bas en haut (Bottom/Right convention ANCFCC).
    """
    if not parcel_poly or parcel_poly.is_empty:
        return (1.0, 0.0)
    coords = list(parcel_poly.exterior.coords)
    best_seg = None
    min_d = 1e9
    for i in range(len(coords) - 1):
        seg = sg.LineString([coords[i], coords[i+1]])
        d = seg.distance(pt)
        if d < min_d:
            min_d = d
            best_seg = seg
    if not best_seg:
        return (1.0, 0.0)
    p0, p1 = best_seg.coords[0], best_seg.coords[1]
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    # Normalisation pour lisibilité (bottom/right): ux >= 0 ou si vertical uy > 0
    if ux < 0 or (abs(ux) < 1e-5 and uy < 0):
        ux, uy = -ux, -uy
    return (ux, uy)


def auto_populate_missing_riverains(
    msp,
    parcel_poly: sg.Polygon,
    sector_db: SectorDatabase,
    pid: str = "",
    scale: float = 1000.0,
    frame_poly: Optional[sg.Polygon] = None
) -> int:
    r"""
    Résolution complète et automatique des riverains cadastraux conforme ANCFCC (100% DEF) :
    1. Corrige le label interne de la parcelle (Plle {id} TC) et purge tout faux numéro.
    2. Identifie toutes les parcelles voisines dans le secteur dans un rayon de 25m :
       - Insère le texte riverain Plle {nbr} TC sur calque 0 orienté vers l'extérieur.
       - Insère les limites de parcelles et de voirie/chaaba sur calque 'DTLS'.
    3. Résout les propriétaires riverains nommés (calque 'riverain') avec expansion Héritiers et \PTC.
    4. Résout les titres fonciers (calque 'titres').
    5. Insère les éléments linéaires uniques (Chaâbat, piste de 8 m, Route goudronnée de 15m).
    6. Insère les bornes de rattachement extérieures (Bxxxx / (Bxxxx)) avec leurs blocs ANCFCC réels.
    7. Calcule et insère les verbornes (v.Bxxxx) aux extrémités des lignes rayonnantes.
    """
    if not parcel_poly or parcel_poly.is_empty:
        return 0

    if frame_poly is None:
        frame_poly = core.get_frame_polygon(msp)

    base_p = re.sub(r'[-_]plan.*$', '', os.path.basename(pid), flags=re.IGNORECASE)
    clean_pid = re.sub(r'^[Pp]lle|^[Pp]', '', base_p).strip()
    sec = sector_db.get_sector_for_parcel(parcel_poly, pid=pid)
    if not sec:
        return 0

    added_count = 0
    text_height = 2.0 * (scale / 1000.0)
    borne_text_height = 1.75 * (scale / 1000.0)

    # Identifier les vrais voisins du secteur (< 25m)
    valid_neighbor_pids = set()
    nearby_neighbors = []
    for p_nbr, nbr_pid in sec.get("parcel_polygons", []):
        if nbr_pid != clean_pid:
            d = parcel_poly.distance(p_nbr)
            if d <= 25.0:
                valid_neighbor_pids.add(nbr_pid)
                nearby_neighbors.append((p_nbr, nbr_pid, d))

    # 1. Nettoyer les faux labels internes uniquement (ne jamais détruire les riverains réels)
    for e in list(msp):
        if e.dxftype() in ("TEXT", "MTEXT"):
            try:
                t = core.get_text_content(e).strip()
                tx, ty = core.get_insert(e)
                pt = sg.Point(tx, ty)
                if re.search(r"\b\d+\b", t) and ("plle" in t.lower() or "p" in t.lower()):
                    found_nums = re.findall(r"\b\d+\b", t)
                    if parcel_poly.buffer(3.0).contains(pt):
                        if clean_pid and clean_pid not in found_nums:
                            e.destroy()
            except Exception:
                pass

    # Vérifier si TC ou Plle {clean_pid} TC existe à l'intérieur
    has_internal_pid = False
    for e in msp:
        if e.dxftype() in ("TEXT", "MTEXT"):
            try:
                t = core.get_text_content(e).strip()
                tx, ty = core.get_insert(e)
                if parcel_poly.contains(sg.Point(tx, ty)):
                    if "tc" in t.lower() or (clean_pid and clean_pid in t):
                        has_internal_pid = True
                        break
            except Exception:
                pass

    if not has_internal_pid and clean_pid:
        c = parcel_poly.centroid
        msp.add_mtext(
            f"Plle {clean_pid}\\PTC",
            dxfattribs={"layer": "0", "char_height": text_height, "insert": (c.x, c.y, 0.0)}
        )
        added_count += 1

    # 2. Relever les textes et bornes existants
    existing_texts = []
    existing_borne_names: Set[str] = set()
    for e in list(msp):
        if e.dxftype() in ("TEXT", "MTEXT"):
            try:
                t = core.get_text_content(e).strip()
                existing_texts.append(t)
                bt = t.replace("(", "").replace(")", "").replace("v.", "").strip().upper()
                if bt.startswith("B"):
                    existing_borne_names.add(bt)
            except Exception:
                pass

    # 3. Résolution des parcelles voisines (Jiran) dans le secteur (< 25m)
    neighbor_frontage_endpoints = []
    for p_nbr, nbr_pid, d in nearby_neighbors:
        lbl = f"Plle {nbr_pid}\\PTC"
        # Calculer la façade faisant face au voisin pour un placement centré et rigoureux
        facing_frontage = parcel_poly.boundary.intersection(p_nbr.buffer(max(12.0, d + 4.0)))
        if not facing_frontage.is_empty:
            f_mid = facing_frontage.centroid
            pt_poly, pt_nbr = nearest_points(f_mid, p_nbr)
        else:
            pt_poly, pt_nbr = nearest_points(parcel_poly, p_nbr)

        dx = pt_nbr.x - pt_poly.x
        dy = pt_nbr.y - pt_poly.y
        L = math.hypot(dx, dy)
        if L > 0.01:
            ux, uy = dx / L, dy / L
        else:
            c_nbr = p_nbr.centroid
            c_p = parcel_poly.centroid
            dx2, dy2 = c_nbr.x - c_p.x, c_nbr.y - c_p.y
            L2 = math.hypot(dx2, dy2) or 1.0
            ux, uy = dx2 / L2, dy2 / L2

        offset = max(18.0, min(30.0, d + 14.0))
        lx = pt_poly.x + ux * offset
        ly = pt_poly.y + uy * offset
        if frame_poly and not frame_poly.buffer(-4.0).contains(sg.Point(lx, ly)):
            np_in, _ = nearest_points(frame_poly.buffer(-4.0), sg.Point(lx, ly))
            lx, ly = np_in.x, np_in.y

        tan_ux, tan_uy = get_facing_segment_tangent(parcel_poly, sg.Point(lx, ly))

        # Vérifier si un label pour ce voisin existe déjà
        matched_ent = None
        for e in list(msp):
            if e.dxftype() in ("TEXT", "MTEXT"):
                t_chk = core.get_text_content(e).strip()
                if (f"plle {nbr_pid}" in t_chk.lower() or f"p{nbr_pid}" in t_chk.lower()) and nbr_pid != clean_pid:
                    matched_ent = e
                    break

        if matched_ent:
            # Repositionner et orienter parallèlement à la limite cadastrale
            ex, ey = core.get_insert(matched_ent)
            is_near_borne = any(math.hypot(ex - bx, ey - by) < 8.0 for bx, by in sec.get("borne_blocks", {}).keys())
            if is_near_borne or math.hypot(ex - lx, ey - ly) > 25.0:
                matched_ent.dxf.insert = (lx, ly, 0.0)
            if hasattr(matched_ent.dxf, "text_direction"):
                matched_ent.dxf.text_direction = (tan_ux, tan_uy, 0.0)
            if hasattr(matched_ent.dxf, "rotation"):
                matched_ent.dxf.rotation = 0.0
            logger.info("🔄 Voisin repositionné et orienté sur façade : Plle %s TC à (%.1f, %.1f) dir=(%.3f, %.3f)", nbr_pid, lx, ly, tan_ux, tan_uy)
        else:
            msp.add_mtext(
                lbl,
                dxfattribs={
                    "layer": "0",
                    "char_height": text_height,
                    "insert": (lx, ly, 0.0),
                    "text_direction": (tan_ux, tan_uy, 0.0),
                }
            )
            existing_texts.append(lbl)
            added_count += 1
            logger.info("➕ Voisin ajouté orienté : Plle %s TC à (%.1f, %.1f) dir=(%.3f, %.3f)", nbr_pid, lx, ly, tan_ux, tan_uy)

    # 4. Import des polylignes limites du secteur (chaaba, oued, piste, route, l.e) sur DTLS/L.E
    # Règle d'or ANCFCC: Ne JAMAIS importer de polygone fermé de voisin (ring) sur DTLS
    if frame_poly:
        for ls, lay, coords in sec.get("limit_lines", []):
            lay_l = lay.lower()
            if lay_l in ("chaaba", "oued", "piste", "route", "l.e"):
                if ls.is_ring:
                    continue
                # Ignorer les lignes quasi-identiques à la limite de la parcelle
                coords_on_bnd = sum(1 for p in coords if parcel_poly.boundary.distance(sg.Point(p)) < 0.2)
                if len(coords) > 2 and (coords_on_bnd / len(coords)) > 0.85:
                    continue
                d = parcel_poly.distance(ls)
                if d <= 25.0:
                    clipped_ls = ls.intersection(frame_poly)
                    if not clipped_ls.is_empty:
                        geoms = [clipped_ls] if isinstance(clipped_ls, sg.LineString) else getattr(clipped_ls, "geoms", [])
                        for g in geoms:
                            if isinstance(g, sg.LineString) and g.length >= 2.0:
                                try:
                                    target_lay = "L.E" if lay_l == "l.e" else "DTLS"
                                    g_coords = list(g.coords)
                                    msp.add_lwpolyline(g_coords, dxfattribs={"layer": target_lay})
                                    neighbor_frontage_endpoints.append((g_coords[0], g_coords[-1]))
                                    added_count += 1
                                except Exception:
                                    pass

    # 5. Segments de limite reliant directement un sommet de parcelle à une borne extérieure ou limite naturelle
    connecting_lines = []
    seen_conn_segs = set()
    ext_borne_pts = [sg.Point(float(bx), float(by)) for bx, by in sec.get("borne_blocks", {}).keys()]
    chaaba_geoms = [geom for geom, _ in sec.get("chaabas", [])]

    for ls, lay, coords in sec.get("limit_lines", []):
        for i in range(len(coords) - 1):
            p0, p1 = coords[i], coords[i+1]
            pt0 = sg.Point(float(p0[0]), float(p0[1]))
            pt1 = sg.Point(float(p1[0]), float(p1[1]))
            d0 = parcel_poly.distance(pt0)
            d1 = parcel_poly.distance(pt1)
            touches = (d0 < 0.2 and 0.5 < d1 <= 20.0) or (d1 < 0.2 and 0.5 < d0 <= 20.0)
            if touches:
                out_pt = pt1 if d0 < 0.2 else pt0
                is_to_ext_borne = any(out_pt.distance(bpt) < 1.0 for bpt in ext_borne_pts)
                is_to_chaaba = any(out_pt.distance(c_geom) < 1.0 for c_geom in chaaba_geoms)
                if is_to_ext_borne or is_to_chaaba:
                    key_seg = (min((p0[0], p0[1]), (p1[0], p1[1])), max((p0[0], p0[1]), (p1[0], p1[1])))
                    key_seg_round = ((round(key_seg[0][0], 1), round(key_seg[0][1], 1)), (round(key_seg[1][0], 1), round(key_seg[1][1], 1)))
                    if key_seg_round not in seen_conn_segs:
                        seen_conn_segs.add(key_seg_round)
                        target_lay = "DTLS" if is_to_ext_borne else "Chaaba"
                        seg = sg.LineString([p0, p1])
                        try:
                            msp.add_line((p0[0], p0[1], 0.0), (p1[0], p1[1], 0.0), dxfattribs={"layer": target_lay})
                            connecting_lines.append(seg)
                            added_count += 1
                        except Exception:
                            pass

    # 6. Bornes extérieures de rattachement (Bxxxx / (Bxxxx)) avec leurs blocs réels
    borne_blocks_dict = sec.get("borne_blocks", {})
    for (bx, by), blk_name in borne_blocks_dict.items():
        bpt = sg.Point(float(bx), float(by))
        d = parcel_poly.distance(bpt)
        max_borne_d = min(25.0, max(15.0, 15.0 * (scale / 1000.0)))
        if 0.5 < d <= max_borne_d and not parcel_poly.contains(bpt):
            matched_bname = None
            for b_t_pt, b_t_name in sec.get("bornes", []):
                if math.hypot(b_t_pt.x - bx, b_t_pt.y - by) < 4.0:
                    matched_bname = b_t_name
                    break
            if not matched_bname:
                continue
            clean_b = matched_bname.replace("(", "").replace(")", "").replace("v.", "").strip().upper()

            # Est-ce que cette borne est connectée par une ligne à la parcelle ?
            is_connected = any(seg.distance(bpt) < 0.5 for seg in connecting_lines)
            lbl = clean_b if is_connected else f"({clean_b})"

            # Vérifier si un bloc existe déjà pour cette borne
            has_blk = any(
                be.dxftype() == "INSERT" and math.hypot(be.dxf.insert.x - bx, be.dxf.insert.y - by) < 1.0
                for be in msp
            )
            if not has_blk:
                try:
                    msp.add_blockref(blk_name, insert=(bx, by, 0.0), dxfattribs={"layer": "bornes"})
                except Exception:
                    pass

            # Calcul de la position optimale de l'étiquette
            ins_x, ins_y = None, None
            if is_connected:
                # SE quadrant: angle ~330 deg, radius 7.5m (dégagé de la ligne de rattachement)
                ins_x = bx + 7.5 * math.cos(math.radians(330))
                ins_y = by + 7.5 * math.sin(math.radians(330))
            else:
                # Recherche de l'angle qui maximise la distance aux bornes internes et au coin
                best_score = -1e9
                for r_dist in [12.0, 15.0, 18.0]:
                    for ang in [245, 225, 270, 315, 0, 135, 180]:
                        rad = math.radians(ang)
                        cx = bx + r_dist * math.cos(rad)
                        cy = by + r_dist * math.sin(rad)
                        cpt = sg.Point(cx, cy)
                        if parcel_poly.buffer(2.0).contains(cpt):
                            continue
                        if frame_poly and not frame_poly.buffer(-2.0).contains(cpt):
                            continue
                        min_b_dist = min([parcel_poly.distance(cpt)] + [math.hypot(cx - obx, cy - oby) for obx, oby in sec.get("borne_blocks", {}).keys() if (obx, oby) != (bx, by)])
                        if min_b_dist < 6.0:
                            continue
                        score = min_b_dist - abs(r_dist - 16.0) * 0.2
                        if score > best_score:
                            best_score = score
                            ins_x, ins_y = cx, cy

            if ins_x is None:
                ins_x, ins_y = bx + 5.0, by + 5.0

            # Vérifier si l'étiquette existe déjà dans le dessin
            existing_ent = None
            for e in list(msp):
                if e.dxftype() in ("TEXT", "MTEXT"):
                    t_val = core.get_text_content(e).replace("(", "").replace(")", "").strip().upper()
                    if t_val == clean_b:
                        existing_ent = e
                        break

            if existing_ent:
                # Mettre à jour le texte (enlever parenthèses si connecté) et repositionner
                if hasattr(existing_ent, "text"):
                    existing_ent.text = lbl
                else:
                    existing_ent.dxf.text = lbl
                existing_ent.dxf.insert = (ins_x, ins_y, 0.0)
                if hasattr(existing_ent.dxf, "text_direction"):
                    existing_ent.dxf.text_direction = (1.0, 0.0, 0.0)
                if hasattr(existing_ent.dxf, "rotation"):
                    existing_ent.dxf.rotation = 0.0
                logger.info("🔄 Borne extérieure mise à jour : '%s' à (%.1f, %.1f)", lbl, ins_x, ins_y)
            else:
                msp.add_mtext(
                    lbl,
                    dxfattribs={
                        "layer": "0",
                        "char_height": borne_text_height,
                        "insert": (ins_x, ins_y, 0.0),
                        "text_direction": (1.0, 0.0, 0.0),
                    }
                )
                existing_borne_names.add(clean_b)
                added_count += 1
                logger.info("➕ Borne extérieure ajoutée : '%s' (%s) à (%.1f, %.1f)", lbl, blk_name, ins_x, ins_y)

    # 7. Verbornes (v.Bxxxx) : étiquetage précis aux extrémités de façade des parcelles voisines
    existing_vb_inserts = []
    for e in list(msp):
        if e.dxftype() in ("TEXT", "MTEXT") and core.get_text_content(e).strip().lower().startswith("v."):
            existing_vb_inserts.append(core.get_insert(e)[:2])

    seen_vb_endpoints = set()
    for ep_start, ep_end in neighbor_frontage_endpoints:
        for pt_end in (ep_start, ep_end):
            # Ne pas ajouter si déjà couvert par une verborne existante dans un rayon de 25m
            if any(math.hypot(pt_end[0] - vx, pt_end[1] - vy) < 25.0 for vx, vy in existing_vb_inserts):
                continue
            # Règle ANCFCC: Ne JAMAIS placer de verborne (v.Bxxxx) à proximité d'une borne déjà tracée sur le plan
            if any(math.hypot(pt_end[0] - bx, pt_end[1] - by) < 18.0 for bx, by in sec.get("borne_blocks", {}).keys()):
                continue
            if any(math.hypot(pt_end[0] - be.dxf.insert.x, pt_end[1] - be.dxf.insert.y) < 18.0 for be in msp if be.dxftype() == "INSERT" and "borne" in getattr(be.dxf, "name", "").lower()):
                continue
            pt_obj = sg.Point(float(pt_end[0]), float(pt_end[1]))
            if parcel_poly.distance(pt_obj) > 2.0:
                key_end = (round(pt_end[0], 0), round(pt_end[1], 0))
                if key_end in seen_vb_endpoints:
                    continue

                best_vb = None
                # 1. Correspondance directe à l'extrémité
                for b_t_pt, b_t_name in sec.get("bornes", []):
                    if math.hypot(b_t_pt.x - pt_end[0], b_t_pt.y - pt_end[1]) < 6.0:
                        clean_vb = b_t_name.replace("(", "").replace(")", "").replace("v.", "").strip().upper()
                        if clean_vb not in existing_borne_names and parcel_poly.distance(b_t_pt) > 8.0:
                            best_vb = clean_vb
                            break

                # 2. Continuité le long de la ligne du secteur vers la borne d'angle
                if not best_vb:
                    for ls, lay, coords in sec.get("limit_lines", []):
                        if lay in ("plle", "riverain", "piste", "chaaba") and ls.distance(pt_obj) < 1.0:
                            closest_idx = min(range(len(coords)), key=lambda i: math.hypot(coords[i][0]-pt_end[0], coords[i][1]-pt_end[1]))
                            for step in (1, -1):
                                curr = closest_idx + step
                                while 0 <= curr < len(coords):
                                    c_pt = coords[curr]
                                    for b_t_pt, b_t_name in sec.get("bornes", []):
                                        if math.hypot(b_t_pt.x - c_pt[0], b_t_pt.y - c_pt[1]) < 6.0:
                                            clean_vb = b_t_name.replace("(", "").replace(")", "").replace("v.", "").strip().upper()
                                            if clean_vb not in existing_borne_names and parcel_poly.distance(b_t_pt) > 8.0:
                                                best_vb = clean_vb
                                                break
                                    if best_vb:
                                        break
                                    curr += step
                                if best_vb:
                                    break
                        if best_vb:
                            break

                if best_vb:
                    seen_vb_endpoints.add(key_end)
                    vb_lbl = f"v.{best_vb}"
                    # Trouver la ligne directrice la plus proche pour orienter la verborne
                    vb_tan_ux, vb_tan_uy = 1.0, 0.0
                    min_l_d = 1e9
                    for e_l in msp:
                        if e_l.dxftype() in ("LINE", "LWPOLYLINE") and getattr(e_l.dxf, "layer", "") in ("DTLS", "L.E", "Chaaba", "0"):
                            if e_l.dxftype() == "LINE":
                                l_seg = sg.LineString([(e_l.dxf.start.x, e_l.dxf.start.y), (e_l.dxf.end.x, e_l.dxf.end.y)])
                            else:
                                l_pts = [(p[0], p[1]) for p in e_l.get_points()]
                                if len(l_pts) >= 2:
                                    l_seg = min((sg.LineString([l_pts[i], l_pts[i+1]]) for i in range(len(l_pts)-1)), key=lambda s: s.distance(pt_obj))
                                else:
                                    continue
                            d_l = l_seg.distance(pt_obj)
                            if d_l < min_l_d:
                                min_l_d = d_l
                                p0, p1 = l_seg.coords[0], l_seg.coords[1]
                                ldx, ldy = p1[0] - p0[0], p1[1] - p0[1]
                                lL = math.hypot(ldx, ldy) or 1.0
                                nux, nuy = ldx / lL, ldy / lL
                                if nux < 0 or (abs(nux) < 1e-5 and nuy < 0):
                                    nux, nuy = -nux, -nuy
                                vb_tan_ux, vb_tan_uy = nux, nuy

                    # Vérifier si cette verborne existe déjà
                    existing_vb_ent = None
                    for e in list(msp):
                        if e.dxftype() in ("TEXT", "MTEXT"):
                            t_chk = core.get_text_content(e).strip()
                            if t_chk == vb_lbl or t_chk == f"v.{best_vb}":
                                existing_vb_ent = e
                                break

                    c_frame = frame_poly.centroid if frame_poly else parcel_poly.centroid
                    to_c_x = c_frame.x - pt_end[0]
                    to_c_y = c_frame.y - pt_end[1]
                    L_to_c = math.hypot(to_c_x, to_c_y) or 1.0
                    ins_x = pt_end[0] + (to_c_x / L_to_c) * 4.0
                    ins_y = pt_end[1] + (to_c_y / L_to_c) * 4.0

                    if existing_vb_ent:
                        existing_vb_ent.dxf.insert = (ins_x, ins_y, 0.0)
                        if hasattr(existing_vb_ent.dxf, "text_direction"):
                            existing_vb_ent.dxf.text_direction = (vb_tan_ux, vb_tan_uy, 0.0)
                        if hasattr(existing_vb_ent.dxf, "rotation"):
                            existing_vb_ent.dxf.rotation = 0.0
                    else:
                        msp.add_mtext(
                            vb_lbl,
                            dxfattribs={
                                "layer": "0",
                                "char_height": borne_text_height,
                                "insert": (ins_x, ins_y, 0.0),
                                "text_direction": (vb_tan_ux, vb_tan_uy, 0.0),
                            }
                        )
                        existing_texts.append(vb_lbl)
                        existing_borne_names.add(best_vb)
                        added_count += 1
                        logger.info("➕ Verborne rayonnante ajoutée : '%s' à (%.1f, %.1f) dir=(%.3f, %.3f)", vb_lbl, ins_x, ins_y, vb_tan_ux, vb_tan_uy)

    # 8. Propriétaires nommés (calque 'riverain') avec expansion Héritiers et \PTC
    def _norm_cmp(s: str) -> str:
        s = re.sub(r'\\P|\n|\bTC\b|\bT\.C\b', ' ', s, flags=re.IGNORECASE)
        return re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]', '', s).lower()

    max_search_d = min(55.0, max(35.0, 40.0 * (scale / 1000.0)))
    for pt, rtxt in sec.get("riverains", []):
        if not parcel_poly.contains(pt):
            d = parcel_poly.distance(pt)
            if 0.5 < d <= max_search_d:
                clean_r = rtxt.strip()
                clean_r = re.sub(r'^\bHert\b|\bHrts\b', 'Héritiers', clean_r, flags=re.IGNORECASE)
                is_natural = bool(re.match(r"^(Jbel|Oued|Chaaba|Chaâba|Châaba|Forêt|Foret)$", clean_r, re.IGNORECASE))
                if not is_natural and not clean_r.upper().endswith("TC"):
                    clean_r = f"{clean_r}\\PTC"
                clean_r_norm = _norm_cmp(clean_r)
                already_has_r = any(clean_r_norm == _norm_cmp(t) for t in existing_texts if len(_norm_cmp(t)) >= 3)

                ins_pt = pt
                if frame_poly and not frame_poly.buffer(-2.0).contains(pt):
                    np_f, _ = nearest_points(frame_poly.buffer(-5.0), pt)
                    ins_pt = np_f
                # S'assurer que le riverain est bien décollé de la parcelle (18-24m) pour clarté
                if parcel_poly.distance(ins_pt) > 30.0:
                    np_p, _ = nearest_points(parcel_poly, ins_pt)
                    v_dx, v_dy = ins_pt.x - np_p.x, ins_pt.y - np_p.y
                    v_l = math.hypot(v_dx, v_dy) or 1.0
                    ins_pt = sg.Point(np_p.x + (v_dx / v_l) * 20.0, np_p.y + (v_dy / v_l) * 20.0)

                tan_ux, tan_uy = get_facing_segment_tangent(parcel_poly, ins_pt)

                if not already_has_r:
                    msp.add_mtext(
                        clean_r,
                        dxfattribs={
                            "layer": "0",
                            "char_height": text_height,
                            "insert": (ins_pt.x, ins_pt.y, 0.0),
                            "text_direction": (tan_ux, tan_uy, 0.0),
                        }
                    )
                    existing_texts.append(clean_r)
                    added_count += 1
                    logger.info("➕ Riverain nommé ajouté : '%s' à (%.1f, %.1f) dir=(%.3f, %.3f)", clean_r, ins_pt.x, ins_pt.y, tan_ux, tan_uy)
                else:
                    # Mettre à jour l'orientation du riverain existant
                    for e in list(msp):
                        if e.dxftype() in ("TEXT", "MTEXT"):
                            t_chk = core.get_text_content(e)
                            if _norm_cmp(t_chk) == clean_r_norm:
                                e_ins = sg.Point(core.get_insert(e)[:2])
                                t_ux, t_uy = get_facing_segment_tangent(parcel_poly, e_ins)
                                if hasattr(e.dxf, "text_direction"):
                                    e.dxf.text_direction = (t_ux, t_uy, 0.0)
                                if hasattr(e.dxf, "rotation"):
                                    e.dxf.rotation = 0.0

    # 9. Titres fonciers
    for pt, ttxt in sec.get("titres", []):
        if not parcel_poly.contains(pt):
            d = parcel_poly.distance(pt)
            if 0.5 < d <= max_search_d:
                clean_t = ttxt.split("(")[0].strip()
                lbl_t = f"{clean_t}\\PTC" if not clean_t.upper().endswith("TC") else clean_t
                lbl_t_norm = _norm_cmp(clean_t)
                already_has_t = any(lbl_t_norm == _norm_cmp(t) for t in existing_texts if len(_norm_cmp(t)) >= 3)
                if not already_has_t:
                    ins_pt = pt
                    if frame_poly and not frame_poly.buffer(-2.0).contains(pt):
                        np_f, _ = nearest_points(frame_poly.buffer(-5.0), pt)
                        ins_pt = np_f
                    msp.add_mtext(lbl_t, dxfattribs={"layer": "0", "char_height": text_height, "insert": (ins_pt.x, ins_pt.y, 0.0)})
                    existing_texts.append(lbl_t)
                    added_count += 1
                    logger.info("➕ Titre ajouté : '%s' à (%.1f, %.1f)", clean_t, ins_pt.x, ins_pt.y)

    # 10. Châaba : positionnement au milieu du lit du cours d'eau avec rotation tangente
    seen_chaaba_pts = []
    for geom, _ in sec.get("chaabas", []):
        d = parcel_poly.distance(geom)
        if d < 25.0:
            clipped = geom.intersection(frame_poly) if frame_poly else geom
            if clipped.is_empty:
                continue
            geoms = [clipped] if isinstance(clipped, sg.LineString) else getattr(clipped, "geoms", [])
            for g in geoms:
                if isinstance(g, sg.LineString) and g.length >= 25.0:
                    mid = g.interpolate(0.5, normalized=True)
                    if any(math.hypot(mid.x - px, mid.y - py) < 45.0 for px, py in seen_chaaba_pts):
                        continue
                    if any(math.hypot(mid.x - bx, mid.y - by) < 10.0 for bx, by in sec.get("borne_blocks", {}).keys()):
                        continue
                    seen_chaaba_pts.append((mid.x, mid.y))
                    p_before = g.interpolate(0.48, normalized=True)
                    p_after = g.interpolate(0.52, normalized=True)
                    dx = p_after.x - p_before.x
                    dy = p_after.y - p_before.y
                    rot = math.degrees(math.atan2(dy, dx)) % 360.0
                    if 90.0 < rot <= 270.0:
                        rot = (rot + 180.0) % 360.0
                    msp.add_text("Chaâbat", dxfattribs={"layer": "0", "height": text_height, "rotation": rot, "insert": (mid.x, mid.y, 0.0)})
                    existing_texts.append("Chaâbat")
                    added_count += 1
                    logger.info("➕ Chaâbat ajoutée au milieu du cours d'eau à (%.1f, %.1f) rot=%.1f", mid.x, mid.y, rot)

    # 11. Piste : positionnement au milieu de l'emprise de voirie avec rotation tangente
    if not any("piste" in t.lower() for t in existing_texts):
        for geom, plbl in sec.get("pistes", []):
            d = parcel_poly.distance(geom)
            if d < 25.0:
                clipped = geom.intersection(frame_poly) if frame_poly else geom
                if clipped.is_empty:
                    continue
                geoms = [clipped] if isinstance(clipped, sg.LineString) else getattr(clipped, "geoms", [])
                for g in geoms:
                    if isinstance(g, sg.LineString) and g.length >= 20.0:
                        mid = g.interpolate(0.5, normalized=True)
                        if any(math.hypot(mid.x - bx, mid.y - by) < 10.0 for bx, by in sec.get("borne_blocks", {}).keys()):
                            continue
                        p_before = g.interpolate(0.48, normalized=True)
                        p_after = g.interpolate(0.52, normalized=True)
                        dx = p_after.x - p_before.x
                        dy = p_after.y - p_before.y
                        rot = math.degrees(math.atan2(dy, dx)) % 360.0
                        if 90.0 < rot <= 270.0:
                            rot = (rot + 180.0) % 360.0
                        pst_txt = "piste de 8 m"
                        msp.add_text(pst_txt, dxfattribs={"layer": "0", "height": text_height, "rotation": rot, "insert": (mid.x, mid.y, 0.0)})
                        existing_texts.append(pst_txt)
                        added_count += 1
                        logger.info("➕ Piste ajoutée au milieu du segment à (%.1f, %.1f) rot=%.1f", mid.x, mid.y, rot)
                        break
                if any("piste" in t.lower() for t in existing_texts):
                    break

    # 12. Route goudronnée
    if not any("route" in t.lower() for t in existing_texts):
        min_rt_d = 1e9
        best_rt_pt = None
        for geom, rlbl in sec.get("routes", []):
            d = parcel_poly.distance(geom)
            if d < min_rt_d and d < 20.0:
                min_rt_d = d
                p_poly, p_geo = nearest_points(parcel_poly, geom)
                best_rt_pt = p_geo
        if best_rt_pt:
            msp.add_text("Route goudronnée de 15m", dxfattribs={"layer": "0", "height": text_height, "insert": (best_rt_pt.x, best_rt_pt.y, 0.0)})
            existing_texts.append("Route goudronnée de 15m")
            added_count += 1

    return added_count


_GLOBAL_SECTOR_DB: Optional[SectorDatabase] = None

def get_sector_database(
    sectors_dir: str = r"C:\Users\Admin\Downloads\SS",
    force_refresh: bool = False,
    selected_sz: Optional[str] = None
) -> Optional[SectorDatabase]:
    """
    Charge et maintient en mémoire cache la base des secteurs / Sous-Zones.
    Supporte à la fois un dossier complet ou un fichier DXF unique de Sous-Zone.
    """
    global _GLOBAL_SECTOR_DB
    need_reload = (
        _GLOBAL_SECTOR_DB is None
        or _GLOBAL_SECTOR_DB.sectors_dir != sectors_dir
        or _GLOBAL_SECTOR_DB.selected_sz != selected_sz
        or force_refresh
    )
    if need_reload:
        if os.path.exists(sectors_dir):
            _GLOBAL_SECTOR_DB = SectorDatabase(
                sectors_dir=sectors_dir,
                force_refresh=force_refresh,
                selected_sz=selected_sz
            )
    return _GLOBAL_SECTOR_DB


def inspect_sz_reference(sectors_path: str, selected_sz: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspecte et retourne les statistiques du référentiel Sous-Zone pour l'interface UI.
    Permet à l'utilisateur de vérifier instantanément que le plan maître a été chargé
    et combien de parcelles et riverains y ont été trouvés.
    """
    if not os.path.exists(sectors_path):
        return {"status": "error", "message": f"المسار غير موجود: {sectors_path}"}

    try:
        db = SectorDatabase(sectors_dir=sectors_path, force_refresh=True, selected_sz=selected_sz)
        if not db.sectors_data:
            return {"status": "error", "message": "لم يتم العثور على أي مخططات DXF صالحة في المسار."}

        tot_parcels = sum(len(s.get("parcel_polygons", [])) for s in db.sectors_data)
        tot_titres = sum(len(s.get("titres", [])) for s in db.sectors_data)
        tot_riv = sum(len(s.get("riverains", [])) for s in db.sectors_data)
        tot_chaaba = sum(len(s.get("chaabas", [])) for s in db.sectors_data)

        details = []
        for s in db.sectors_data:
            details.append({
                "tag": s.get("sz_tag", "SZ"),
                "file": s.get("filename", ""),
                "parcels": len(s.get("parcel_polygons", [])),
                "titres": len(s.get("titres", [])),
                "riverains": len(s.get("riverains", []))
            })

        return {
            "status": "ok",
            "sectors_count": len(db.sectors_data),
            "total_parcels": tot_parcels,
            "total_titres": tot_titres,
            "total_riverains": tot_riv,
            "total_chaabas": tot_chaaba,
            "details": details
        }
    except Exception as exc:
        return {"status": "error", "message": f"خطأ أثناء فحص المخطط المرجعي: {exc}"}

