"""
VL + CV 混合分割 — Shrink-to-Fit 策略 (Round 3-C)

核心思路：
1. VL 输出语义 bbox（已验证综合 IoU ~0.73）
2. CV 在 bbox 内找到实际内容的外接矩形
3. 适度膨胀保留文字/绘画周围的合理留白
4. 去除 bbox 内的大面积空白，提升 IoU

关键教训：
- 像素级精修（Otsu/纹理）会过度收紧，丢失 GT 中的留白区域
- shrink-to-fit 只收缩边界，不改变内部结构，更符合 GT 标注习惯
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple


def _get_bbox_roi(img: np.ndarray, bbox: Dict) -> Tuple[np.ndarray, int, int, int, int]:
    """从 bbox 裁剪 ROI"""
    h, w = img.shape[:2]
    x0 = max(0, int(bbox["x1"] * w))
    y0 = max(0, int(bbox["y1"] * h))
    x1 = min(w, int(bbox["x2"] * w))
    y1 = min(h, int(bbox["y2"] * h))

    if x1 <= x0 or y1 <= y0:
        return None, x0, y0, x1, y1

    roi = img[y0:y1, x0:x1]
    return roi, x0, y0, x1, y1


def _estimate_paper_lightness(gray_roi: np.ndarray) -> float:
    """估计纸张底色亮度：取最亮的 10% 像素的中位数"""
    flat = gray_roi.flatten()
    top_10_percent = np.percentile(flat, 90)
    paper_pixels = flat[flat >= top_10_percent * 0.95]
    if len(paper_pixels) == 0:
        return float(np.max(flat))
    return float(np.median(paper_pixels))


def shrink_to_fit(
    img_bgr: np.ndarray,
    bbox: Dict,
    shrink_for: str = "inscription",
    min_content_ratio: float = 0.50,
) -> Dict:
    """
    在 bbox 内收缩到实际内容的外接矩形 + 适度膨胀

    参数:
        img_bgr: 原图
        bbox: 原 bbox {"x1","y1","x2","y2"}
        shrink_for: "inscription" 或 "painting"
        min_content_ratio: 收缩后面积 < 原面积 * ratio 时回退到原 bbox

    返回:
        新 bbox {"x1","y1","x2","y2","note"}
    """
    h, w = img_bgr.shape[:2]
    roi, x0, y0, x1, y1 = _get_bbox_roi(img_bgr, bbox)
    if roi is None or roi.size == 0:
        return bbox

    rh, rw = roi.shape[:2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # 1. 估计纸张底色
    paper_light = _estimate_paper_lightness(gray)

    # 2. 宽松阈值找内容
    # 题跋：墨迹通常比纸张暗 15-40 灰度级
    # 绘画：墨迹+着色可能比纸张暗 10-30，淡墨可能只暗 5-15
    if shrink_for == "inscription":
        threshold = max(paper_light - 40, paper_light * 0.65)
    else:
        threshold = max(paper_light - 35, paper_light * 0.70)

    _, content_mask = cv2.threshold(gray, int(threshold), 255, cv2.THRESH_BINARY_INV)

    # 3. 对于绘画，额外加纹理通道（捕获淡墨渲染）
    if shrink_for == "painting":
        laplacian = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))
        tex_median = np.median(laplacian)
        tex_mask = (laplacian > tex_median * 0.6).astype(np.uint8) * 255
        content_mask = cv2.bitwise_or(content_mask, tex_mask)

    # 4. 轻微开运算去噪（2px）
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    content_mask = cv2.morphologyEx(content_mask, cv2.MORPH_OPEN, kernel)

    # 5. 找到非零像素的外接矩形
    ys, xs = np.where(content_mask > 0)
    if len(xs) == 0:
        # 没找到内容（可能是全淡墨），保持原 bbox
        return bbox

    cx0, cy0 = int(xs.min()), int(ys.min())
    cx1, cy1 = int(xs.max()) + 1, int(ys.max()) + 1

    # 6. 适度膨胀（保留文字/绘画周围的合理留白）
    if shrink_for == "inscription":
        # 题跋：左右多留（行间距），上下少留（字间距）
        pad_x = int(rw * 0.06) + 12
        pad_y = int(rh * 0.04) + 8
    else:
        # 绘画：各向均匀膨胀
        pad_x = int(rw * 0.05) + 15
        pad_y = int(rh * 0.05) + 15

    cx0 = max(0, cx0 - pad_x)
    cy0 = max(0, cy0 - pad_y)
    cx1 = min(rw, cx1 + pad_x)
    cy1 = min(rh, cy1 + pad_y)

    # 7. 面积回退检查
    new_area = (cx1 - cx0) * (cy1 - cy0)
    orig_area = rw * rh
    area_ratio = new_area / orig_area if orig_area > 0 else 1.0

    if area_ratio < min_content_ratio:
        # 收缩过度，可能是淡墨内容被漏掉，回退到原 bbox
        return bbox

    # 8. 转回相对坐标
    new_bbox = {
        "x1": (x0 + cx0) / w,
        "y1": (y0 + cy0) / h,
        "x2": (x0 + cx1) / w,
        "y2": (y0 + cy1) / h,
    }
    # 保留原 note
    if "note" in bbox:
        new_bbox["note"] = bbox["note"]

    return new_bbox


def apply_shrink_to_fit(
    img_bgr: np.ndarray,
    insc_bboxes: List[Dict],
    paint_bboxes: List[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    """
    对所有 bbox 应用 shrink-to-fit

    返回: (shrinked_insc_bboxes, shrinked_paint_bboxes)
    """
    new_insc = [shrink_to_fit(img_bgr, b, "inscription") for b in insc_bboxes]
    new_paint = [shrink_to_fit(img_bgr, b, "painting") for b in paint_bboxes]
    return new_insc, new_paint


# 保留旧接口兼容性
refine_inscription_mask = None
refine_painting_mask = None
bbox_to_refined_polygons = None


def run_hybrid_segmentation(
    image_path: str,
    vl_insc_bboxes: List[Dict],
    vl_paint_bboxes: List[Dict],
) -> Dict:
    """
    执行 VL + CV Shrink-to-Fit 混合分割

    返回: {
        "inscription_mask": np.ndarray,
        "painting_mask": np.ndarray,
        "inscription_regions": [{"x1","y1","x2","y2"}],
        "painting_regions": [{"x1","y1","x2","y2"}],
    }
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    h, w = img.shape[:2]

    # 1. Shrink-to-fit 收缩 bbox
    shrinked_insc, shrinked_paint = apply_shrink_to_fit(img, vl_insc_bboxes, vl_paint_bboxes)

    # 2. 收缩后的 bbox 转 mask
    def _bboxes_to_mask(bboxes, w, h):
        mask = np.zeros((h, w), dtype=np.uint8)
        for b in bboxes:
            x0 = max(0, int(b["x1"] * w))
            y0 = max(0, int(b["y1"] * h))
            x1 = min(w, int(b["x2"] * w))
            y1 = min(h, int(b["y2"] * h))
            if x1 > x0 and y1 > y0:
                mask[y0:y1, x0:x1] = 255
        return mask

    insc_mask = _bboxes_to_mask(shrinked_insc, w, h)
    paint_mask = _bboxes_to_mask(shrinked_paint, w, h)

    # 3. 解决重叠：题跋优先
    overlap = (insc_mask > 0) & (paint_mask > 0)
    paint_mask[overlap] = 0

    # 4. 重新计算 shrinked bbox（去重叠后可能变化，但这里简单处理：保持 shrinked）
    # 实际上去重叠后 paint 区域变小了，但 bbox 不变，这是可以接受的近似

    return {
        "inscription_mask": insc_mask,
        "painting_mask": paint_mask,
        "inscription_regions": shrinked_insc,
        "painting_regions": shrinked_paint,
    }
