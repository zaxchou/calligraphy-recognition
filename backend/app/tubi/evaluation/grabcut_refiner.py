"""
VL Polygon/BBox + GrabCut 边界精修模块 (方案A)

核心思路：
1. 自适应选择：规则矩形（矩形度>0.85）用BBox，不规则用Polygon
2. GrabCut精修：在VL输出区域内运行GrabCut，让边界精确贴合实际内容边缘
3. 输出优化后的多边形顶点

与之前shrink-to-fit的区别：
- shrink-to-fit是"收缩到内容外接矩形"，还是矩形
- grabcut是"精确贴合内容轮廓"，输出多边形
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional


def compute_rectangularity(points: List[Dict]) -> float:
    """
    计算多边形的矩形度 = 多边形面积 / 最小外接矩形面积
    
    返回值：0~1，越接近1越像矩形
    """
    if len(points) < 3:
        return 0.0
    
    pts = np.array([[p["x"], p["y"]] for p in points], dtype=np.float32)
    
    # 最小外接矩形（考虑旋转）
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect)
    
    # 多边形面积
    poly_area = cv2.contourArea(pts)
    # 外接矩形面积
    rect_area = cv2.contourArea(box)
    
    if rect_area <= 0:
        return 0.0
    
    return float(poly_area / rect_area)


def polygon_to_bbox(points: List[Dict]) -> Dict:
    """将多边形points转bbox格式"""
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    return {
        "x1": min(xs), "y1": min(ys),
        "x2": max(xs), "y2": max(ys),
    }


def _region_to_mask(region: Dict, width: int, height: int) -> np.ndarray:
    """将单个region（polygon或bbox）转为mask"""
    mask = np.zeros((height, width), dtype=np.uint8)
    
    if "points" in region and region["points"]:
        pts = []
        for pt in region["points"]:
            px = int(pt.get("x", 0) * width)
            py = int(pt.get("y", 0) * height)
            px = max(0, min(width - 1, px))
            py = max(0, min(height - 1, py))
            pts.append([px, py])
        if len(pts) >= 3:
            cv2.fillPoly(mask, [np.array(pts, dtype=np.int32)], 255)
    elif "x1" in region:
        x1 = int(region["x1"] * width)
        y1 = int(region["y1"] * height)
        x2 = int(region["x2"] * width)
        y2 = int(region["y2"] * height)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255
    
    return mask


def _mask_to_polygon(mask: np.ndarray, width: int, height: int) -> Optional[List[Dict]]:
    """将mask转回多边形points（相对坐标）"""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    
    # 取最大轮廓
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < 100:
        return None
    
    # 简化轮廓
    peri = cv2.arcLength(largest, True)
    epsilon = max(0.5, peri * 0.005)  # 比integration.py更激进，减少顶点数
    approx = cv2.approxPolyDP(largest, epsilon, True)
    
    if len(approx) < 3:
        return None
    
    points = []
    for pt in approx.reshape(-1, 2):
        points.append({
            "x": round(float(pt[0]) / width, 4),
            "y": round(float(pt[1]) / height, 4),
        })
    
    return points


def adaptive_select_shape(region: Dict, img_width: int, img_height: int) -> Dict:
    """
    自适应选择：检测region的矩形度，规则形状回退到bbox
    
    返回：优化后的region（可能替换points为x1,y1,x2,y2）
    """
    # 如果本身就是bbox，直接返回
    if "x1" in region and "points" not in region:
        return region
    
    # 如果有多边形points，计算矩形度
    if "points" in region and region["points"]:
        rect = compute_rectangularity(region["points"])
        
        # 矩形度 > 0.85：接近矩形，用bbox更稳定
        if rect > 0.85:
            bbox = polygon_to_bbox(region["points"])
            new_region = dict(region)
            new_region.update(bbox)
            del new_region["points"]
            new_region["_rectangularity"] = round(rect, 3)
            new_region["_shape_adapted"] = "bbox"
            return new_region
        else:
            # 不规则形状，保留多边形
            new_region = dict(region)
            new_region["_rectangularity"] = round(rect, 3)
            new_region["_shape_adapted"] = "polygon"
            return new_region
    
    return region


def grabcut_refiner(
    img_bgr: np.ndarray,
    region: Dict,
    region_type: str = "inscription",
    padding_ratio: float = 0.15,
    iter_count: int = 5,
) -> Optional[Dict]:
    """
    对单个region运行GrabCut精修

    参数:
        img_bgr: 原图 (H, W, 3)
        region: VL输出的region（polygon或bbox）
        region_type: "inscription" 或 "painting"
        padding_ratio: ROI扩展比例（相对region尺寸）
        iter_count: GrabCut迭代次数
    
    返回:
        优化后的region（多边形points格式），失败返回None
    """
    h, w = img_bgr.shape[:2]
    
    # 1. 自适应选择形状
    region = adaptive_select_shape(region, w, h)
    
    # 2. 获取region的bbox（用于crop ROI）
    if "x1" in region:
        rx1 = int(region["x1"] * w)
        ry1 = int(region["y1"] * h)
        rx2 = int(region["x2"] * w)
        ry2 = int(region["y2"] * h)
    else:
        # 从points计算bbox
        xs = [int(p["x"] * w) for p in region["points"]]
        ys = [int(p["y"] * h) for p in region["points"]]
        rx1, rx2 = min(xs), max(xs)
        ry1, ry2 = min(ys), max(ys)
    
    rx1, ry1 = max(0, rx1), max(0, ry1)
    rx2, ry2 = min(w, rx2), min(h, ry2)
    
    if rx2 <= rx1 or ry2 <= ry1:
        return None
    
    rw, rh = rx2 - rx1, ry2 - ry1
    
    # 3. 扩展padding crop ROI
    pad_x = int(rw * padding_ratio)
    pad_y = int(rh * padding_ratio)
    
    cx1 = max(0, rx1 - pad_x)
    cy1 = max(0, ry1 - pad_y)
    cx2 = min(w, rx2 + pad_x)
    cy2 = min(h, ry2 + pad_y)
    
    roi = img_bgr[cy1:cy2, cx1:cx2]
    roi_h, roi_w = roi.shape[:2]
    
    if roi_h < 10 or roi_w < 10:
        return None
    
    # 4. 构建GrabCut初始mask
    # GC_BGD = 0 (背景), GC_FGD = 1 (前景), GC_PR_BGD = 2 (可能背景), GC_PR_FGD = 3 (可能前景)
    gc_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
    
    # 将VL区域映射到ROI坐标
    vx1 = rx1 - cx1
    vy1 = ry1 - cy1
    vx2 = rx2 - cx1
    vy2 = ry2 - cy1
    
    # 创建VL区域的精确mask
    vl_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
    if "points" in region and region["points"]:
        # 多边形
        pts = []
        for pt in region["points"]:
            px = int(pt["x"] * w) - cx1
            py = int(pt["y"] * h) - cy1
            px = max(0, min(roi_w - 1, px))
            py = max(0, min(roi_h - 1, py))
            pts.append([px, py])
        if len(pts) >= 3:
            cv2.fillPoly(vl_mask, [np.array(pts, dtype=np.int32)], 255)
    else:
        # Bbox
        vl_mask[vy1:vy2, vx1:vx2] = 255
    
    # 5. 设置GrabCut mask
    # 策略：VL区域内 = PR_FGD(3)，VL区域外 = PR_BGD(2)
    # 但区域边缘留一定buffer为PR_BGD，让GrabCut有优化空间
    
    # 用距离变换创建边缘buffer
    kernel = np.ones((5, 5), np.uint8)
    vl_eroded = cv2.erode(vl_mask, kernel, iterations=1)
    vl_dilated = cv2.dilate(vl_mask, kernel, iterations=1)
    
    gc_mask[vl_eroded > 0] = cv2.GC_FGD      # 内部 = 确定前景
    gc_mask[(vl_mask > 0) & (vl_eroded == 0)] = cv2.GC_PR_FGD  # 边缘 = 可能前景
    gc_mask[(vl_dilated == 0)] = cv2.GC_PR_BGD  # 外部 = 可能背景
    gc_mask[(vl_dilated > 0) & (vl_mask == 0)] = cv2.GC_PR_BGD  # 膨胀边缘外 = 可能背景
    
    # 6. 根据类型调整阈值策略
    if region_type == "inscription":
        # 题跋：文字与纸张对比度通常较高，GrabCut容易收敛
        # 不需要特殊处理
        pass
    else:
        # 绘画：可能有淡墨渲染，对比度低
        # 增加迭代次数
        iter_count = max(iter_count, 7)
    
    # 7. 运行GrabCut
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    
    try:
        cv2.grabCut(roi, gc_mask, None, bgd_model, fgd_model, iter_count, cv2.GC_INIT_WITH_MASK)
    except cv2.error as e:
        print(f"WARNING: GrabCut failed: {e}")
        return None
    
    # 8. 提取前景mask
    refined_mask = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    
    # 9. 后处理：去除小碎片
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    refined_mask = cv2.morphologyEx(refined_mask, cv2.MORPH_OPEN, kernel_clean)
    
    # 10. 转回多边形
    poly_points = _mask_to_polygon(refined_mask, roi_w, roi_h)
    if poly_points is None:
        return None
    
    # 将ROI坐标映射回原图坐标
    final_points = []
    for pt in poly_points:
        final_points.append({
            "x": round((pt["x"] * roi_w + cx1) / w, 4),
            "y": round((pt["y"] * roi_h + cy1) / h, 4),
        })
    
    # 11. 构建返回region
    refined_region = {
        "points": final_points,
        "note": region.get("note", "") + f" [GrabCut refined, shape={region.get('_shape_adapted', 'original')}]",
        "_original": dict(region),
    }
    
    return refined_region


def refine_regions(
    img_bgr: np.ndarray,
    inscription_regions: List[Dict],
    painting_regions: List[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    """
    对所有region运行GrabCut精修
    
    返回: (refined_inscription_regions, refined_painting_regions)
    """
    refined_insc = []
    for i, region in enumerate(inscription_regions):
        print(f"  Refining inscription {i+1}/{len(inscription_regions)}...")
        refined = grabcut_refiner(img_bgr, region, "inscription")
        if refined:
            refined_insc.append(refined)
            print(f"    -> {len(refined['points'])} vertices")
        else:
            # 精修失败，保留原始
            refined_insc.append(region)
            print(f"    -> failed, keeping original")
    
    refined_paint = []
    for i, region in enumerate(painting_regions):
        print(f"  Refining painting {i+1}/{len(painting_regions)}...")
        refined = grabcut_refiner(img_bgr, region, "painting")
        if refined:
            refined_paint.append(refined)
            print(f"    -> {len(refined['points'])} vertices")
        else:
            refined_paint.append(region)
            print(f"    -> failed, keeping original")
    
    return refined_insc, refined_paint


def run_grabcut_refinement(
    image_path: str,
    vl_insc_regions: List[Dict],
    vl_paint_regions: List[Dict],
) -> Dict:
    """
    主入口：对VL输出运行完整的GrabCut精修流程
    
    返回: {
        "inscription_regions": [...],  # 精修后的多边形
        "painting_regions": [...],
        "inscription_mask": np.ndarray,
        "painting_mask": np.ndarray,
    }
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")
    
    h, w = img.shape[:2]
    
    # 精修
    refined_insc, refined_paint = refine_regions(img, vl_insc_regions, vl_paint_regions)
    
    # 转mask
    insc_mask = np.zeros((h, w), dtype=np.uint8)
    paint_mask = np.zeros((h, w), dtype=np.uint8)
    
    for r in refined_insc:
        if "points" in r:
            pts = []
            for pt in r["points"]:
                px = int(pt["x"] * w)
                py = int(pt["y"] * h)
                pts.append([px, py])
            if len(pts) >= 3:
                cv2.fillPoly(insc_mask, [np.array(pts, dtype=np.int32)], 255)
    
    for r in refined_paint:
        if "points" in r:
            pts = []
            for pt in r["points"]:
                px = int(pt["x"] * w)
                py = int(pt["y"] * h)
                pts.append([px, py])
            if len(pts) >= 3:
                cv2.fillPoly(paint_mask, [np.array(pts, dtype=np.int32)], 255)
    
    # 解决重叠：题跋优先
    overlap = (insc_mask > 0) & (paint_mask > 0)
    paint_mask[overlap] = 0
    
    return {
        "inscription_regions": refined_insc,
        "painting_regions": refined_paint,
        "inscription_mask": insc_mask,
        "painting_mask": paint_mask,
    }
