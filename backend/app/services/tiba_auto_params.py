from __future__ import annotations

from typing import Any, Dict, Tuple

import cv2
import numpy as np


def _mask_bbox(mask: np.ndarray) -> Tuple[int, int, int, int] | None:
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _clip_bbox(b: Tuple[int, int, int, int], w: int, h: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = b
    x1 = max(0, min(w - 1, int(x1)))
    y1 = max(0, min(h - 1, int(y1)))
    x2 = max(0, min(w - 1, int(x2)))
    y2 = max(0, min(h - 1, int(y2)))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return x1, y1, x2, y2


def _border_bg_lab_stats(img_bgr: np.ndarray, ratio: float = 0.06, grad_max: float = 6.0) -> Dict[str, float]:
    h, w = img_bgr.shape[:2]
    s = max(10, int(min(h, w) * float(ratio)))
    s = min(s, min(h, w) // 3) if min(h, w) >= 60 else s
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    grad = cv2.Laplacian(gray, cv2.CV_16S, ksize=3)
    grad = np.abs(grad).astype(np.float32)
    border = np.zeros((h, w), dtype=np.uint8)
    border[0:s, :] = 1
    border[h - s : h, :] = 1
    border[:, 0:s] = 1
    border[:, w - s : w] = 1
    sel = (border > 0) & (grad < float(grad_max))
    if int(np.count_nonzero(sel)) < 500:
        sel = border > 0
    pts = img_bgr[sel]
    lab = cv2.cvtColor(pts.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    med = np.median(lab, axis=0)
    mad = np.median(np.abs(lab - med), axis=0)
    return {
        "bg_L_med": float(med[0]),
        "bg_a_med": float(med[1]),
        "bg_b_med": float(med[2]),
        "bg_L_mad": float(mad[0]),
        "bg_a_mad": float(mad[1]),
        "bg_b_mad": float(mad[2]),
        "bg_sel_ratio": float(np.count_nonzero(sel)) / float(max(1, h * w)),
        "bg_sample_px": float(lab.shape[0]),
    }


def _gray_contrast_stats(gray: np.ndarray) -> Dict[str, float]:
    if gray.size == 0:
        return {"p10": 0.0, "p50": 0.0, "p90": 0.0, "contrast": 0.0}
    p10, p50, p90 = np.percentile(gray.reshape(-1).astype(np.float32), [10, 50, 90])
    return {"p10": float(p10), "p50": float(p50), "p90": float(p90), "contrast": float(p90 - p10)}


def compute_tubi_params(image_path: str, width: int, height: int, regions: Dict[str, Any]) -> Dict[str, Any]:
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        return {
            "paint": {"bg_sample_ratio": 0.06, "bg_deltae": 12.0, "bg_grad_max": 8.0},
            "insc": {},
            "expand": {"enabled": True},
            "seal": {},
            "metrics": {"image_read_failed": True},
        }

    h, w = img.shape[:2]
    width = int(width or w)
    height = int(height or h)
    metrics: Dict[str, Any] = {}

    try:
        metrics.update(_border_bg_lab_stats(img, ratio=0.06, grad_max=6.0))
    except Exception:
        pass

    bg_L = float(metrics.get("bg_L_med", 200.0))
    bg_var = float(metrics.get("bg_L_mad", 0.0)) + float(metrics.get("bg_a_mad", 0.0)) + float(metrics.get("bg_b_mad", 0.0))
    dark_paper = bg_L < 170.0
    textured_paper = bg_var > 18.0

    hsv_all = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sch_all = hsv_all[:, :, 1].astype(np.float32)
    vch_all = hsv_all[:, :, 2].astype(np.float32)
    wash_ratio = float(np.mean((sch_all < 35) & (vch_all > 60) & (vch_all < 200)))
    edges_all = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 60, 160)
    edge_density = float(np.mean(edges_all > 0))
    metrics["wash_ratio"] = wash_ratio
    metrics["edge_density"] = edge_density
    low_edge = edge_density < 0.010
    ink_wash = wash_ratio > 0.12 and edge_density < 0.11

    paint_params = {
        "bg_sample_ratio": 0.06,
        "bg_deltae": 12.0,
        "bg_grad_max": 8.0,
        "bg_s_max": 0.0,
    }
    if ink_wash:
        paint_params["bg_deltae"] = 9.5
        paint_params["bg_grad_max"] = 4.5
        paint_params["bg_s_max"] = 0.0
    elif dark_paper:
        paint_params["bg_deltae"] = 30.0
        paint_params["bg_grad_max"] = 14.0
        paint_params["bg_s_max"] = 55.0
    elif low_edge:
        paint_params["bg_deltae"] = 18.0
        paint_params["bg_grad_max"] = 10.0
        paint_params["bg_s_max"] = 35.0
    elif textured_paper:
        paint_params["bg_deltae"] = 13.0
        paint_params["bg_grad_max"] = 6.5
        paint_params["bg_s_max"] = 35.0

    try:
        from app.services.tubi_mask_refiner import regions_to_mask

        paint_seed = regions_to_mask(regions.get("painting_regions", []) or [], w, h)
        insc_seed = regions_to_mask(regions.get("inscription_regions", []) or [], w, h)
    except Exception:
        paint_seed = np.zeros((h, w), dtype=np.uint8)
        insc_seed = np.zeros((h, w), dtype=np.uint8)

    seed_px = int(cv2.countNonZero(insc_seed))
    paint_seed_px = int(cv2.countNonZero(paint_seed))
    metrics["insc_seed_px"] = seed_px
    metrics["paint_seed_px"] = paint_seed_px
    if seed_px > 0 and paint_seed_px > 0:
        ov = int(cv2.countNonZero(cv2.bitwise_and(insc_seed, paint_seed)))
        metrics["seed_overlap_px"] = ov
        metrics["seed_overlap_ratio"] = float(ov) / float(seed_px)
    else:
        metrics["seed_overlap_px"] = 0
        metrics["seed_overlap_ratio"] = 0.0

    b = _mask_bbox(insc_seed)
    if b:
        x1, y1, x2, y2 = _clip_bbox(b, w, h)
        roi = img[y1 : y2 + 1, x1 : x2 + 1]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        cs = _gray_contrast_stats(gray)
        metrics["insc_seed_bbox"] = [x1, y1, x2, y2]
        metrics.update({f"insc_gray_{k}": v for k, v in cs.items()})
    else:
        cs = {"contrast": 0.0}

    low_contrast = float(cs.get("contrast", 0.0)) < 35.0
    small_seed = seed_px > 0 and seed_px < int(w * h * 0.015)

    insc_params: Dict[str, Any] = {}
    if low_contrast or small_seed or ink_wash or dark_paper:
        insc_params.update(
            {
                "roi_pad_ratio": 0.12,
                "otsu_mult": 0.66 if (low_contrast or ink_wash) else 0.70,
                "adaptive_block": 25,
                "adaptive_c": 6 if (low_contrast or ink_wash) else 8,
                "ink_mode": "or",
                "dilate_kx": 21,
                "dilate_ky": 35,
                "dilate_iter": 2,
                "grow_max_dx_ratio": 0.14,
                "grow_max_dy_ratio": 0.22,
                "grow_min_area": 80,
                "grow_iters": 7,
                "density_min": 0.07 if (low_contrast or ink_wash) else 0.10,
                "clean_open_k": 5,
                "clean_open_iter": 1,
                "clean_close_k": 3,
                "clean_close_iter": 1,
            }
        )
    else:
        insc_params.update({"roi_pad_ratio": 0.08, "ink_mode": "and"})

    expand_enabled = True
    if seed_px > 0 and float(metrics.get("seed_overlap_ratio", 0.0)) > 0.70:
        expand_enabled = False
    if ink_wash or low_edge:
        expand_enabled = False

    img_area = int(h * w)
    paint_is_small = paint_seed_px > 0 and img_area > 0 and float(paint_seed_px) / float(img_area) < 0.10

    expand_params = {
        "enabled": expand_enabled,
        "min_edge_density": 0.018 if dark_paper else 0.012,
        "adjacent_dilate_k": 13,
        "max_fill_ratio": 0.28 if dark_paper else 0.35,
        "bg_like_deltae": 9.0 if dark_paper else 10.0,
        "bg_like_grad_max": 6.0,
        "bg_like_max_ratio": 0.85,
        "max_added_ratio_of_paint": 1.8 if paint_is_small else 0.25,
        "max_added_ratio_of_image": 0.18 if paint_is_small else 0.12,
    }

    seal_params = {
        "seal_enable_green": True,
        "seal_green_h_min": 35,
        "seal_green_h_max": 90,
        "seal_s_min": 20,
        "seal_v_min": 55 if dark_paper else 60,
        "seal_rect_min": 0.35,
        "seal_solidity_min": 0.55,
    }

    scene = []
    if dark_paper:
        scene.append("dark_paper")
    if textured_paper:
        scene.append("textured_paper")
    if ink_wash:
        scene.append("ink_wash")
    if low_edge:
        scene.append("low_edge")
    metrics["scene_type"] = scene

    if seed_px > 0 and b:
        x1, y1, x2, y2 = _clip_bbox(b, w, h)
        gx1 = max(0, x1 - int(w * 0.05))
        gy1 = max(0, y1 - int(h * 0.05))
        gx2 = min(w - 1, x2 + int(w * 0.05))
        gy2 = min(h - 1, y2 + int(h * 0.05))
        gate = img[gy1 : gy2 + 1, gx1 : gx2 + 1]
        hsv = cv2.cvtColor(gate, cv2.COLOR_BGR2HSV)
        hch = hsv[:, :, 0].astype(np.int32)
        sch = hsv[:, :, 1].astype(np.float32)
        vch = hsv[:, :, 2].astype(np.float32)
        pale_red = ((hch <= 25) | (hch >= 165)) & (sch >= 8) & (sch <= 24) & (vch >= 90)
        pale_green = (hch >= 35) & (hch <= 90) & (sch >= 8) & (sch <= 24) & (vch >= 90)
        pale_ratio = float(np.mean(pale_red | pale_green))
        metrics["seal_pale_ratio"] = pale_ratio
        if pale_ratio > 0.0015:
            seal_params["seal_s_min"] = 12
            seal_params["seal_v_min"] = 45 if dark_paper else 50
            seal_params["seal_mean_s_min"] = 10
            seal_params["seal_mean_v_max"] = 252
            seal_params["seal_rect_min"] = 0.40
            seal_params["seal_solidity_min"] = 0.60

    return {"paint": paint_params, "insc": insc_params, "expand": expand_params, "seal": seal_params, "metrics": metrics}
