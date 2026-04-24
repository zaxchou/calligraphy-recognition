import os
from typing import Any, Dict, Iterable, List, Tuple

import cv2
import numpy as np


def _regions_bbox(regions: Iterable[Dict[str, Any]], width: int, height: int) -> Tuple[int, int, int, int] | None:
    xs: List[int] = []
    ys: List[int] = []
    for r in regions or []:
        pts = r.get("points")
        if not isinstance(pts, list):
            continue
        for p in pts:
            try:
                x = int(p.get("x", 0))
                y = int(p.get("y", 0))
            except Exception:
                continue
            xs.append(x)
            ys.append(y)
    if not xs or not ys:
        return None
    x1 = max(0, min(xs))
    y1 = max(0, min(ys))
    x2 = min(width - 1, max(xs))
    y2 = min(height - 1, max(ys))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _ensure_dir(path: str) -> None:
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def _overlay_mask(img_bgr: np.ndarray, mask: np.ndarray, color_bgr: Tuple[int, int, int], alpha: float = 0.35) -> np.ndarray:
    if mask.ndim == 2:
        m = mask > 0
    else:
        m = mask[:, :, 0] > 0
    overlay = img_bgr.copy()
    overlay[m] = (overlay[m] * (1.0 - alpha) + np.array(color_bgr, dtype=np.float32) * alpha).astype(np.uint8)
    return overlay


def refine_paint_mask_stats(
    image_path: str,
    painting_regions: List[Dict[str, Any]],
    image_width: int,
    image_height: int,
    bg_sample_ratio: float = 0.06,
    bg_deltae: float = 12.0,
    bg_grad_max: float = 8.0,
    bg_s_max: float = 0.0,
    return_mask: bool = False,
    debug_dir: str | None = None,
    max_roi_pixels: int = 500_000,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False}
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        out["error"] = "image_read_failed"
        return out

    h, w = img.shape[:2]
    if image_width and image_height and (image_width != w or image_height != h):
        w = image_width
        h = image_height

    bbox = _regions_bbox(painting_regions, w, h)
    if not bbox:
        out["error"] = "no_painting_bbox"
        return out

    x1, y1, x2, y2 = bbox
    pad_x = int((x2 - x1 + 1) * 0.05)
    pad_y = int((y2 - y1 + 1) * 0.05)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w - 1, x2 + pad_x)
    y2 = min(h - 1, y2 + pad_y)
    roi = img[y1 : y2 + 1, x1 : x2 + 1]
    rh, rw = roi.shape[:2]
    if rh < 20 or rw < 20:
        out["error"] = "roi_too_small"
        return out

    try:
        bbox_area_ratio = float(rw * rh) / float(max(1, w * h))
        if bbox_area_ratio > 0.55:
            hsv0 = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            s0 = hsv0[:, :, 1].astype(np.float32)
            gray0 = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            grad0 = cv2.Laplacian(gray0, cv2.CV_16S, ksize=3)
            grad0 = np.abs(grad0).astype(np.float32)
            rough = ((s0 > 45.0) & (gray0 < 245)).astype(np.uint8) * 255
            rough2 = (grad0 > 14.0).astype(np.uint8) * 255
            rough = cv2.bitwise_or(rough, rough2)
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
            rough = cv2.morphologyEx(rough, cv2.MORPH_CLOSE, k, iterations=1)
            ys2, xs2 = np.where(rough > 0)
            if xs2.size > 0:
                rx1, rx2 = int(xs2.min()), int(xs2.max())
                ry1, ry2 = int(ys2.min()), int(ys2.max())
                pad = int(min(rw, rh) * 0.04)
                rx1 = max(0, rx1 - pad)
                ry1 = max(0, ry1 - pad)
                rx2 = min(rw - 1, rx2 + pad)
                ry2 = min(rh - 1, ry2 + pad)
                if (rx2 - rx1 + 1) >= 40 and (ry2 - ry1 + 1) >= 40:
                    x1, y1, x2, y2 = x1 + rx1, y1 + ry1, x1 + rx2, y1 + ry2
                    roi = img[y1 : y2 + 1, x1 : x2 + 1]
                    rh, rw = roi.shape[:2]
    except Exception:
        pass

    # --- 暗黄纸检测（用于决定绘画mask策略）---
    hsv_full = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat_mean = float(hsv_full[:, :, 1].mean())
    corner_size = 30
    gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    corners_gray = [
        gray_full[0:corner_size, 0:corner_size],
        gray_full[0:corner_size, w - corner_size:w],
        gray_full[h - corner_size:h, 0:corner_size],
        gray_full[h - corner_size:h, w - corner_size:w],
    ]
    paper_base_gray = float(np.median([c.mean() for c in corners_gray]))
    is_dark_paper = paper_base_gray < 190 or sat_mean > 35

    scale = 1.0
    roi_pixels = int(rh * rw)
    if roi_pixels > max_roi_pixels:
        scale = float(np.sqrt(max_roi_pixels / float(roi_pixels)))
        new_w = max(20, int(rw * scale))
        new_h = max(20, int(rh * scale))
        roi_small = cv2.resize(roi, (new_w, new_h), interpolation=cv2.INTER_AREA)
    else:
        roi_small = roi

    sh, sw = roi_small.shape[:2]

    # --- 暗黄纸使用 Otsu + 低阈值淡墨策略（替代 grabCut）---
    if is_dark_paper:
        gray_roi = cv2.cvtColor(roi_small, cv2.COLOR_BGR2GRAY)
        hsv_roi = cv2.cvtColor(roi_small, cv2.COLOR_BGR2HSV)
        sat_roi = hsv_roi[:, :, 1].astype(np.float32)

        # Otsu 反色
        _, otsu_inv = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 带偏移的严格阈值（偏移3）
        otsu_thresh_val = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]
        effective_thresh = int(otsu_thresh_val) + 3
        _, strict_inv = cv2.threshold(gray_roi, float(effective_thresh), 255, cv2.THRESH_BINARY_INV)

        # 低阈值抓淡墨（仅在 ROI 不太大时启用，避免全图误判）
        roi_area_ratio = float(rh * rw) / float(max(1, h * w))
        if roi_area_ratio < 0.65:
            # 小/中等 ROI：可以用 light_ink 抓淡墨笔画
            _, light_raw = cv2.threshold(gray_roi, float(paper_gray_scaled) - 20, 255, cv2.THRESH_BINARY_INV)
            # 饱和度过滤：墨迹有颜色，旧纸灰斑是低饱和度的
            sat_mask = (sat_roi >= 30.0).astype(np.uint8) * 255
            light_ink = cv2.bitwise_and(light_raw, sat_mask)
            fg = cv2.bitwise_or(otsu_inv, cv2.bitwise_or(strict_inv, light_ink))
        else:
            # 大 ROI（接近全图）：只用 Otsu+strict，不用 light_ink
            # 避免"比纸色暗一点就都是画"的问题
            fg = cv2.bitwise_or(otsu_inv, strict_inv)

        # 闭运算 9×9 ×3次，让笔画更饱满、连接更好
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel_close, iterations=3)
        # 开运算去噪
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel_open, iterations=1)

        # 连通区过滤：>=200px（降低门槛，保留更多竹叶碎片）
        try:
            num, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
            if num > 1:
                clean = np.zeros_like(fg)
                for lid in range(1, num):
                    if int(stats[lid, cv2.CC_STAT_AREA]) >= 200:
                        clean[labels == lid] = 255
                fg = clean
        except Exception:
            pass

        removed_small = np.zeros_like(fg)
    else:
        # --- 亮纸使用原有 grabCut 策略 ---
        rect = (1, 1, max(1, sw - 2), max(1, sh - 2))
        mask = np.full((sh, sw), cv2.GC_BGD, dtype=np.uint8)
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)

        try:
            iter_count = 5 if sw * sh <= 350_000 else 3
            cv2.grabCut(roi_small, mask, rect, bgd, fgd, iterCount=iter_count, mode=cv2.GC_INIT_WITH_RECT)
        except Exception:
            out["error"] = "grabcut_failed"
            return out

        fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

        bg_s = max(10, int(min(h, w) * float(bg_sample_ratio)))
        bg_s = min(bg_s, min(h, w) // 4) if min(h, w) >= 40 else bg_s
        bg_samples = []
        try:
            bg_samples.append(img[0:bg_s, 0:bg_s])
            bg_samples.append(img[0:bg_s, w - bg_s : w])
            bg_samples.append(img[h - bg_s : h, 0:bg_s])
            bg_samples.append(img[h - bg_s : h, w - bg_s : w])
            bg_stack = np.concatenate([p.reshape(-1, 3) for p in bg_samples if p is not None and p.size > 0], axis=0)
            bg_lab = cv2.cvtColor(bg_stack.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1, 3)
            bg_med = np.median(bg_lab, axis=0).astype(np.float32)
        except Exception:
            bg_med = None

        hsv = cv2.cvtColor(roi_small, cv2.COLOR_BGR2HSV)
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]
        white = ((v > 245) & (s < 25)).astype(np.uint8) * 255
        fg = cv2.bitwise_and(fg, cv2.bitwise_not(white))

        removed_small = np.zeros_like(fg)
        if bg_med is not None:
            roi_lab = cv2.cvtColor(roi_small, cv2.COLOR_BGR2LAB).astype(np.float32)
            d0 = roi_lab[:, :, 0] - bg_med[0]
            d1 = roi_lab[:, :, 1] - bg_med[1]
            d2 = roi_lab[:, :, 2] - bg_med[2]
            delta = np.sqrt(d0 * d0 + d1 * d1 + d2 * d2)
            gray = cv2.cvtColor(roi_small, cv2.COLOR_BGR2GRAY)
            grad = cv2.Laplacian(gray, cv2.CV_16S, ksize=3)
            grad = np.abs(grad).astype(np.float32)
            candidate = (fg > 0) & (delta < float(bg_deltae)) & (grad < float(bg_grad_max))
            removed_small[candidate] = 255
            fg[candidate] = 0
            if float(bg_s_max) > 0:
                cand2 = (fg > 0) & (s < float(bg_s_max)) & (grad < float(bg_grad_max))
                removed_small[cand2] = 255
                fg[cand2] = 0
            fg_ratio2 = float(cv2.countNonZero(fg)) / float(max(1, sw * sh))
            if fg_ratio2 > 0.35:
                thr = float(bg_deltae) * 1.6
                gthr = float(bg_grad_max) * 1.2
                cand3 = (fg > 0) & (delta < thr) & (grad < gthr)
                removed_small[cand3] = 255
                fg[cand3] = 0

        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_ratio = float(cv2.countNonZero(fg)) / float(max(1, sw * sh))
        if fg_ratio < 0.28:
            k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k7, iterations=2)
            fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k3, iterations=1)
        else:
            fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k3, iterations=2)

        try:
            num, labels, stats, _ = cv2.connectedComponentsWithStats((fg > 0).astype(np.uint8), connectivity=8)
            if num > 1:
                min_keep = max(300, int(sw * sh * 0.0005))
                keep = np.zeros(num, dtype=np.uint8)
                keep[0] = 0
                for lid in range(1, num):
                    if int(stats[lid, cv2.CC_STAT_AREA]) >= min_keep:
                        keep[lid] = 1
                fg = (keep[labels] * 255).astype(np.uint8)
        except Exception:
            pass

    if scale != 1.0:
        fg = cv2.resize(fg, (rw, rh), interpolation=cv2.INTER_NEAREST)
        removed_small = cv2.resize(removed_small, (rw, rh), interpolation=cv2.INTER_NEAREST)

    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y1 : y2 + 1, x1 : x2 + 1] = fg
    full_removed = np.zeros((h, w), dtype=np.uint8)
    full_removed[y1 : y2 + 1, x1 : x2 + 1] = removed_small

    paint_pixels = int(cv2.countNonZero(full_mask))
    total_pixels = int(w * h) if w > 0 and h > 0 else int(image_width * image_height)
    paint_percent = (paint_pixels / float(total_pixels) * 100.0) if total_pixels > 0 else 0.0

    if debug_dir:
        _ensure_dir(debug_dir)
        try:
            cv2.imwrite(os.path.join(debug_dir, "paint_mask.png"), full_mask)
            cv2.imwrite(os.path.join(debug_dir, "paint_bg_removed.png"), full_removed)
            overlay = _overlay_mask(img, full_mask, (255, 0, 0), alpha=0.35)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 200, 255), 2)
            cv2.imwrite(os.path.join(debug_dir, "paint_overlay.jpg"), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        except Exception:
            pass

    out.update(
        {
            "ok": True,
            "painting_pixels": paint_pixels,
            "painting_percent": float(round(paint_percent, 2)),
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
        }
    )
    if return_mask:
        out["mask"] = full_mask
    return out


def _regions_seed_mask(regions: Iterable[Dict[str, Any]], width: int, height: int) -> np.ndarray:
    m = np.zeros((height, width), dtype=np.uint8)
    for r in regions or []:
        pts = r.get("points")
        if not isinstance(pts, list) or len(pts) < 3:
            continue
        poly = []
        for p in pts:
            try:
                x = int(p.get("x", 0))
                y = int(p.get("y", 0))
            except Exception:
                continue
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))
            poly.append([x, y])
        if len(poly) >= 3:
            arr = np.array([poly], dtype=np.int32)
            cv2.fillPoly(m, arr, 255)
    return m


def regions_to_mask(regions: Iterable[Dict[str, Any]], width: int, height: int) -> np.ndarray:
    return _regions_seed_mask(regions, width, height)


def mask_to_regions(
    mask: np.ndarray,
    approx_epsilon_ratio: float = 0.003,
    min_area: int = 200,
    max_regions: int = 20,
) -> List[Dict[str, Any]]:
    if mask is None or mask.size == 0:
        return []
    m = (mask > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    items = []
    for cnt in contours:
        if cnt is None or len(cnt) < 3:
            continue
        area = float(cv2.contourArea(cnt))
        if area < float(min_area):
            continue
        peri = float(cv2.arcLength(cnt, True))
        eps = float(max(0.5, peri * float(approx_epsilon_ratio)))
        approx = cv2.approxPolyDP(cnt, eps, True)
        if approx is None or len(approx) < 3:
            continue
        pts = approx.reshape(-1, 2).tolist()
        items.append((area, pts))
    if not items:
        return []
    items.sort(key=lambda t: t[0], reverse=True)
    out = []
    for _, pts in items[: int(max_regions)]:
        out.append({"points": [{"x": int(x), "y": int(y)} for x, y in pts]})
    return out


def refine_inscription_mask_stats(
    image_path: str,
    inscription_regions: List[Dict[str, Any]],
    paint_mask: np.ndarray | None,
    image_width: int,
    image_height: int,
    roi_pad_ratio: float = 0.08,
    otsu_mult: float = 0.80,
    adaptive_block: int = 21,
    adaptive_c: int = 12,
    ink_mode: str = "and",
    ink_open_k: int = 3,
    ink_open_iter: int = 1,
    dilate_kx: int = 17,
    dilate_ky: int = 29,
    dilate_iter: int = 1,
    grow_max_dx_ratio: float = 0.10,
    grow_max_dy_ratio: float = 0.15,
    grow_min_area: int = 150,
    grow_iters: int = 5,
    paint_overlap_max: float = 0.25,
    density_min: float = 0.12,
    clean_open_k: int = 7,
    clean_open_iter: int = 2,
    clean_close_k: int = 3,
    clean_close_iter: int = 2,
    seal_h_max: int = 25,
    seal_s_min: int = 20,
    seal_v_min: int = 60,
    seal_gate_pad_ratio: float = 0.05,
    seal_area_min: int = 80,
    seal_area_max: int = 40000,
    seal_ar_min: float = 0.4,
    seal_ar_max: float = 2.5,
    seal_mean_s_min: float = 22,
    seal_mean_v_max: float = 245,
    seal_enable_green: bool = False,
    seal_green_h_min: int = 35,
    seal_green_h_max: int = 90,
    seal_rect_min: float = 0.35,
    seal_solidity_min: float = 0.55,
    return_mask: bool = False,
    debug_dir: str | None = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False}
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        out["error"] = "image_read_failed"
        return out

    h, w = img.shape[:2]
    if image_width and image_height and (image_width != w or image_height != h):
        w = image_width
        h = image_height

    seed = _regions_seed_mask(inscription_regions, w, h)
    if cv2.countNonZero(seed) == 0:
        out["error"] = "no_inscription_seed"
        return out

    bbox = _regions_bbox(inscription_regions, w, h)
    if not bbox:
        out["error"] = "no_inscription_bbox"
        return out

    x1, y1, x2, y2 = bbox
    pad_x = int((x2 - x1 + 1) * float(roi_pad_ratio))
    pad_y = int((y2 - y1 + 1) * float(roi_pad_ratio))
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w - 1, x2 + pad_x)
    y2 = min(h - 1, y2 + pad_y)

    roi = img[y1 : y2 + 1, x1 : x2 + 1]
    seed_roi = seed[y1 : y2 + 1, x1 : x2 + 1]
    if cv2.countNonZero(seed_roi) == 0:
        out["error"] = "seed_outside_roi"
        return out

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    otsu_val, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    sensitive = cv2.threshold(gray, int(otsu_val * float(otsu_mult)), 255, cv2.THRESH_BINARY_INV)[1]
    b = int(adaptive_block)
    if b < 3:
        b = 3
    if b % 2 == 0:
        b += 1
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, b, int(adaptive_c))
    mode = str(ink_mode or "and").strip().lower()
    if mode == "or":
        ink = cv2.bitwise_or(sensitive, adaptive)
    else:
        ink = cv2.bitwise_and(sensitive, adaptive)

    ok = max(1, int(ink_open_k))
    if ok % 2 == 0:
        ok += 1
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ok, ok))
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, k_open, iterations=max(1, int(ink_open_iter)))

    paint_roi = None
    paint_excl_roi = None
    if paint_mask is not None and paint_mask.shape[:2] == (h, w):
        paint_roi = paint_mask[y1 : y2 + 1, x1 : x2 + 1]
        try:
            seed_px = int(cv2.countNonZero(seed_roi))
            if seed_px > 0:
                ov = int(cv2.countNonZero(cv2.bitwise_and(paint_roi, seed_roi)))
                ov_ratio = float(ov) / float(seed_px)
            else:
                ov_ratio = 0.0
        except Exception:
            ov_ratio = 0.0
        if ov_ratio < 0.35:
            paint_excl_roi = paint_roi
            ink = cv2.subtract(ink, paint_excl_roi)

    dkx = max(1, int(dilate_kx))
    dky = max(1, int(dilate_ky))
    if dkx % 2 == 0:
        dkx += 1
    if dky % 2 == 0:
        dky += 1
    dil_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dkx, dky))
    ink_connected = cv2.dilate(ink, dil_k, iterations=max(1, int(dilate_iter)))

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(ink_connected, connectivity=8)
    if num <= 1:
        out["error"] = "no_components"
        return out

    seed_components = set()
    for lid in range(1, num):
        comp = (labels == lid).astype(np.uint8) * 255
        if cv2.countNonZero(cv2.bitwise_and(comp, seed_roi)) > 0:
            seed_components.add(lid)

    if not seed_components:
        out["error"] = "no_seed_components"
        return out

    merged = set(seed_components)
    result_roi = np.zeros(seed_roi.shape[:2], dtype=np.uint8)
    for lid in merged:
        result_roi[labels == lid] = 255

    rh, rw = result_roi.shape[:2]
    max_dx = rw * float(grow_max_dx_ratio)
    max_dy = rh * float(grow_max_dy_ratio)
    min_area = int(grow_min_area)
    sd = max(11, int(min(rw, rh) * 0.06))
    if sd % 2 == 0:
        sd += 1
    sd_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sd, sd))
    seed_dilated = cv2.dilate(seed_roi, sd_k, iterations=1)
    ad = max(9, int(min(rw, rh) * 0.04))
    if ad % 2 == 0:
        ad += 1
    anchor_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ad, ad))

    for _ in range(max(1, int(grow_iters))):
        ys, xs = np.where(result_roi > 0)
        if xs.size == 0:
            break
        cur_x_min, cur_x_max = int(xs.min()), int(xs.max())
        cur_y_min, cur_y_max = int(ys.min()), int(ys.max())
        anchor = cv2.dilate(result_roi, anchor_k, iterations=1)
        added = 0
        for lid in range(1, num):
            if lid in merged:
                continue
            x, y, bw, bh, area = stats[lid]
            if area < min_area:
                continue
            x_near = (x <= cur_x_max + max_dx and x + bw >= cur_x_min - max_dx * 0.5)
            y_near = (y <= cur_y_max + max_dy and y + bh >= cur_y_min - max_dy * 0.3)
            if not (x_near and y_near):
                continue

            comp = (labels == lid).astype(np.uint8) * 255
            if cv2.countNonZero(cv2.bitwise_and(comp, seed_dilated)) == 0 and cv2.countNonZero(cv2.bitwise_and(comp, anchor)) == 0:
                continue
            if paint_excl_roi is not None:
                paint_ov = cv2.countNonZero(cv2.bitwise_and(comp, paint_excl_roi))
                if paint_ov > area * float(paint_overlap_max):
                    continue

            bbox_area = int(bw * bh)
            if bbox_area > 0:
                ink_in_bbox = ink[y : y + bh, x : x + bw]
                density = float(cv2.countNonZero(ink_in_bbox)) / float(bbox_area)
                if density < float(density_min):
                    continue

            result_roi[labels == lid] = 255
            merged.add(lid)
            added += 1

        if added == 0:
            break

    cok = max(1, int(clean_open_k))
    if cok % 2 == 0:
        cok += 1
    clean_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cok, cok))
    result_roi = cv2.morphologyEx(result_roi, cv2.MORPH_OPEN, clean_k, iterations=max(1, int(clean_open_iter)))
    cck = max(1, int(clean_close_k))
    if cck % 2 == 0:
        cck += 1
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cck, cck))
    result_roi = cv2.morphologyEx(result_roi, cv2.MORPH_CLOSE, close_k, iterations=max(1, int(clean_close_iter)))

    if paint_excl_roi is not None:
        result_roi = cv2.subtract(result_roi, paint_excl_roi)

    result = np.zeros((h, w), dtype=np.uint8)
    result[y1 : y2 + 1, x1 : x2 + 1] = result_roi

    try:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hch = hsv[:, :, 0]
        sch = hsv[:, :, 1]
        vch = hsv[:, :, 2]
        red1 = ((hch <= int(seal_h_max)) & (sch >= int(seal_s_min)) & (vch >= int(seal_v_min))).astype(np.uint8) * 255
        red2 = ((hch >= 165) & (sch >= int(seal_s_min)) & (vch >= int(seal_v_min))).astype(np.uint8) * 255
        cand = cv2.bitwise_or(red1, red2)
        if bool(seal_enable_green):
            green = (
                (hch >= int(seal_green_h_min))
                & (hch <= int(seal_green_h_max))
                & (sch >= int(seal_s_min))
                & (vch >= int(seal_v_min))
            ).astype(np.uint8) * 255
            cand = cv2.bitwise_or(cand, green)
        gate = np.zeros((h, w), dtype=np.uint8)
        gx1 = max(0, x1 - int(w * float(seal_gate_pad_ratio)))
        gy1 = max(0, y1 - int(h * float(seal_gate_pad_ratio)))
        gx2 = min(w - 1, x2 + int(w * float(seal_gate_pad_ratio)))
        gy2 = min(h - 1, y2 + int(h * float(seal_gate_pad_ratio)))
        gate[gy1 : gy2 + 1, gx1 : gx2 + 1] = 255
        cand = cv2.bitwise_and(cand, gate)
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, k3, iterations=1)
        k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, k7, iterations=2)
        if paint_mask is not None and paint_mask.shape[:2] == (h, w):
            cand = cv2.subtract(cand, paint_mask)
        num2, lab2, st2, cen2 = cv2.connectedComponentsWithStats(cand, connectivity=8)
        seal = np.zeros((h, w), dtype=np.uint8)
        for lid in range(1, num2):
            x, y, bw, bh, area = st2[lid]
            if area < int(seal_area_min) or area > int(seal_area_max):
                continue
            ar = float(bw) / float(max(bh, 1))
            if ar < float(seal_ar_min) or ar > float(seal_ar_max):
                continue
            m = lab2 == lid
            mean_s = float(np.mean(sch[m])) if np.any(m) else 0.0
            mean_v = float(np.mean(vch[m])) if np.any(m) else 255.0
            if mean_s < float(seal_mean_s_min) or mean_v > float(seal_mean_v_max):
                continue
            comp = (m.astype(np.uint8) * 255)
            contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            cnt = max(contours, key=cv2.contourArea)
            a = float(cv2.contourArea(cnt))
            if a <= 0.0:
                continue
            rect = float(a) / float(max(1.0, float(bw * bh)))
            hull = cv2.convexHull(cnt)
            ha = float(cv2.contourArea(hull)) if hull is not None else 0.0
            sol = float(a) / float(max(1.0, ha))
            if rect < float(seal_rect_min) or sol < float(seal_solidity_min):
                continue
            seal[m] = 255
        if cv2.countNonZero(seal) > 0:
            result = cv2.bitwise_or(result, seal)
        if debug_dir:
            _ensure_dir(debug_dir)
            cv2.imwrite(os.path.join(debug_dir, "seal_mask.png"), seal)
    except Exception:
        pass

    insc_pixels = int(cv2.countNonZero(result))
    total_pixels = int(w * h) if w > 0 and h > 0 else int(image_width * image_height)
    insc_percent = (insc_pixels / float(total_pixels) * 100.0) if total_pixels > 0 else 0.0

    if debug_dir:
        _ensure_dir(debug_dir)
        try:
            cv2.imwrite(os.path.join(debug_dir, "inscription_seed.png"), seed)
            cv2.imwrite(os.path.join(debug_dir, "inscription_mask.png"), result)
            overlay = _overlay_mask(img, result, (0, 0, 255), alpha=0.35)
            cv2.imwrite(os.path.join(debug_dir, "inscription_overlay.jpg"), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if paint_mask is not None:
                both = img.copy()
                paint_exclusive = paint_mask
                try:
                    if paint_mask.shape[:2] == result.shape[:2]:
                        paint_exclusive = cv2.subtract(paint_mask, result)
                except Exception:
                    paint_exclusive = paint_mask
                both = _overlay_mask(both, paint_exclusive, (255, 0, 0), alpha=0.28)
                both = _overlay_mask(both, result, (0, 0, 255), alpha=0.35)
                cv2.imwrite(os.path.join(debug_dir, "paint_and_inscription_overlay.jpg"), both, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        except Exception:
            pass

    out.update(
        {
            "ok": True,
            "inscription_pixels": insc_pixels,
            "inscription_percent": float(round(insc_percent, 2)),
            "seed_pixels": int(cv2.countNonZero(seed)),
            "components_total": int(num - 1),
            "components_merged": int(len(merged)),
        }
    )
    if return_mask:
        out["mask"] = result
    return out


def detect_inscription_grid_density(
    image_path: str,
    inscription_regions: List[Dict[str, Any]],
    image_width: int,
    image_height: int,
    expand_x_ratio: float = 0.22,
    expand_x_min: int = 48,
    expand_y_ratio: float = 0.10,
    density_thresh_core: float = 0.055,
    density_thresh_expand: float = 0.120,
    cell_size_min: int = 20,
    cell_size_divisor: int = 25,
    close_v_kx: int = 16,
    close_v_ky: int = 26,
    close_h_kx: int = 26,
    close_h_ky: int = 16,
    close_iters: int = 2,
    final_dilate_k: int = 19,
    final_smooth_k: int = 9,
    seal_h_max: int = 10,
    seal_s_min: int = 35,
    seal_v_min: int = 50,
    seal_v_max: int = 220,
    seal_area_min: int = 80,
    seal_area_max: int = 40000,
    seal_ar_min: float = 0.35,
    seal_ar_max: float = 3.0,
    seal_solidity_min: float = 0.45,
    seal_gate_ratio: float = 0.06,
    return_mask: bool = False,
    debug_dir: str | None = None,
) -> Dict[str, Any]:
    """
    网格密度法题跋检测 v4 — 只检测题跋占比，不区分绘画/留白。
    
    核心思路：
    1. LLM 多边形作为 ROI 种子
    2. 适度扩展 ROI 以捕获漏识别文字
    3. 网格密度分析：文字区域高密度，绘画线条低密度
    4. 双阈值：核心区（信任LLM）用低阈值，扩展区用高阈值
    5. 连通分量形态过滤：去除扇骨等细长线条
    6. 闭运算连接相邻字 → 整块题跋区域
    7. 印章检测补充
    """
    out: Dict[str, Any] = {"ok": False}
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        out["error"] = "image_read_failed"
        return out

    h, w = img.shape[:2]
    if image_width and image_height and (image_width != w or image_height != h):
        w = image_width
        h = image_height

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Step 1: LLM ROI
    llm_roi = _regions_seed_mask(inscription_regions, w, h)
    roi_px = cv2.countNonZero(llm_roi)
    if roi_px == 0:
        out["error"] = "no_inscription_seed"
        return out

    ys, xs = np.where(llm_roi > 0)
    rx1, rx2, ry1, ry2 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())

    # 扩展 ROI 以捕获 LLM 漏识别的题跋文字
    roi_w = max(rx2 - rx1, 1)
    roi_h = max(ry2 - ry1, 1)
    expand_x = max(int(roi_w * float(expand_x_ratio)), int(expand_x_min))
    expand_y = int(roi_h * float(expand_y_ratio))

    rx1, ry1 = max(0, rx1 - expand_x), max(0, ry1 - expand_y)
    rx2, ry2 = min(w - 1, rx2 + expand_x), min(h - 1, ry2 + expand_y)

    # Step 2: 墨迹检测（ROI内，不截断到LLM范围）
    gray_roi = gray[ry1:ry2 + 1, rx1:rx2 + 1]
    otsu_val, _ = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    sensitive = cv2.threshold(gray_roi, int(otsu_val * 0.78), 255, cv2.THRESH_BINARY_INV)[1]
    adaptive = cv2.adaptiveThreshold(gray_roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY_INV, 21, 12)
    ink_roi = cv2.bitwise_and(sensitive, adaptive)

    # LLM 原始区域的 crop（用于区分核心区 vs 扩展区）
    llm_crop = llm_roi[ry1:ry2 + 1, rx1:rx2 + 1]
    rh, rw = ink_roi.shape[:2]

    # Step 3: 网格密度分析
    cell_size = max(int(cell_size_min), min(rh, rw) // int(cell_size_divisor))
    nx = (rw + cell_size - 1) // cell_size
    ny = (rh + cell_size - 1) // cell_size

    # 构建核心区/扩展区 grid mask
    core_mask_grid = np.zeros((ny, nx), dtype=np.bool_)
    for cy in range(ny):
        for cx in range(nx):
            x1c = min(cx * cell_size, rw)
            x2c = min((cx + 1) * cell_size, rw)
            y1c = min(cy * cell_size, rh)
            y2c = min((cy + 1) * cell_size, rh)
            if cv2.countNonZero(llm_crop[y1c:y2c, x1c:x2c]) > 0:
                core_mask_grid[cy, cx] = True

    density_map = np.zeros((ny, nx), dtype=np.float32)
    for cy in range(ny):
        for cx in range(nx):
            x1c = min(cx * cell_size, rw)
            x2c = min((cx + 1) * cell_size, rw)
            y1c = min(cy * cell_size, rh)
            y2c = min((cy + 1) * cell_size, rh)
            cell = ink_roi[y1c:y2c, x1c:x2c]
            cell_area = max((x2c - x1c) * (y2c - y1c), 1)
            density_map[cy, cx] = float(cv2.countNonZero(cell)) / float(cell_area)

    # 平滑密度图
    density_map_u8 = (np.clip(density_map, 0, 1) * 255).astype(np.float32)
    smoothed = cv2.blur(density_map_u8, (3, 3))
    smoothed_density = (smoothed / 255.0).astype(np.float32)

    # 双阈值：核心区低阈值，扩展区高阈值
    text_cells_core = ((density_map > float(density_thresh_core)) |
                        (smoothed_density > float(density_thresh_core) * 0.7)) & core_mask_grid
    text_cells_expand = ((density_map > float(density_thresh_expand)) |
                          (smoothed_density > float(density_thresh_expand) * 0.7)) & (~core_mask_grid)
    text_cells = text_cells_core | text_cells_expand

    # 将 text_cells 映射回 mask（保留该格内实际墨迹，不是填满格子）
    text_mask = np.zeros_like(ink_roi)
    for cy in range(ny):
        for cx in range(nx):
            if text_cells[cy, cx]:
                x1c = min(cx * cell_size, rw)
                x2c = min((cx + 1) * cell_size, rw)
                y1c = min(cy * cell_size, rh)
                y2c = min((cy + 1) * cell_size, rh)
                text_mask[y1c:y2c, x1c:x2c] = cv2.bitwise_or(
                    text_mask[y1c:y2c, x1c:x2c],
                    ink_roi[y1c:y2c, x1c:x2c]
                )

    # Step 3.5: 连通分量方向性过滤
    num_cc, labels_cc, stats_cc, _ = cv2.connectedComponentsWithStats(text_mask, connectivity=8)
    refined_text = np.zeros_like(text_mask)
    total_ink_area = max(cv2.countNonZero(text_mask), 1)

    for lid in range(1, num_cc):
        area = stats_cc[lid, cv2.CC_STAT_AREA]
        if area < 50:
            continue
        bx = stats_cc[lid][cv2.CC_STAT_LEFT]
        by = stats_cc[lid][cv2.CC_STAT_TOP]
        bw = stats_cc[lid][cv2.CC_STAT_WIDTH]
        bh = stats_cc[lid][cv2.CC_STAT_HEIGHT]
        bbox_area = max(bw * bh, 1)
        solidity = float(area) / bbox_area

        # 过滤：极端长条形且低密度 → 扇骨等线条
        if bw > 80 and bh > 30 and solidity < 0.06:
            continue
        # 超大面积分量且低密度 → 大面积绘画
        if float(area) / total_ink_area > 0.15 and solidity < 0.05:
            continue
        # 窄长条 → 单根扇骨
        if (bw < 20 and bh > 100) or (bh < 20 and bw > 100):
            if solidity < 0.12:
                continue
        refined_text[labels_cc == lid] = 255

    # Step 4: 形态学闭运算连接相邻字
    k_close_v = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(close_v_kx), int(close_v_ky)))
    k_close_h = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(close_h_kx), int(close_h_ky)))
    text_conn = cv2.morphologyEx(refined_text, cv2.MORPH_CLOSE, k_close_v, iterations=int(close_iters))
    text_conn = cv2.bitwise_or(text_conn,
                                cv2.morphologyEx(refined_text, cv2.MORPH_CLOSE, k_close_h, iterations=int(close_iters)))
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    text_conn = cv2.morphologyEx(text_conn, cv2.MORPH_OPEN, k_open, iterations=1)

    # Step 5: 印章检测
    seal_final = np.zeros((h, w), dtype=np.uint8)
    try:
        h_ch = hsv[:, :, 0]
        s_ch = hsv[:, :, 1]
        v_ch = hsv[:, :, 2]
        red1 = ((h_ch <= int(seal_h_max)) & (s_ch >= int(seal_s_min)) &
                (v_ch >= int(seal_v_min)) & (v_ch <= int(seal_v_max))).astype(np.uint8) * 255
        red2 = ((h_ch >= 165) & (s_ch >= int(seal_s_min)) &
                (v_ch >= int(seal_v_min)) & (v_ch <= int(seal_v_max))).astype(np.uint8) * 255
        seal_raw = cv2.bitwise_or(red1, red2)
        seal_gate = np.zeros((h, w), dtype=np.uint8)
        gp = int(max(h, w) * float(seal_gate_ratio))
        seal_gate[max(0, ry1 - gp):min(h, ry2 + gp + 1), max(0, rx1 - gp):min(w, rx2 + gp + 1)] = 255
        seal_raw = cv2.bitwise_and(seal_raw, seal_gate)
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        seal_open = cv2.morphologyEx(seal_raw, cv2.MORPH_OPEN, k3, iterations=1)
        k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        seal_clean = cv2.morphologyEx(seal_open, cv2.MORPH_CLOSE, k7, iterations=2)

        ns, nl, st_, _ = cv2.connectedComponentsWithStats(seal_clean, connectivity=8)
        for lid in range(1, ns):
            sx, sy, sbw, sbh, sarea = st_[lid]
            if sarea < int(seal_area_min) or sarea > int(seal_area_max):
                continue
            sar = float(sbw) / max(sbh, 1)
            if sar < float(seal_ar_min) or sar > float(seal_ar_max):
                continue
            cm_ = (nl == lid).astype(np.uint8) * 255
            ct_, _ = cv2.findContours(cm_, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if ct_:
                c_ = max(ct_, key=cv2.contourArea)
                ha_ = cv2.contourArea(cv2.convexHull(c_))
                if ha_ > 0 and float(sarea) / ha_ >= float(seal_solidity_min):
                    seal_final[nl == lid] = 255
    except Exception:
        pass

    # Step 6: 合并 + 最终膨胀
    full_text = np.zeros((h, w), dtype=np.uint8)
    full_text[ry1:ry2 + 1, rx1:rx2 + 1] = text_conn
    combined = cv2.bitwise_or(full_text, seal_final)

    fk = max(3, int(final_dilate_k))
    if fk % 2 == 0:
        fk += 1
    final_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (fk, fk))
    final_mask = cv2.dilate(combined, final_k, iterations=1)
    sk = max(3, int(final_smooth_k))
    if sk % 2 == 0:
        sk += 1
    smooth_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sk, sk))
    final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, smooth_k, iterations=1)

    insc_pixels = int(cv2.countNonZero(final_mask))
    total_pixels = int(w * h) if w > 0 and h > 0 else int(image_width * image_height)
    insc_percent = (insc_pixels / float(total_pixels) * 100.0) if total_pixels > 0 else 0.0

    if debug_dir:
        _ensure_dir(debug_dir)
        try:
            # 密度图可视化
            density_vis = (np.clip(density_map / 0.15, 0, 1) * 255).astype(np.uint8)
            density_vis = cv2.resize(density_vis, (rw, rh), interpolation=cv2.INTER_NEAREST)
            cv2.imwrite(os.path.join(debug_dir, "grid_density.png"), density_vis)
            cv2.imwrite(os.path.join(debug_dir, "inscription_mask.png"), final_mask)
            overlay = _overlay_mask(img, final_mask, (0, 0, 255), alpha=0.35)
            cv2.imwrite(os.path.join(debug_dir, "inscription_overlay.jpg"), overlay,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        except Exception:
            pass

    out.update({
        "ok": True,
        "inscription_pixels": insc_pixels,
        "inscription_percent": float(round(insc_percent, 2)),
        "seed_pixels": int(roi_px),
        "method": "grid_density_v4",
    })
    if return_mask:
        out["mask"] = final_mask
    return out


def expand_paint_mask_with_edges(
    image_path: str,
    paint_mask: np.ndarray,
    exclude_mask: np.ndarray | None,
    pad_x_ratio: float = 0.18,
    pad_y_ratio: float = 0.12,
    right_ext_ratio: float = 0.42,
    x_margin_ratio: float = 0.15,
    bottom_cutoff_ratio: float = 0.10,
    edge_dilate_k: int = 5,
    edge_dilate_iter: int = 2,
    fan_close_k: int = 41,
    fan_close_iter: int = 2,
    max_fill_ratio: float = 0.35,
    min_edge_density: float = 0.012,
    adjacent_dilate_k: int = 13,
    bg_like_deltae: float = 10.0,
    bg_like_grad_max: float = 6.0,
    bg_like_max_ratio: float = 0.85,
    max_added_ratio_of_paint: float = 0.25,
    max_added_ratio_of_image: float = 0.12,
    debug_dir: str | None = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False}
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        out["error"] = "image_read_failed"
        return out

    h, w = img.shape[:2]
    if paint_mask is None or paint_mask.shape[:2] != (h, w):
        out["error"] = "invalid_paint_mask"
        return out

    ys, xs = np.where(paint_mask > 0)
    if xs.size == 0:
        out["error"] = "empty_paint_mask"
        return out

    px1, px2 = int(xs.min()), int(xs.max())
    py1, py2 = int(ys.min()), int(ys.max())

    pad_x = int(w * float(pad_x_ratio))
    pad_y = int(h * float(pad_y_ratio))
    x1 = max(0, px1 - pad_x)
    y1 = max(0, py1 - pad_y)
    x2 = min(w - 1, px2 + int(w * float(right_ext_ratio)))
    y2 = min(h - 1, py2 + pad_y)

    roi = img[y1 : y2 + 1, x1 : x2 + 1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    med = float(np.median(blur))
    lower = int(max(0, 0.66 * med))
    upper = int(min(255, 1.33 * med))
    edges = cv2.Canny(blur, lower, upper)

    k = max(1, int(edge_dilate_k))
    if k % 2 == 0:
        k += 1
    kd = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    edges = cv2.dilate(edges, kd, iterations=max(1, int(edge_dilate_iter)))

    if exclude_mask is not None and exclude_mask.shape[:2] == (h, w):
        ex = exclude_mask[y1 : y2 + 1, x1 : x2 + 1]
        edges = cv2.subtract(edges, ex)

    base_paint_roi = paint_mask[y1 : y2 + 1, x1 : x2 + 1]
    edges = cv2.subtract(edges, base_paint_roi)

    bg_like = None
    try:
        s = max(10, int(min(h, w) * 0.06))
        s = min(s, min(h, w) // 4) if min(h, w) >= 40 else s
        patches = [
            img[0:s, 0:s],
            img[0:s, w - s : w],
            img[h - s : h, 0:s],
            img[h - s : h, w - s : w],
        ]
        pts = np.concatenate([p.reshape(-1, 3) for p in patches if p is not None and p.size > 0], axis=0)
        bg_lab = cv2.cvtColor(pts.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
        bg_med = np.median(bg_lab, axis=0).astype(np.float32)
        roi_lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.float32)
        d0 = roi_lab[:, :, 0] - bg_med[0]
        d1 = roi_lab[:, :, 1] - bg_med[1]
        d2 = roi_lab[:, :, 2] - bg_med[2]
        delta = np.sqrt(d0 * d0 + d1 * d1 + d2 * d2)
        grad = cv2.Laplacian(gray, cv2.CV_16S, ksize=3)
        grad = np.abs(grad).astype(np.float32)
        bg_like = ((delta < float(bg_like_deltae)) & (grad < float(bg_like_grad_max))).astype(np.uint8) * 255
    except Exception:
        bg_like = None

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(edges, connectivity=8)
    if num <= 1:
        out["ok"] = True
        out["added_pixels"] = 0
        out["components_added"] = 0
        out["bbox"] = [x1, y1, x2, y2]
        return out

    added_mask_roi = np.zeros_like(edges)
    rejected_mask_roi = np.zeros_like(edges)
    components_added = 0
    hull_points: List[np.ndarray] = []
    fan_hull_points: List[np.ndarray] = []
    best_lid = 0
    best_area = 0
    roi_area = int(edges.shape[0] * edges.shape[1])
    adj_k = max(1, int(adjacent_dilate_k))
    if adj_k % 2 == 0:
        adj_k += 1
    adj_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (adj_k, adj_k))
    adjacent = cv2.dilate(base_paint_roi, adj_kernel, iterations=1)
    for lid in range(1, num):
        x, y, bw, bh, area = stats[lid]
        if area < 120:
            continue
        if bw < 10 or bh < 10:
            continue

        cx, cy = centroids[lid]
        global_cx = x1 + float(cx)
        global_cy = y1 + float(cy)
        gx1 = x1 + int(x)
        gx2 = gx1 + int(bw) - 1
        if global_cx < px1 - w * 0.05:
            continue
        if global_cx > px2 + w * 0.55:
            continue
        if global_cx < px2 - w * float(x_margin_ratio):
            continue
        if global_cy < py1 - h * 0.25 or global_cy > py2 + h * 0.25:
            continue
        if global_cy > py2 - h * float(bottom_cutoff_ratio):
            continue

        comp = (labels == lid).astype(np.uint8) * 255
        close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        comp_closed = cv2.morphologyEx(comp, cv2.MORPH_CLOSE, close_k, iterations=2)
        contours, _ = cv2.findContours(comp_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        filled = np.zeros_like(comp_closed)
        for cnt in contours:
            if cnt is None or len(cnt) < 3:
                continue
            hull = cv2.convexHull(cnt)
            cv2.drawContours(filled, [hull], -1, 255, thickness=-1)

        if exclude_mask is not None and exclude_mask.shape[:2] == (h, w):
            ex = exclude_mask[y1 : y2 + 1, x1 : x2 + 1]
            filled = cv2.subtract(filled, ex)

        filled_px = int(cv2.countNonZero(filled))
        if filled_px < 300:
            continue
        if filled_px > int(roi_area * float(max_fill_ratio)):
            rejected_mask_roi = cv2.bitwise_or(rejected_mask_roi, filled)
            continue
        if filled_px > int(area * 250):
            continue
        edge_inside = int(cv2.countNonZero(cv2.bitwise_and(edges, filled)))
        density = float(edge_inside) / float(max(1, filled_px))
        if density < float(min_edge_density):
            rejected_mask_roi = cv2.bitwise_or(rejected_mask_roi, filled)
            continue
        if bg_like is not None:
            bg_px = int(cv2.countNonZero(cv2.bitwise_and(bg_like, filled)))
            if float(bg_px) / float(max(1, filled_px)) > float(bg_like_max_ratio):
                rejected_mask_roi = cv2.bitwise_or(rejected_mask_roi, filled)
                continue
        if int(cv2.countNonZero(cv2.bitwise_and(adjacent, filled))) == 0:
            rejected_mask_roi = cv2.bitwise_or(rejected_mask_roi, filled)
            continue

        added_mask_roi = cv2.bitwise_or(added_mask_roi, filled)
        components_added += 1
        if int(area) > best_area:
            best_area = int(area)
            best_lid = int(lid)
        pts = np.column_stack(np.where(labels == lid))
        if pts.size > 0:
            hull_points.append(pts)
            if int(bw) >= 40 and int(bh) >= 40:
                ar = float(bw) / float(max(bh, 1))
                if 0.25 <= ar <= 4.5:
                    fan_hull_points.append(pts)


    if components_added == 0:
        out["ok"] = True
        out["added_pixels"] = 0
        out["components_added"] = 0
        out["bbox"] = [x1, y1, x2, y2]
        return out

    if fan_hull_points:
        try:
            pts_all = np.concatenate(fan_hull_points, axis=0)
            if pts_all.shape[0] >= 500:
                pts_xy = np.flip(pts_all, axis=1).astype(np.int32)
                hull = cv2.convexHull(pts_xy)
                hull_mask = np.zeros_like(edges)
                cv2.fillConvexPoly(hull_mask, hull, 255)
                if exclude_mask is not None and exclude_mask.shape[:2] == (h, w):
                    ex = exclude_mask[y1 : y2 + 1, x1 : x2 + 1]
                    hull_mask = cv2.subtract(hull_mask, ex)
                hull_px = int(cv2.countNonZero(hull_mask))
                x_min = int(np.min(pts_xy[:, 0])) if pts_xy.size else 0
                if hull_px >= 1500 and hull_px <= int(roi_area * float(max_fill_ratio)) and x_min >= int((px2 - x1) - w * 0.22):
                    edge_inside = int(cv2.countNonZero(cv2.bitwise_and(edges, hull_mask)))
                    density = float(edge_inside) / float(max(1, hull_px))
                    ok_bg = True
                    if bg_like is not None:
                        bg_px = int(cv2.countNonZero(cv2.bitwise_and(bg_like, hull_mask)))
                        ok_bg = float(bg_px) / float(max(1, hull_px)) <= float(bg_like_max_ratio)
                    if density >= float(min_edge_density) and ok_bg and int(cv2.countNonZero(cv2.bitwise_and(adjacent, hull_mask))) > 0:
                        added_mask_roi = cv2.bitwise_or(added_mask_roi, hull_mask)
                    else:
                        rejected_mask_roi = cv2.bitwise_or(rejected_mask_roi, hull_mask)
        except Exception:
            pass

    if best_lid:
        try:
            bx, by, bw, bh, _ = stats[best_lid]
            fan_edges = (labels == best_lid).astype(np.uint8) * 255
            fk = max(3, int(fan_close_k))
            if fk % 2 == 0:
                fk += 1
            close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (fk, fk))
            fan_closed = cv2.morphologyEx(fan_edges, cv2.MORPH_CLOSE, close_k, iterations=max(1, int(fan_close_iter)))
            contours, _ = cv2.findContours(fan_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                contours.sort(key=lambda c: cv2.contourArea(c), reverse=True)
                cnt = contours[0]
                filled = np.zeros_like(fan_closed)
                cv2.drawContours(filled, [cnt], -1, 255, thickness=-1)
                pad_x = int(bw * 0.25)
                pad_y = int(bh * 0.35)
                cx1 = max(0, int(bx) - pad_x)
                cy1 = max(0, int(by) - pad_y)
                cx2 = min(filled.shape[1] - 1, int(bx + bw - 1) + pad_x)
                cy2 = min(filled.shape[0] - 1, int(by + bh - 1) + pad_y)
                clip = np.zeros_like(filled)
                clip[cy1 : cy2 + 1, cx1 : cx2 + 1] = 255
                filled = cv2.bitwise_and(filled, clip)
                if exclude_mask is not None and exclude_mask.shape[:2] == (h, w):
                    ex = exclude_mask[y1 : y2 + 1, x1 : x2 + 1]
                    filled = cv2.subtract(filled, ex)
                filled_px = int(cv2.countNonZero(filled))
                if 1500 <= filled_px <= int(roi_area * float(max_fill_ratio)):
                    edge_inside = int(cv2.countNonZero(cv2.bitwise_and(edges, filled)))
                    density = float(edge_inside) / float(max(1, filled_px))
                    ok_bg = True
                    if bg_like is not None:
                        bg_px = int(cv2.countNonZero(cv2.bitwise_and(bg_like, filled)))
                        ok_bg = float(bg_px) / float(max(1, filled_px)) <= float(bg_like_max_ratio)
                    if density >= float(min_edge_density) and ok_bg and int(cv2.countNonZero(cv2.bitwise_and(adjacent, filled))) > 0:
                        added_mask_roi = cv2.bitwise_or(added_mask_roi, filled)
                    else:
                        rejected_mask_roi = cv2.bitwise_or(rejected_mask_roi, filled)
        except Exception:
            pass

    try:
        base_paint_px = int(cv2.countNonZero(paint_mask))
        added_roi_px = int(cv2.countNonZero(added_mask_roi))
        img_area = int(h * w)
        if img_area > 0 and base_paint_px > 0 and added_roi_px > 0:
            if float(added_roi_px) / float(base_paint_px) > float(max_added_ratio_of_paint) and float(added_roi_px) / float(img_area) > float(max_added_ratio_of_image):
                rejected_mask_roi = cv2.bitwise_or(rejected_mask_roi, added_mask_roi)
                added_mask_roi[:] = 0
                components_added = 0
    except Exception:
        pass

    out_mask = paint_mask.copy()
    out_mask[y1 : y2 + 1, x1 : x2 + 1] = cv2.bitwise_or(out_mask[y1 : y2 + 1, x1 : x2 + 1], added_mask_roi)
    if exclude_mask is not None and exclude_mask.shape[:2] == (h, w):
        out_mask = cv2.subtract(out_mask, exclude_mask)

    added_pixels = int(cv2.countNonZero(out_mask)) - int(cv2.countNonZero(paint_mask))
    if added_pixels < 0:
        added_pixels = 0

    if debug_dir:
        _ensure_dir(debug_dir)
        try:
            cv2.imwrite(os.path.join(debug_dir, "paint_edges_roi.png"), edges)
            cv2.imwrite(os.path.join(debug_dir, "paint_added_roi.png"), added_mask_roi)
            cv2.imwrite(os.path.join(debug_dir, "paint_added_roi_rejected.png"), rejected_mask_roi)
            if bg_like is not None:
                cv2.imwrite(os.path.join(debug_dir, "paint_expand_bg_like.png"), bg_like)
            cv2.imwrite(os.path.join(debug_dir, "paint_mask_expanded.png"), out_mask)
            overlay = _overlay_mask(img, out_mask, (255, 0, 0), alpha=0.35)
            cv2.imwrite(os.path.join(debug_dir, "paint_overlay_expanded.jpg"), overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if exclude_mask is not None and exclude_mask.shape[:2] == (h, w):
                both = img.copy()
                both = _overlay_mask(both, out_mask, (255, 0, 0), alpha=0.28)
                both = _overlay_mask(both, exclude_mask, (0, 0, 255), alpha=0.35)
                cv2.imwrite(os.path.join(debug_dir, "paint_and_inscription_overlay.jpg"), both, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        except Exception:
            pass

    out.update(
        {
            "ok": True,
            "added_pixels": int(added_pixels),
            "components_added": int(components_added),
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "mask": out_mask,
        }
    )
    return out
