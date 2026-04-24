import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from dotenv import load_dotenv

from app.services.tubi_auto_params import compute_tubi_params
from app.services.tubi_mask_refiner import expand_paint_mask_with_edges, mask_to_regions, refine_inscription_mask_stats, refine_paint_mask_stats, regions_to_mask


def main() -> int:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
    db_path = os.path.join("data", "calligraphy.db")
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        pick_id = os.environ.get("TUBI_IMAGE_ID", "").strip()
        if pick_id:
            cur.execute(
                "select image_id, image_width, image_height, filepath, regions "
                "from tubi_analyses where image_id=?",
                (pick_id,),
            )
            row = cur.fetchone()
            if not row:
                print("image_id_not_found", pick_id)
                return 3
            rows = [row]
        else:
            cur.execute(
                "select image_id, image_width, image_height, filepath, regions "
                "from tubi_analyses where status='analyzed' and regions is not null"
            )
            rows = cur.fetchall()
    finally:
        con.close()

    if not rows:
        print("no_analyzed_rows")
        return 2

    if len(rows) == 1:
        image_id, w, h, fp, regions = rows[0]
    else:
        rows.sort(key=lambda r: int(r[1] or 0) * int(r[2] or 0))
        image_id, w, h, fp, regions = rows[0]
    w = int(w or 0)
    h = int(h or 0)
    if isinstance(regions, str):
        regions = json.loads(regions)
    regions = regions or {}

    try:
        paint_seed = regions_to_mask(regions.get("painting_regions") or [], w, h)
        insc_seed = regions_to_mask(regions.get("inscription_regions") or [], w, h)
        if cv2.countNonZero(paint_seed) > 0 and cv2.countNonZero(insc_seed) > 0:
            paint_norm = cv2.subtract(paint_seed, insc_seed)
            norm_regions = mask_to_regions(paint_norm)
            if norm_regions:
                regions["painting_regions"] = norm_regions
    except Exception:
        pass

    auto = compute_tubi_params(fp, w, h, regions)
    paint_auto = (auto or {}).get("paint") or {}
    insc_auto = (auto or {}).get("insc") or {}
    expand_auto = (auto or {}).get("expand") or {}
    seal_auto = (auto or {}).get("seal") or {}

    debug_dir = os.path.join("data", "tubi_debug", str(image_id))
    paint = refine_paint_mask_stats(
        image_path=fp,
        painting_regions=regions.get("painting_regions") or [],
        image_width=w,
        image_height=h,
        bg_sample_ratio=float(paint_auto.get("bg_sample_ratio", 0.06)),
        bg_deltae=float(paint_auto.get("bg_deltae", 12.0)),
        bg_grad_max=float(paint_auto.get("bg_grad_max", 8.0)),
        bg_s_max=float(paint_auto.get("bg_s_max", 0.0)),
        return_mask=True,
        debug_dir=debug_dir,
    )
    paint_mask = paint.get("mask") if paint.get("ok") else None

    insc = refine_inscription_mask_stats(
        image_path=fp,
        inscription_regions=regions.get("inscription_regions") or [],
        paint_mask=paint_mask,
        image_width=w,
        image_height=h,
        roi_pad_ratio=float(insc_auto.get("roi_pad_ratio", 0.08)),
        otsu_mult=float(insc_auto.get("otsu_mult", 0.80)),
        adaptive_block=int(insc_auto.get("adaptive_block", 21)),
        adaptive_c=int(insc_auto.get("adaptive_c", 12)),
        ink_mode=str(insc_auto.get("ink_mode", "and")),
        ink_open_k=int(insc_auto.get("ink_open_k", 3)),
        ink_open_iter=int(insc_auto.get("ink_open_iter", 1)),
        dilate_kx=int(insc_auto.get("dilate_kx", 17)),
        dilate_ky=int(insc_auto.get("dilate_ky", 29)),
        dilate_iter=int(insc_auto.get("dilate_iter", 1)),
        grow_max_dx_ratio=float(insc_auto.get("grow_max_dx_ratio", 0.10)),
        grow_max_dy_ratio=float(insc_auto.get("grow_max_dy_ratio", 0.15)),
        grow_min_area=int(insc_auto.get("grow_min_area", 150)),
        grow_iters=int(insc_auto.get("grow_iters", 5)),
        paint_overlap_max=float(insc_auto.get("paint_overlap_max", 0.25)),
        density_min=float(insc_auto.get("density_min", 0.12)),
        clean_open_k=int(insc_auto.get("clean_open_k", 7)),
        clean_open_iter=int(insc_auto.get("clean_open_iter", 2)),
        clean_close_k=int(insc_auto.get("clean_close_k", 3)),
        clean_close_iter=int(insc_auto.get("clean_close_iter", 2)),
        seal_h_max=int(seal_auto.get("seal_h_max", 25)),
        seal_s_min=int(seal_auto.get("seal_s_min", 20)),
        seal_v_min=int(seal_auto.get("seal_v_min", 60)),
        seal_gate_pad_ratio=float(seal_auto.get("seal_gate_pad_ratio", 0.05)),
        seal_area_min=int(seal_auto.get("seal_area_min", 80)),
        seal_area_max=int(seal_auto.get("seal_area_max", 40000)),
        seal_ar_min=float(seal_auto.get("seal_ar_min", 0.4)),
        seal_ar_max=float(seal_auto.get("seal_ar_max", 2.5)),
        seal_mean_s_min=float(seal_auto.get("seal_mean_s_min", 22)),
        seal_mean_v_max=float(seal_auto.get("seal_mean_v_max", 245)),
        seal_enable_green=bool(seal_auto.get("seal_enable_green", False)),
        seal_green_h_min=int(seal_auto.get("seal_green_h_min", 35)),
        seal_green_h_max=int(seal_auto.get("seal_green_h_max", 90)),
        seal_rect_min=float(seal_auto.get("seal_rect_min", 0.35)),
        seal_solidity_min=float(seal_auto.get("seal_solidity_min", 0.55)),
        return_mask=True,
        debug_dir=debug_dir,
    )
    insc_mask = insc.get("mask") if insc.get("ok") else None

    if paint_mask is not None and insc_mask is not None and bool(expand_auto.get("enabled", True)):
        expanded = expand_paint_mask_with_edges(
            image_path=fp,
            paint_mask=paint_mask,
            exclude_mask=insc_mask,
            pad_x_ratio=float(expand_auto.get("pad_x_ratio", 0.18)),
            pad_y_ratio=float(expand_auto.get("pad_y_ratio", 0.12)),
            right_ext_ratio=float(expand_auto.get("right_ext_ratio", 0.42)),
            x_margin_ratio=float(expand_auto.get("x_margin_ratio", 0.15)),
            bottom_cutoff_ratio=float(expand_auto.get("bottom_cutoff_ratio", 0.10)),
            edge_dilate_k=int(expand_auto.get("edge_dilate_k", 5)),
            edge_dilate_iter=int(expand_auto.get("edge_dilate_iter", 2)),
            fan_close_k=int(expand_auto.get("fan_close_k", 41)),
            fan_close_iter=int(expand_auto.get("fan_close_iter", 2)),
            max_fill_ratio=float(expand_auto.get("max_fill_ratio", 0.35)),
            min_edge_density=float(expand_auto.get("min_edge_density", 0.012)),
            adjacent_dilate_k=int(expand_auto.get("adjacent_dilate_k", 13)),
            bg_like_deltae=float(expand_auto.get("bg_like_deltae", 10.0)),
            bg_like_grad_max=float(expand_auto.get("bg_like_grad_max", 6.0)),
            bg_like_max_ratio=float(expand_auto.get("bg_like_max_ratio", 0.85)),
            max_added_ratio_of_paint=float(expand_auto.get("max_added_ratio_of_paint", 0.25)),
            max_added_ratio_of_image=float(expand_auto.get("max_added_ratio_of_image", 0.12)),
            debug_dir=debug_dir,
        )
        if expanded.get("ok") and expanded.get("mask") is not None:
            paint_mask = expanded.get("mask")

    total = float(w * h) if w > 0 and h > 0 else 0.0
    if total > 0:
        if paint_mask is not None and insc_mask is not None:
            try:
                paint_mask = cv2.subtract(paint_mask, insc_mask)
            except Exception:
                pass
        paint_px = float(cv2.countNonZero(paint_mask)) if paint_mask is not None else 0.0
        insc_px = float(cv2.countNonZero(insc_mask)) if insc_mask is not None else 0.0
        blank_px = max(0.0, total - paint_px - insc_px)
        out = {
            "painting_percent": round(paint_px / total * 100.0, 2),
            "inscription_percent": round(insc_px / total * 100.0, 2),
            "blank_percent": round(blank_px / total * 100.0, 2),
        }
    else:
        out = {}

    print("picked", image_id, w, h, fp)
    print("paint", {k: v for k, v in paint.items() if k != "mask"})
    print("inscription", {k: v for k, v in insc.items() if k != "mask"})
    print("exclusive", out)
    print("debug_dir", debug_dir)
    for name in sorted(os.listdir(debug_dir)):
        p = os.path.join(debug_dir, name)
        if os.path.isfile(p):
            print(" -", name, os.path.getsize(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
