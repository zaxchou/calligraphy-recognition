import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import cv2
import numpy as np
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.path_utils import normalize_path
from app.models.tubi_analysis import TubiAnalysis
from app.services.inscription_position_analyzer import analyze_inscription_position
from app.services.siliconflow_service import calculate_area_stats
from app.services.tubi_auto_params import compute_tubi_params
from app.services.auto_tags import compute_tags
from app.services.tubi_mask_refiner import (
    expand_paint_mask_with_edges,
    mask_to_regions,
    refine_inscription_mask_stats,
    refine_paint_mask_stats,
    regions_to_mask,
)


def _to_local_path(p: str) -> str:
    if not p:
        return ""
    p2 = p.replace("/", os.sep)
    if os.path.isabs(p2) or (len(p2) >= 2 and p2[1] == ":"):
        return os.path.normpath(p2)
    p2 = p2.lstrip("\\/")
    return os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p2))


def _is_image_file(p: str) -> bool:
    ext = os.path.splitext(p or "")[1].lower()
    return ext in (".jpg", ".jpeg", ".png", ".webp")


def _parse_bool(v: str, default: bool = False) -> bool:
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _write_ids(path: str, ids: list[str]) -> None:
    if not ids:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for x in ids:
            f.write(str(x).strip() + "\n")


def _read_ids(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            out = []
            for line in f:
                s = (line or "").strip()
                if s:
                    out.append(s)
            return out
    except Exception:
        return []


def _run_with_subprocess_timeout(
    ids: list[str],
    *,
    timeout_sec: int,
    save_debug: bool,
    do_expand: bool,
    refresh_regions: bool,
) -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fail_path = os.path.join("data", f"reanalyze_failed_ids_{ts}.txt")
    timeout_path = os.path.join("data", f"reanalyze_timeout_ids_{ts}.txt")
    ok = 0
    failed = 0
    timed_out = 0
    for i, image_id in enumerate(ids, start=1):
        print(f"[{i}/{len(ids)}] start", image_id, flush=True)
        child_env = os.environ.copy()
        child_env["TUBI_REANALYZE_SUBPROCESS_CHILD"] = "1"
        child_env["TUBI_REANALYZE_ONLY_IDS"] = image_id
        child_env["TUBI_REANALYZE_LIMIT"] = "0"
        child_env["TUBI_REANALYZE_OFFSET"] = "0"
        child_env["TUBI_REANALYZE_REFRESH_REGIONS"] = "true" if refresh_regions else "false"
        child_env["TUBI_DEBUG_SAVE_IMAGES"] = "true" if save_debug else "false"
        child_env["TUBI_REANALYZE_ENABLE_EXPAND"] = "true" if do_expand else "false"
        child_env["TUBI_REANALYZE_USE_SUBPROCESS"] = "false"

        t0 = time.perf_counter()
        try:
            p = subprocess.run(
                [sys.executable, os.path.join("scripts", "dev_reanalyze_existing_uploads.py")],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                env=child_env,
                timeout=(int(timeout_sec) if int(timeout_sec) > 0 else None),
                capture_output=True,
                text=True,
            )
            dt = time.perf_counter() - t0
            if p.returncode == 0:
                ok += 1
                print(f"[{i}/{len(ids)}] ok", image_id, f"{dt:.2f}s", flush=True)
            else:
                failed += 1
                _write_ids(fail_path, [image_id])
                print(f"[{i}/{len(ids)}] fail", image_id, f"{dt:.2f}s", (p.stderr or p.stdout or "")[:200].replace("\n", " "), flush=True)
        except subprocess.TimeoutExpired:
            dt = time.perf_counter() - t0
            timed_out += 1
            _write_ids(timeout_path, [image_id])
            print(f"[{i}/{len(ids)}] timeout", image_id, f"{dt:.2f}s", flush=True)

    print("done", {"ok": ok, "failed": failed, "timeout": timed_out, "fail_file": fail_path, "timeout_file": timeout_path})
    return 0 if (failed == 0 and timed_out == 0) else 1


def _normalize_regions_insc_first(regions: dict, w: int, h: int) -> bool:
    try:
        paint_seed = regions_to_mask(regions.get("painting_regions", []) or [], w, h)
        insc_seed = regions_to_mask(regions.get("inscription_regions", []) or [], w, h)
        if cv2.countNonZero(paint_seed) > 0 and cv2.countNonZero(insc_seed) > 0:
            paint_norm = cv2.subtract(paint_seed, insc_seed)
            norm_regions = mask_to_regions(paint_norm)
            if norm_regions:
                regions["painting_regions"] = norm_regions
                return True
    except Exception:
        pass
    return False


def _write_annotated(image_path: str, out_path: str, paint_mask: np.ndarray | None, insc_mask: np.ndarray | None) -> str | None:
    img_bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return None
    overlay = img_bgr.copy()
    if paint_mask is not None:
        blue = np.zeros_like(img_bgr)
        blue[:, :, 0] = 255
        paint_blend = cv2.addWeighted(overlay, 0.72, blue, 0.28, 0.0)
        cv2.copyTo(paint_blend, paint_mask, overlay)
    if insc_mask is not None:
        red = np.zeros_like(img_bgr)
        red[:, :, 2] = 255
        ins_blend = cv2.addWeighted(overlay, 0.65, red, 0.35, 0.0)
        cv2.copyTo(ins_blend, insc_mask, overlay)
    os.makedirs(os.path.dirname(_to_local_path(out_path)), exist_ok=True)
    cv2.imwrite(_to_local_path(out_path), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return normalize_path(out_path)


def main() -> int:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
    settings = get_settings()

    only_ids = [s.strip() for s in os.getenv("TUBI_REANALYZE_ONLY_IDS", "").split(",") if s.strip()]
    only_failed_file = os.getenv("TUBI_REANALYZE_ONLY_FAILED_FILE", "").strip()
    if only_failed_file:
        only_ids = _read_ids(only_failed_file)
    limit = int(os.getenv("TUBI_REANALYZE_LIMIT", "0") or 0)
    offset = int(os.getenv("TUBI_REANALYZE_OFFSET", "0") or 0)
    refresh_regions = _parse_bool(os.getenv("TUBI_REANALYZE_REFRESH_REGIONS", ""), default=False)
    save_debug = _parse_bool(os.getenv("TUBI_DEBUG_SAVE_IMAGES", ""), default=False)
    do_expand = _parse_bool(os.getenv("TUBI_REANALYZE_ENABLE_EXPAND", ""), default=True)
    use_subprocess = _parse_bool(os.getenv("TUBI_REANALYZE_USE_SUBPROCESS", ""), default=False)
    timeout_sec = int(os.getenv("TUBI_REANALYZE_TIMEOUT_SEC", "0") or 0)
    child = os.getenv("TUBI_REANALYZE_SUBPROCESS_CHILD", "").strip() == "1"

    db = SessionLocal()
    ok = 0
    skipped = 0
    failed = 0
    try:
        q = db.query(TubiAnalysis)
        if only_ids:
            q = q.filter(TubiAnalysis.image_id.in_(only_ids))
        q = q.order_by(TubiAnalysis.created_at.desc())
        if offset:
            q = q.offset(offset)
        if limit:
            q = q.limit(limit)
        rows = q.all()
        if not rows:
            print("no_rows")
            return 2

        if use_subprocess and not child:
            ids = [r.image_id for r in rows if r and r.image_id]
            db.close()
            return _run_with_subprocess_timeout(
                ids,
                timeout_sec=timeout_sec,
                save_debug=save_debug,
                do_expand=do_expand,
                refresh_regions=refresh_regions,
            )

        for idx, a in enumerate(rows, start=1):
            try:
                fp = _to_local_path(a.filepath)
                if not _is_image_file(fp) or not os.path.exists(fp):
                    skipped += 1
                    continue

                try:
                    size_mb = float(os.path.getsize(fp)) / float(1024 * 1024)
                except Exception:
                    size_mb = 0.0
                print(f"[{idx}/{len(rows)}] processing", a.image_id, f"{size_mb:.1f}MB", fp, flush=True)

                img = cv2.imread(fp, cv2.IMREAD_COLOR)
                if img is None:
                    skipped += 1
                    continue
                h, w = img.shape[:2]
                if not a.image_width or not a.image_height:
                    a.image_width = int(w)
                    a.image_height = int(h)

                regions = a.regions or {}
                if isinstance(regions, str):
                    regions = json.loads(regions)
                if not isinstance(regions, dict):
                    regions = {}

                normalized = _normalize_regions_insc_first(regions, w, h)

                auto = compute_tubi_params(fp, w, h, regions)
                meta = regions.get("_meta") if isinstance(regions, dict) else None
                if not isinstance(meta, dict):
                    meta = {}
                meta["auto_params"] = {k: v for k, v in (auto or {}).items() if k in ("paint", "insc", "expand", "seal")}
                meta["auto_metrics"] = (auto or {}).get("metrics") or {}
                meta["normalized_regions"] = bool(normalized)
                regions["_meta"] = meta

                try:
                    area_stats = calculate_area_stats(regions, w, h)
                except Exception:
                    area_stats = {"painting_percent": 0.0, "inscription_percent": 0.0, "blank_percent": 0.0}

                dbg = os.path.join("data", "tubi_debug", str(a.image_id)) if save_debug else None

                paint_auto = (auto or {}).get("paint") or {}
                paint_mask = None
                refined_paint = refine_paint_mask_stats(
                    image_path=fp,
                    painting_regions=regions.get("painting_regions", []) or [],
                    image_width=w,
                    image_height=h,
                    bg_sample_ratio=float(paint_auto.get("bg_sample_ratio", 0.06)),
                    bg_deltae=float(paint_auto.get("bg_deltae", 12.0)),
                    bg_grad_max=float(paint_auto.get("bg_grad_max", 8.0)),
                    bg_s_max=float(paint_auto.get("bg_s_max", 0.0)),
                    return_mask=True,
                    debug_dir=dbg,
                )
                if refined_paint.get("ok"):
                    paint_mask = refined_paint.get("mask")

                insc_seed_mask = None
                try:
                    insc_seed_mask = regions_to_mask(regions.get("inscription_regions", []) or [], w, h)
                except Exception:
                    insc_seed_mask = None

                insc_auto = (auto or {}).get("insc") or {}
                seal_auto = (auto or {}).get("seal") or {}
                inscription_mask = None
                refined_insc = refine_inscription_mask_stats(
                    image_path=fp,
                    inscription_regions=regions.get("inscription_regions", []) or [],
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
                    debug_dir=dbg,
                )
                if refined_insc.get("ok"):
                    inscription_mask = refined_insc.get("mask")
                elif insc_seed_mask is not None and cv2.countNonZero(insc_seed_mask) > 0:
                    inscription_mask = insc_seed_mask
                    if dbg:
                        try:
                            os.makedirs(dbg, exist_ok=True)
                            cv2.imwrite(os.path.join(dbg, "inscription_seed.png"), insc_seed_mask)
                            cv2.imwrite(os.path.join(dbg, "inscription_mask.png"), inscription_mask)
                        except Exception:
                            pass

                if paint_mask is not None and inscription_mask is not None:
                    paint_mask = cv2.subtract(paint_mask, inscription_mask)

                expand_auto = (auto or {}).get("expand") or {}
                if (
                    do_expand
                    and paint_mask is not None
                    and inscription_mask is not None
                    and bool(expand_auto.get("enabled", True))
                ):
                    expanded = expand_paint_mask_with_edges(
                        image_path=fp,
                        paint_mask=paint_mask,
                        exclude_mask=inscription_mask,
                        pad_x_ratio=float(expand_auto.get("pad_x_ratio", getattr(settings, "TUBI_FAN_EXPAND_PAD_X_RATIO", 0.18))),
                        pad_y_ratio=float(expand_auto.get("pad_y_ratio", getattr(settings, "TUBI_FAN_EXPAND_PAD_Y_RATIO", 0.12))),
                        right_ext_ratio=float(expand_auto.get("right_ext_ratio", getattr(settings, "TUBI_FAN_EXPAND_RIGHT_EXT_RATIO", 0.42))),
                        x_margin_ratio=float(expand_auto.get("x_margin_ratio", getattr(settings, "TUBI_FAN_EXPAND_X_MARGIN_RATIO", 0.15))),
                        bottom_cutoff_ratio=float(expand_auto.get("bottom_cutoff_ratio", getattr(settings, "TUBI_FAN_EXPAND_BOTTOM_CUTOFF_RATIO", 0.10))),
                        edge_dilate_k=int(expand_auto.get("edge_dilate_k", getattr(settings, "TUBI_FAN_EDGE_DILATE_K", 5))),
                        edge_dilate_iter=int(expand_auto.get("edge_dilate_iter", getattr(settings, "TUBI_FAN_EDGE_DILATE_ITER", 2))),
                        fan_close_k=int(expand_auto.get("fan_close_k", getattr(settings, "TUBI_FAN_FAN_CLOSE_K", 41))),
                        fan_close_iter=int(expand_auto.get("fan_close_iter", getattr(settings, "TUBI_FAN_FAN_CLOSE_ITER", 2))),
                        max_fill_ratio=float(expand_auto.get("max_fill_ratio", getattr(settings, "TUBI_FAN_MAX_FILL_RATIO", 0.35))),
                        min_edge_density=float(expand_auto.get("min_edge_density", 0.012)),
                        adjacent_dilate_k=int(expand_auto.get("adjacent_dilate_k", 13)),
                        bg_like_deltae=float(expand_auto.get("bg_like_deltae", 10.0)),
                        bg_like_grad_max=float(expand_auto.get("bg_like_grad_max", 6.0)),
                        bg_like_max_ratio=float(expand_auto.get("bg_like_max_ratio", 0.85)),
                        max_added_ratio_of_paint=float(expand_auto.get("max_added_ratio_of_paint", 0.25)),
                        max_added_ratio_of_image=float(expand_auto.get("max_added_ratio_of_image", 0.12)),
                        debug_dir=dbg,
                    )
                    if expanded.get("ok") and expanded.get("mask") is not None:
                        paint_mask = expanded.get("mask")

                if paint_mask is not None or inscription_mask is not None:
                    total_pixels = float(w * h) if w > 0 and h > 0 else 0.0
                    if total_pixels > 0:
                        paint_px = float(cv2.countNonZero(paint_mask)) if paint_mask is not None else total_pixels * float(area_stats.get("painting_percent", 0.0)) / 100.0
                        insc_px = float(cv2.countNonZero(inscription_mask)) if inscription_mask is not None else total_pixels * float(area_stats.get("inscription_percent", 0.0)) / 100.0
                        blank_px = total_pixels - paint_px - insc_px
                        if blank_px < 0:
                            blank_px = 0.0
                        area_stats["painting_percent"] = float(round(paint_px / total_pixels * 100.0, 2))
                        area_stats["inscription_percent"] = float(round(insc_px / total_pixels * 100.0, 2))
                        area_stats["blank_percent"] = float(round(blank_px / total_pixels * 100.0, 2))

                try:
                    position_analysis = analyze_inscription_position(regions, w, h)
                except Exception:
                    position_analysis = {}

                annotated_path = f"data/annotated/annotated_{a.image_id}.jpg"
                annotated_image_path = _write_annotated(fp, annotated_path, paint_mask, inscription_mask)

                a.regions = regions
                a.painting_percent = float(area_stats.get("painting_percent", 0.0) or 0.0)
                a.inscription_percent = float(area_stats.get("inscription_percent", 0.0) or 0.0)
                a.blank_percent = float(area_stats.get("blank_percent", 0.0) or 0.0)
                a.position_analysis = position_analysis
                if annotated_image_path:
                    a.annotated_image_path = annotated_image_path
                a.status = "analyzed"
                a.updated_at = datetime.now(timezone.utc)
                # 自动标签持久化
                try:
                    record_for_tags = {
                        "title": a.title,
                        "period_phase": a.period_phase,
                        "artwork_height_cm": a.artwork_height_cm,
                        "artwork_width_cm": a.artwork_width_cm,
                        "content_analysis": a.content_analysis,
                        "material_tags": a.material_tags,
                    }
                    auto_tags = compute_tags(record_for_tags)
                    if auto_tags:
                        existing_tags = []
                        if a.tags:
                            try:
                                existing_tags = json.loads(a.tags) if isinstance(a.tags, str) else a.tags
                            except Exception:
                                existing_tags = []
                        if not isinstance(existing_tags, list):
                            existing_tags = []
                        for tag in auto_tags:
                            if tag not in existing_tags:
                                existing_tags.append(tag)
                        a.tags = json.dumps(existing_tags, ensure_ascii=False)
                except Exception as e:
                    print(f"  [警告] 自动标签持久化失败: {e}")

                db.add(a)
                db.commit()
                ok += 1
                print(f"[{idx}/{len(rows)}] ok", a.image_id, a.painting_percent, a.inscription_percent, a.blank_percent)
            except Exception as e:
                db.rollback()
                failed += 1
                print(f"[{idx}/{len(rows)}] fail", a.image_id, str(e)[:200])
                continue

        print("done", {"ok": ok, "skipped": skipped, "failed": failed})
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
