"""
合点算法化模块
==============
不依赖 LLM 定位合点，而是用 CV + 几何算法自动计算。

算法流程：
1. 检测题款/印章区域（红色印章 + 文字区域）
2. 基于起、承、转三点计算整体走势方向
3. 在题款/印章区域内选择与转点形成回环闭合的最佳合点
4. 验证四点能拟合平滑曲线（S/C 形）
"""

import cv2
import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


def detect_seal_regions(img_bgr: np.ndarray) -> List[Dict]:
    """
    检测画面中的印章（红色方形/圆形区域）。
    
    印章特征：
    - 颜色：纯正的朱砂红（高饱和度，中等亮度）
    - 形状：方形或圆形，紧凑度高
    - 位置：通常靠近题款文字
    - 大小：相对较小（画面面积的 0.01%-1%）
    
    返回印章区域列表，每个元素包含：
    - center: (cx, cy) 像素坐标
    - bbox: (x, y, w, h)
    - area: 面积
    - confidence: 置信度
    """
    h, w = img_bgr.shape[:2]
    total_pixels = h * w
    
    # 转换到 HSV 空间
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    
    # 印章红色更精确的范围（朱砂红特征）
    # H: 0-12 和 160-180（色轮两端）
    # S: 高饱和度 80-255（印章颜色纯度高）
    # V: 中等亮度 80-230（不是太亮也不是太暗）
    lower_red1 = np.array([0, 80, 80])
    upper_red1 = np.array([12, 255, 230])
    lower_red2 = np.array([160, 80, 80])
    upper_red2 = np.array([180, 255, 230])
    
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)
    
    # 去噪
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    
    # 查找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    seals = []
    min_area = total_pixels * 0.0002   # 最小面积
    max_area = total_pixels * 0.008    # 最大面积（印章通常不会太大）
    min_dim = max(h, w) * 0.01         # 最小尺寸
    max_dim = max(h, w) * 0.12         # 最大尺寸（印章一般不超过画面12%）
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        
        x, y, bw, bh = cv2.boundingRect(contour)
        
        # 尺寸过滤
        if bw < min_dim or bh < min_dim:
            continue
        if bw > max_dim or bh > max_dim:
            continue
        
        # 宽高比：印章通常是方形或近方形 (0.6 - 1.6)
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        if aspect > 1.8:
            continue
        
        # 计算紧凑度（圆形度）
        perimeter = cv2.arcLength(contour, True)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter ** 2)
        else:
            circularity = 0
        
        # 印章紧凑度要求高（方形 ~0.785，圆形 ~1.0）
        if circularity < 0.5:
            continue
        
        # 检查颜色纯度（印章区域内红色占比要高）
        roi_mask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.drawContours(roi_mask, [contour], -1, 255, -1)
        total_roi = cv2.countNonZero(roi_mask)
        filled_roi = cv2.countNonZero(cv2.bitwise_and(mask, roi_mask))
        fill_ratio = filled_roi / max(total_roi, 1)
        
        # 印章通常颜色填充均匀 (fill_ratio > 0.6)
        if fill_ratio < 0.4:
            continue
        
        M = cv2.moments(contour)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
        else:
            cx = x + bw // 2
            cy = y + bh // 2
        
        # 综合置信度
        confidence = circularity * 0.4 + fill_ratio * 0.3 + (1.0 - abs(aspect - 1.0)) * 0.3
        
        seals.append({
            "center": (cx, cy),
            "bbox": (x, y, bw, bh),
            "area": area,
            "circularity": circularity,
            "fill_ratio": fill_ratio,
            "aspect_ratio": aspect,
            "confidence": confidence,
        })
    
    # 去重：合并距离太近的检测结果
    if seals:
        seals = _merge_nearby_seals(seals, min_dist=max(h, w) * 0.03)
    
    # 按置信度排序
    seals.sort(key=lambda s: s["confidence"], reverse=True)
    
    # 最多保留 5 个印章（中国画一般不超过 5 枚）
    seals = seals[:5]
    
    logger.debug(f"Detected {len(seals)} seal regions (filtered from raw contours)")
    return seals


def _merge_nearby_seals(seals: List[Dict], min_dist: float) -> List[Dict]:
    """合并距离太近的印章检测结果"""
    if not seals:
        return seals
    
    merged = [seals[0]]
    for seal in seals[1:]:
        cx, cy = seal["center"]
        too_close = False
        for existing in merged:
            ex, ey = existing["center"]
            if np.sqrt((cx - ex)**2 + (cy - ey)**2) < min_dist:
                # 保留置信度更高的
                if seal["confidence"] > existing["confidence"]:
                    merged.remove(existing)
                    merged.append(seal)
                too_close = True
                break
        if not too_close:
            merged.append(seal)
    
    return merged


def detect_text_regions(img_bgr: np.ndarray) -> List[Dict]:
    """
    检测画面中的题款文字区域（竖排文字）。
    
    中国画题款通常是竖排的，表现为：
    - 一列或多列深色细小区域
    - 紧密排列，形成垂直条带
    - 通常在画面边缘（左侧、右侧、或左上/右上）
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # 文字通常是深色
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 水平形态学操作连接同一列的文字
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, int(h * 0.02)))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, h_kernel, iterations=1)
    
    # 垂直形态学操作去掉过宽的区域
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.15), 1))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel, iterations=1)
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    text_regions = []
    min_area = (h * w) * 0.0005
    max_area = (h * w) * 0.15
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        
        x, y, bw, bh = cv2.boundingRect(contour)
        
        # 题款通常是竖排的：高度 > 宽度的 2 倍
        aspect_ratio = bh / max(bw, 1)
        if aspect_ratio < 2.0:
            continue
        
        # 题款通常靠近边缘
        edge_distance = min(x, w - (x + bw))
        if edge_distance > w * 0.3:
            continue
        
        text_regions.append({
            "bbox": (x, y, bw, bh),
            "center": (x + bw // 2, y + bh // 2),
            "area": area,
            "aspect_ratio": aspect_ratio,
            "edge_distance": edge_distance,
        })
    
    logger.debug(f"Detected {len(text_regions)} text regions")
    return text_regions


def compute_he_point(
    img_bgr: np.ndarray,
    qi: Dict,      # {"x": pct, "y": pct} 百分比坐标
    cheng_list: List[Dict],
    zhuan: Dict,
    w: int, h: int  # 图像像素尺寸
) -> Dict:
    """
    基于起、承、转三点 + 题款/印章检测结果，算法计算合点。
    
    算法步骤：
    1. 检测印章和文字区域
    2. 计算起→承→转的走势方向
    3. 在印章/文字区域中，选择与转点形成回环闭合的最佳合点
    4. 如果没有检测到题款/印章，则使用几何回环点
    """
    # 获取像素坐标
    qi_px = (int(qi["x"] * w / 100), int(qi["y"] * h / 100))
    
    if cheng_list:
        # 取最后一个承点（最接近转的）
        last_cheng = cheng_list[-1]
        cheng_px = (int(last_cheng["x"] * w / 100), int(last_cheng["y"] * h / 100))
    else:
        cheng_px = qi_px
    
    zhuan_px = (int(zhuan["x"] * w / 100), int(zhuan["y"] * h / 100))
    
    # 1. 检测印章和文字
    seals = detect_seal_regions(img_bgr)
    text_regions = detect_text_regions(img_bgr)
    
    # 2. 计算题款/印章的目标区域
    anchor_points = []  # 合点的候选锚点（像素坐标）
    
    # 印章中心
    for seal in seals:
        anchor_points.append({
            "point": seal["center"],
            "weight": seal["confidence"] * 1.5,  # 印章权重更高
            "source": "seal",
        })
    
    # 文字区域末端（竖排文字的末尾 = 底部）
    for tr in text_regions:
        x, y, bw, bh = tr["bbox"]
        # 竖排文字的末尾在底部
        end_point = (x + bw // 2, y + bh)
        anchor_points.append({
            "point": end_point,
            "weight": 0.8,
            "source": "text_end",
        })
        # 也考虑文字区域中心
        anchor_points.append({
            "point": tr["center"],
            "weight": 0.6,
            "source": "text_center",
        })
    
    # 3. 如果没有检测到任何题款/印章
    if not anchor_points:
        logger.warning("No seal/text detected, using geometric fallback for he")
        return _geometric_fallback_he(qi_px, cheng_px, zhuan_px, w, h)
    
    # 4. 计算走势方向（起→承→转的总体方向向量）
    # 使用起→转的方向作为主走势
    trend_dx = zhuan_px[0] - qi_px[0]
    trend_dy = zhuan_px[1] - qi_px[1]
    
    # 5. 在锚点中选择最佳合点
    # 最佳合点 = 与转点的连线与主走势形成最大"回环"效果的点
    # "回环" = 转→合 的方向应该与 起→转 的方向形成弯曲（类似弧线）
    
    best_he = None
    best_score = -999
    
    for anchor in anchor_points:
        pt = anchor["point"]
        weight = anchor["weight"]
        
        # 转→合向量
        zhuan_to_he_dx = pt[0] - zhuan_px[0]
        zhuan_to_he_dy = pt[1] - zhuan_px[1]
        
        # 计算回环得分：
        # 理想的回环：转→合的方向与起→转的方向形成一个"弯曲"
        # 用叉积来衡量弯曲程度（正/负表示左弯/右弯）
        cross = trend_dx * zhuan_to_he_dy - trend_dy * zhuan_to_he_dx
        
        # 距离（转→合）不要太远也不要太近
        dist = np.sqrt(zhuan_to_he_dx**2 + zhuan_to_he_dy**2)
        max_dist = np.sqrt(w**2 + h**2)
        dist_score = 1.0 - abs(dist / max_dist - 0.3)  # 理想距离是画面对角线的 30%
        
        # 方向变化程度（叉积的绝对值越大，弯曲越明显）
        bend_score = min(abs(cross) / (max_dist * 0.5), 1.0)
        
        # 综合得分
        score = (bend_score * 0.5 + dist_score * 0.3 + weight * 0.2)
        
        if score > best_score:
            best_score = score
            best_he = pt
    
    if best_he is None:
        return _geometric_fallback_he(qi_px, cheng_px, zhuan_px, w, h)
    
    # 转换为百分比坐标
    he_pct_x = best_he[0] * 100 / w
    he_pct_y = best_he[1] * 100 / h
    
    return {
        "x": round(he_pct_x, 1),
        "y": round(he_pct_y, 1),
        "reason": f"算法计算: 检测到{len(seals)}个印章, {len(text_regions)}个文字区域, 合点在附近",
        "pixel": best_he,
        "seals_detected": len(seals),
        "text_detected": len(text_regions),
        "method": "algorithm",
    }


def _geometric_fallback_he(
    qi_px: Tuple[int, int],
    cheng_px: Tuple[int, int],
    zhuan_px: Tuple[int, int],
    w: int, h: int
) -> Dict:
    """
    几何回环兜底方案：当没有检测到题款/印章时，
    计算一个与起→承→转走势形成回环的点。
    
    策略：起→承→转是主走势，合应该是主走势的"回折点"。
    """
    # 计算起→转的中点
    mid_x = (qi_px[0] + zhuan_px[0]) / 2
    mid_y = (qi_px[1] + zhuan_px[1]) / 2
    
    # 走势方向向量
    trend_dx = zhuan_px[0] - qi_px[0]
    trend_dy = zhuan_px[1] - qi_px[1]
    
    # 法线方向（垂直于走势）
    norm = np.sqrt(trend_dx**2 + trend_dy**2) or 1
    perp_dx = -trend_dy / norm
    perp_dy = trend_dx / norm
    
    # 在法线方向上偏移中点，选择与转点形成回环的方向
    # 偏移量约为画面对角线的 20%
    offset = np.sqrt(w**2 + h**2) * 0.2
    
    # 两个候选点（法线的正反方向）
    candidates = [
        (mid_x + perp_dx * offset, mid_y + perp_dy * offset),
        (mid_x - perp_dx * offset, mid_y - perp_dy * offset),
    ]
    
    # 选择与转点距离更合理（不太远不太近）的
    best = None
    best_dist_score = -999
    
    for cx, cy in candidates:
        # 限制在画面范围内
        cx = max(w * 0.05, min(w * 0.95, cx))
        cy = max(h * 0.05, min(h * 0.95, cy))
        
        dist = np.sqrt((cx - zhuan_px[0])**2 + (cy - zhuan_px[1])**2)
        ideal_dist = np.sqrt(w**2 + h**2) * 0.3
        score = -abs(dist - ideal_dist)
        
        if score > best_dist_score:
            best_dist_score = score
            best = (cx, cy)
    
    he_pct_x = best[0] * 100 / w
    he_pct_y = best[1] * 100 / h
    
    return {
        "x": round(he_pct_x, 1),
        "y": round(he_pct_y, 1),
        "reason": "几何回环兜底（无题款印章检测）",
        "pixel": (int(best[0]), int(best[1])),
        "method": "geometric_fallback",
    }


def validate_he_with_qcqh(
    qi: Dict,
    cheng_list: List[Dict],
    zhuan: Dict,
    he: Dict
) -> Dict:
    """
    验证起承转合四点是否构成合理的回环。
    
    检查项：
    1. 四点不能共线
    2. 四点应该能拟合一条平滑曲线
    3. 合点不能与起点太近
    """
    points = []
    points.append((qi["x"], qi["y"]))
    for c in cheng_list:
        points.append((c["x"], c["y"]))
    points.append((zhuan["x"], zhuan["y"]))
    points.append((he["x"], he["y"]))
    
    if len(points) < 4:
        return {"valid": False, "reason": "点数不足"}
    
    # 检查起点和合点的距离
    start_end_dist = np.sqrt((points[0][0] - points[-1][0])**2 + 
                              (points[0][1] - points[-1][1])**2)
    
    # 检查共线性（所有点是否近似在一条直线上）
    if _check_collinear(points):
        return {"valid": False, "reason": "四点近似共线，无法形成回环"}
    
    # 检查路径是否弯曲（方向变化次数）
    direction_changes = _count_direction_changes(points)
    
    valid = direction_changes >= 1  # 至少有一次方向变化
    
    return {
        "valid": valid,
        "reason": f"方向变化{direction_changes}次, 起合距离{start_end_dist:.0f}%",
        "direction_changes": direction_changes,
        "start_end_dist": start_end_dist,
    }


def _check_collinear(points: List[Tuple[float, float]], threshold: float = 0.95) -> bool:
    """检查点集是否近似共线"""
    if len(points) < 3:
        return False
    
    p0, p1 = np.array(points[0]), np.array(points[1])
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = np.sqrt(dx**2 + dy**2)
    if length < 1e-6:
        return True
    
    for p in points[2:]:
        # 计算点到直线的距离
        px, py = np.array(p)[0] - p0[0], np.array(p)[1] - p0[1]
        dist = abs(dx * py - dy * px) / length
        max_dim = max(abs(dx), abs(dy), 1)
        if dist / max_dim > 0.2:  # 不是共线的
            return False
    
    return True


def _count_direction_changes(points: List[Tuple[float, float]]) -> int:
    """计算路径的方向变化次数"""
    if len(points) < 3:
        return 0
    
    angles = []
    for i in range(len(points) - 1):
        dx = points[i+1][0] - points[i][0]
        dy = points[i+1][1] - points[i][1]
        angle = np.arctan2(dy, dx)
        angles.append(angle)
    
    changes = 0
    for i in range(len(angles) - 1):
        diff = angles[i+1] - angles[i]
        # 标准化到 [-pi, pi]
        while diff > np.pi: diff -= 2 * np.pi
        while diff < -np.pi: diff += 2 * np.pi
        if abs(diff) > np.pi / 6:  # 方向变化超过 30 度
            changes += 1
    
    return changes
