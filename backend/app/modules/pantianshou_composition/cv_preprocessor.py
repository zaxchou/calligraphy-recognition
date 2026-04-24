"""
起承转合 CV 预处理模块
=====================
在 LLM 分析之前，通过传统 CV 方法提取精确的几何信息，
注入到 LLM prompt 中，辅助 AI 做出更准确的分析。

核心能力：
1. 画材检测与精确重心（图像矩计算，非 bbox 中心）
2. 边缘入画点检测（辅助"起"的定位）
3. 印章/题跋区域检测（红色分割 + 文本区域检测）
4. 主干线条方向检测（HOG/梯度分析）
5. 边缘笔墨密度分析（四边+角落的密度分布）
6. 路径几何验证（对 LLM 输出进行一致性检查）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class MaterialElement:
    """检测到的画材元素"""
    area: float                    # 面积（像素）
    centroid: Tuple[float, float]  # 图像矩重心 (cx, cy) 像素坐标
    centroid_pct: Tuple[float, float]  # 图像矩重心百分比 (x%, y%)
    bbox: Tuple[int, int, int, int]  # 边界框 (x, y, w, h)
    pixel_ratio: float = 0.0       # 面积占画面的比例
    edge_proximity: str = ""       # 最近的边缘: "top"/"bottom"/"left"/"right"/"none"
    edge_distance: float = 0.0     # 到最近边缘的距离比例 (0=在边缘, 1=在中心)
    is_major: bool = False         # 是否为主要画材（面积 > 阈值）


@dataclass
class EdgeEntry:
    """边缘入画点（"起"的候选位置）"""
    edge: str                      # "top"/"bottom"/"left"/"right"
    x: float                       # 百分比坐标 (0-100)
    y: float                       # 百分比坐标 (0-100)
    density: float                 # 该区域的笔墨密度
    confidence: float              # 置信度 (0-1)
    reason: str = ""               # 描述


@dataclass
class SealInfo:
    """检测到的印章"""
    x: float                       # 百分比坐标 (0-100)
    y: float                       # 百分比坐标 (0-100)
    radius: float                  # 百分比半径
    shape: str = "circle"          # "circle" / "square"
    confidence: float = 0.0


@dataclass
class InscriptInfo:
    """检测到的题跋区域"""
    x: float
    y: float
    width: float
    height: float
    position: str = ""             # "top-left" / "top-right" / "right" 等
    area_ratio: float = 0.0


@dataclass
class EdgeDensityProfile:
    """四边笔墨密度分布"""
    top_density: float = 0.0       # 上边缘 (top 10%)
    bottom_density: float = 0.0    # 下边缘 (bottom 10%)
    left_density: float = 0.0      # 左边缘 (left 10%)
    right_density: float = 0.0     # 右边缘 (right 10%)
    top_left_corner: float = 0.0   # 左上角
    top_right_corner: float = 0.0  # 右上角
    bot_left_corner: float = 0.0   # 左下角
    bot_right_corner: float = 0.0  # 右下角
    dominant_entry_edge: str = ""  # 密度最高的入画边缘


@dataclass
class DirectionInfo:
    """主干方向信息"""
    dominant_angle: float = 0.0    # 主方向角度 [0, 180)
    dominant_strength: float = 0.0 # 主方向强度 [0, 1]
    secondary_angle: float = 0.0   # 次方向角度
    secondary_strength: float = 0.0
    is_diagonal: bool = False      # 是否呈对角线趋势
    direction_desc: str = ""       # 方向描述（中文）


@dataclass
class CVPreprocessResult:
    """CV 预处理的完整结果"""
    materials: List[MaterialElement] = field(default_factory=list)
    major_materials: List[MaterialElement] = field(default_factory=list)
    edge_entries: List[EdgeEntry] = field(default_factory=list)
    seals: List[SealInfo] = field(default_factory=list)
    inscriptions: List[InscriptInfo] = field(default_factory=list)
    edge_density: EdgeDensityProfile = field(default_factory=EdgeDensityProfile)
    direction: DirectionInfo = field(default_factory=DirectionInfo)

    # 提供给 LLM 的摘要文本
    llm_context: str = ""

    # 路径验证结果（LLM 输出后填充）
    path_validation: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. 画材检测与精确重心
# ---------------------------------------------------------------------------

def _detect_materials(
    img_bgr: np.ndarray,
    min_area_ratio: float = 0.005,
    max_elements: int = 20,
    gray: Optional[np.ndarray] = None,
    hsv: Optional[np.ndarray] = None,
) -> List[MaterialElement]:
    """
    使用连通域分析 + 图像矩计算检测画材并获取精确重心。

    图像矩重心比 bbox 中心更准确地反映画材的视觉重心，
    因为它会考虑像素分布的不均匀性（例如一棵树冠重心偏上）。
    """
    h, w = img_bgr.shape[:2]
    total_area = h * w

    # 构建前景掩码：深色墨迹 + 浅色画材
    if gray is None:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 双边滤波：在降噪的同时保留边缘（比高斯模糊更适合国画）
    d = max(5, min(15, max(h, w) // 100))
    # 确保 d 为奇数（OpenCV 双边滤波和 GaussianBlur 都要求奇数核）
    if d % 2 == 0:
        d += 1
    sigma_color = 50
    sigma_space = 50
    filtered = cv2.bilateralFilter(gray, d, sigma_color, sigma_space)

    # Otsu 二值化
    _, binary = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # HSV 色差补充浅色画材
    if hsv is None:
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    hsv_blur = cv2.GaussianBlur(hsv, (d, d), 0)
    sat = hsv_blur[:, :, 1].astype(np.float32)
    val = hsv_blur[:, :, 2].astype(np.float32)
    sat_median = np.median(sat)
    val_median = np.median(val)
    sat_dev = np.abs(sat - sat_median)
    val_dev = np.abs(val - val_median)
    sat_thresh = max(8, sat_median * 0.4)
    val_thresh = max(15, val_median * 0.15)
    color_mask = ((sat_dev > sat_thresh) | (val_dev > val_thresh)).astype(np.uint8) * 255
    color_only = cv2.subtract(color_mask, binary)

    # 形态学清理
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    color_only = cv2.morphologyEx(color_only, cv2.MORPH_CLOSE, kernel, iterations=1)
    color_only = cv2.morphologyEx(color_only, cv2.MORPH_OPEN, kernel, iterations=1)

    # 合并深色 + 浅色
    fg = cv2.bitwise_or(binary, color_only)

    # 进一步清理噪声
    clean_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, clean_kernel, iterations=2)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, clean_kernel, iterations=2)

    # 连通域分析
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(fg, connectivity=8)

    min_area = total_area * min_area_ratio
    elements: List[MaterialElement] = []

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue

        # 使用图像矩计算精确重心
        component_mask = (labels == i).astype(np.uint8)
        moments = cv2.moments(component_mask)
        if moments["m00"] > 0:
            cx = moments["m10"] / moments["m00"]
            cy = moments["m01"] / moments["m00"]
        else:
            cx, cy = float(centroids[i][0]), float(centroids[i][1])

        bbox = (
            stats[i, cv2.CC_STAT_LEFT],
            stats[i, cv2.CC_STAT_TOP],
            stats[i, cv2.CC_STAT_WIDTH],
            stats[i, cv2.CC_STAT_HEIGHT],
        )

        # 计算边缘接近度
        edge_proximity, edge_dist = _compute_edge_proximity(cx, cy, w, h)

        pixel_ratio = area / total_area
        is_major = pixel_ratio > 0.02  # 主要画材：面积 > 2%

        # 百分比坐标（与 LLM 坐标系统一致）
        cx_pct = cx / w * 100
        cy_pct = cy / h * 100

        elements.append(MaterialElement(
            area=area,
            centroid=(cx, cy),
            centroid_pct=(cx_pct, cy_pct),
            bbox=bbox,
            pixel_ratio=pixel_ratio,
            edge_proximity=edge_proximity,
            edge_distance=edge_dist,
            is_major=is_major,
        ))

    # 按面积降序排序
    elements.sort(key=lambda e: e.area, reverse=True)
    return elements[:max_elements]


def _compute_edge_proximity(cx: float, cy: float, w: int, h: int) -> Tuple[str, float]:
    """计算点到最近边缘的距离和方向"""
    dists = {
        "top": cy / h,
        "bottom": (h - cy) / h,
        "left": cx / w,
        "right": (w - cx) / w,
    }
    nearest = min(dists, key=dists.get)
    return nearest, dists[nearest]


# ---------------------------------------------------------------------------
# 2. 边缘入画点检测
# ---------------------------------------------------------------------------

def _detect_edge_entries(
    img_bgr: np.ndarray,
    edge_strip_ratio: float = 0.12,
    min_density: float = 0.02,
    gray: Optional[np.ndarray] = None,
) -> List[EdgeEntry]:
    """
    检测画面四边笔墨从外部"进入"画面的位置。
    这些位置是"起"的最佳候选点。
    """
    h, w = img_bgr.shape[:2]

    # 构建笔墨掩码
    if gray is None:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    fg = (binary > 0).astype(np.float32)

    strip_w = int(w * edge_strip_ratio)
    strip_h = int(h * edge_strip_ratio)
    entries: List[EdgeEntry] = []

    # 上边缘
    top_strip = fg[:strip_h, :]
    if np.mean(top_strip) > min_density:
        col_density = np.mean(top_strip, axis=0)
        # 找到密度最高的区域
        if np.max(col_density) > min_density * 2:
            peak_x = int(np.argmax(col_density))
            peak_y = 0
            # 向下延伸找笔墨的入画点
            for y in range(strip_h):
                if fg[y, peak_x] > 0:
                    peak_y = y
                    break
            confidence = min(1.0, np.max(col_density) / 0.5)
            entries.append(EdgeEntry(
                edge="top",
                x=peak_x / w * 100,
                y=peak_y / h * 100,
                density=float(np.max(col_density)),
                confidence=confidence,
                reason=f"上边缘入画点，笔墨密度{np.max(col_density):.2f}",
            ))

    # 下边缘
    bot_strip = fg[h - strip_h:, :]
    if np.mean(bot_strip) > min_density:
        col_density = np.mean(bot_strip, axis=0)
        if np.max(col_density) > min_density * 2:
            peak_x = int(np.argmax(col_density))
            peak_y = h - 1
            for y in range(h - 1, h - strip_h - 1, -1):
                if fg[y, peak_x] > 0:
                    peak_y = y
                    break
            confidence = min(1.0, np.max(col_density) / 0.5)
            entries.append(EdgeEntry(
                edge="bottom",
                x=peak_x / w * 100,
                y=peak_y / h * 100,
                density=float(np.max(col_density)),
                confidence=confidence,
                reason=f"下边缘入画点，笔墨密度{np.max(col_density):.2f}",
            ))

    # 左边缘
    left_strip = fg[:, :strip_w]
    if np.mean(left_strip) > min_density:
        row_density = np.mean(left_strip, axis=1)
        if np.max(row_density) > min_density * 2:
            peak_y = int(np.argmax(row_density))
            peak_x = 0
            for x in range(strip_w):
                if fg[peak_y, x] > 0:
                    peak_x = x
                    break
            confidence = min(1.0, np.max(row_density) / 0.5)
            entries.append(EdgeEntry(
                edge="left",
                x=peak_x / w * 100,
                y=peak_y / h * 100,
                density=float(np.max(row_density)),
                confidence=confidence,
                reason=f"左边缘入画点，笔墨密度{np.max(row_density):.2f}",
            ))

    # 右边缘
    right_strip = fg[:, w - strip_w:]
    if np.mean(right_strip) > min_density:
        row_density = np.mean(right_strip, axis=1)
        if np.max(row_density) > min_density * 2:
            peak_y = int(np.argmax(row_density))
            peak_x = w - 1
            for x in range(w - 1, w - strip_w - 1, -1):
                if fg[peak_y, x] > 0:
                    peak_x = x
                    break
            confidence = min(1.0, np.max(row_density) / 0.5)
            entries.append(EdgeEntry(
                edge="right",
                x=peak_x / w * 100,
                y=peak_y / h * 100,
                density=float(np.max(row_density)),
                confidence=confidence,
                reason=f"右边缘入画点，笔墨密度{np.max(row_density):.2f}",
            ))

    # 按置信度排序
    entries.sort(key=lambda e: e.confidence, reverse=True)
    return entries


# ---------------------------------------------------------------------------
# 3. 印章检测（红色分割）
# ---------------------------------------------------------------------------

def _detect_seals(
    img_bgr: np.ndarray,
    min_area_ratio: float = 0.0005,
    max_area_ratio: float = 0.03,
    min_circularity: float = 0.15,
    hsv: Optional[np.ndarray] = None,
) -> List[SealInfo]:
    """
    通过 HSV 红色分割检测印章位置。
    中国画印章通常为朱红色，在 HSV 空间中有明显特征。
    """
    h, w = img_bgr.shape[:2]
    total_area = h * w

    if hsv is None:
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # 红色在 HSV 中分两个区间（环绕 H=0/180）
    # 区间1: H 0-10
    mask1 = cv2.inRange(hsv, np.array([0, 80, 50]), np.array([10, 255, 255]))
    # 区间2: H 160-180
    mask2 = cv2.inRange(hsv, np.array([160, 80, 50]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(mask1, mask2)

    # 去噪 - 更强的形态学操作
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=2)

    # 连通域
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(red_mask, connectivity=8)
    min_area = total_area * min_area_ratio
    max_area = total_area * max_area_ratio

    seals: List[SealInfo] = []
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area or area > max_area:
            continue

        bw_px = stats[i, cv2.CC_STAT_WIDTH]
        bh_px = stats[i, cv2.CC_STAT_HEIGHT]

        # 长宽比过滤（印章通常接近方形或圆形）
        aspect = bw_px / max(bh_px, 1)
        if aspect < 0.4 or aspect > 2.5:
            continue

        # 计算圆形度
        contours, _ = cv2.findContours(
            (labels == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            continue
        perimeter = cv2.arcLength(contours[0], True)
        if perimeter < 1:
            continue
        circularity = 4 * np.pi * area / max(perimeter ** 2, 1e-9)

        # 过滤太不规则的形状
        if circularity < min_circularity:
            continue

        cx, cy = float(centroids[i][0]), float(centroids[i][1])

        # 计算等效半径
        radius = float(np.sqrt(bw_px * bh_px / np.pi)) / max(w, h) * 100

        # 判断形状：圆形 vs 方形
        shape = "circle" if 0.7 < aspect < 1.3 else "square"
        confidence = min(1.0, circularity * 1.5) if shape == "circle" else min(1.0, (1 - abs(circularity - 0.7)) * 2.0)

        seals.append(SealInfo(
            x=cx / w * 100,
            y=cy / h * 100,
            radius=radius,
            shape=shape,
            confidence=max(0.3, min(1.0, confidence)),
        ))

    return seals


# ---------------------------------------------------------------------------
# 4. 题跋区域检测
# ---------------------------------------------------------------------------

def _detect_inscriptions(
    img_bgr: np.ndarray,
    min_area_ratio: float = 0.01,
    gray: Optional[np.ndarray] = None,
) -> List[InscriptInfo]:
    """
    检测题跋区域。
    题跋通常在画面的留白区域，呈竖排文字形态。
    使用文本区域检测 + 位置启发式。
    """
    h, w = img_bgr.shape[:2]
    total_area = h * w

    if gray is None:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 使用 MSER (Maximally Stable Extremal Regions) 检测文本区域
    mser = cv2.MSER_create()
    mser.setMinArea(int(total_area * 0.0001))
    mser.setMaxArea(int(total_area * 0.05))

    try:
        regions, _ = mser.detectRegions(gray)
    except Exception:
        return []

    if not regions or len(regions) < 5:
        return []

    # 过滤太小的区域
    regions = [r for r in regions if r.shape[0] > 10]

    if len(regions) < 5:
        return []

    # 聚类：题跋文字通常在相似位置形成竖列
    all_pts = np.vstack(regions).astype(np.float32)
    centroids_arr = np.array([np.mean(r, axis=0) for r in regions], dtype=np.float32)

    # 简单空间聚类：将区域按列分组
    x_coords = centroids_arr[:, 0]
    x_sorted = np.sort(x_coords)

    # 找到密集的列群
    col_groups = []
    current_group = [x_sorted[0]]
    for x in x_sorted[1:]:
        if x - current_group[-1] < w * 0.08:  # 同一列的阈值
            current_group.append(x)
        else:
            col_groups.append(current_group)
            current_group = [x]
    col_groups.append(current_group)

    # 只保留包含足够多区域的列（至少5个区域）
    dense_groups = [g for g in col_groups if len(g) >= 5]

    inscriptions: List[InscriptInfo] = []
    for group in dense_groups:
        group_x = np.mean(group)
        group_pts = centroids_arr[
            (centroids_arr[:, 0] >= group[0] - w * 0.02) &
            (centroids_arr[:, 0] <= group[-1] + w * 0.02)
        ]
        if len(group_pts) < 3:
            continue

        y_min = np.min(group_pts[:, 1])
        y_max = np.max(group_pts[:, 1])
        x_min = np.min(group_pts[:, 0])
        x_max = np.max(group_pts[:, 0])

        # 扩展边界
        pad = max(5, int(max(y_max - y_min, x_max - x_min) * 0.1))
        x_min = max(0, x_min - pad)
        y_min = max(0, y_min - pad)
        x_max = min(w, x_max + pad)
        y_max = min(h, y_max + pad)

        area = (x_max - x_min) * (y_max - y_min)
        if area / total_area < min_area_ratio:
            continue

        # 确定位置描述
        cx = (x_min + x_max) / 2
        cy = (y_min + y_max) / 2
        position = _describe_position(cx, cy, w, h)

        inscriptions.append(InscriptInfo(
            x=(x_min + x_max) / 2 / w * 100,
            y=(y_min + y_max) / 2 / h * 100,
            width=(x_max - x_min) / w * 100,
            height=(y_max - y_min) / h * 100,
            position=position,
            area_ratio=area / total_area,
        ))

    # 去重（合并重叠区域）
    if len(inscriptions) > 1:
        merged = [inscriptions[0]]
        for insc in inscriptions[1:]:
            overlap = False
            for m in merged:
                if _rects_overlap(
                    insc.x, insc.y, insc.width, insc.height,
                    m.x, m.y, m.width, m.height,
                ):
                    overlap = True
                    break
            if not overlap:
                merged.append(insc)
        inscriptions = merged

    return inscriptions


def _describe_position(cx: float, cy: float, w: int, h: int) -> str:
    """描述区域在画面中的位置"""
    x_pct = cx / w
    y_pct = cy / h

    parts = []
    if y_pct < 0.35:
        parts.append("top")
    elif y_pct > 0.65:
        parts.append("bottom")
    else:
        parts.append("middle")

    if x_pct < 0.35:
        parts.append("left")
    elif x_pct > 0.65:
        parts.append("right")
    else:
        parts.append("center")

    return "-".join(parts)


def _rects_overlap(
    x1: float, y1: float, w1: float, h1: float,
    x2: float, y2: float, w2: float, h2: float,
    threshold: float = 0.3,
) -> bool:
    """检查两个矩形是否重叠"""
    left = max(x1 - w1 / 2, x2 - w2 / 2)
    right = min(x1 + w1 / 2, x2 + w2 / 2)
    top = max(y1 - h1 / 2, y2 - h2 / 2)
    bottom = min(y1 + h1 / 2, y2 + h2 / 2)

    if left >= right or top >= bottom:
        return False

    overlap_area = (right - left) * (bottom - top)
    area1 = w1 * h1
    area2 = w2 * h2
    return overlap_area / max(min(area1, area2), 1) > threshold


# ---------------------------------------------------------------------------
# 5. 边缘笔墨密度分析
# ---------------------------------------------------------------------------

def _compute_edge_density(img_bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> EdgeDensityProfile:
    """
    计算画面四边和四角的笔墨密度分布。
    密度最高的边缘通常是画材入画的方向。
    """
    h, w = img_bgr.shape[:2]

    if gray is None:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    fg = (binary > 0).astype(np.float32)

    strip_w = int(w * 0.10)
    strip_h = int(h * 0.10)

    # 四边密度
    top_d = float(np.mean(fg[:strip_h, :]))
    bottom_d = float(np.mean(fg[h - strip_h:, :]))
    left_d = float(np.mean(fg[:, :strip_w]))
    right_d = float(np.mean(fg[:, w - strip_w:]))

    # 四角密度（各取 15% × 15%）
    corner_w = int(w * 0.15)
    corner_h = int(h * 0.15)
    tl = float(np.mean(fg[:corner_h, :corner_w]))
    tr = float(np.mean(fg[:corner_h, w - corner_w:]))
    bl = float(np.mean(fg[h - corner_h:, :corner_w]))
    br = float(np.mean(fg[h - corner_h:, w - corner_w:]))

    # 找主导入画边缘
    edge_densities = {
        "上边缘": top_d,
        "下边缘": bottom_d,
        "左边缘": left_d,
        "右边缘": right_d,
    }
    dominant = max(edge_densities, key=edge_densities.get)

    return EdgeDensityProfile(
        top_density=top_d,
        bottom_density=bottom_d,
        left_density=left_d,
        right_density=right_d,
        top_left_corner=tl,
        top_right_corner=tr,
        bot_left_corner=bl,
        bot_right_corner=br,
        dominant_entry_edge=dominant,
    )


# ---------------------------------------------------------------------------
# 6. 主干方向检测
# ---------------------------------------------------------------------------

def _detect_main_direction(img_bgr: np.ndarray, gray: Optional[np.ndarray] = None) -> DirectionInfo:
    """
    使用 HOG/梯度方向分析检测画面的主干方向。
    这有助于判断起承转合路径的整体走势。
    """
    h, w = img_bgr.shape[:2]

    if gray is None:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 使用 Sobel 算子计算梯度
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=True)

    # 只取强梯度（排除弱边缘噪声）
    mag_threshold = np.percentile(mag, 70)
    mask = mag > mag_threshold
    ang_m = ang[mask]
    mag_m = mag[mask]

    if ang_m.size < 10:
        return DirectionInfo()

    # 18-bin 方向直方图 (每 10° 一格)
    bins = 18
    hist = np.zeros(bins, dtype=np.float64)
    for angle, magnitude in zip(ang_m, mag_m):
        # 转换到 [0, 180) 范围（方向无正负）
        a = angle % 180
        idx = int(a / 10) % bins
        hist[idx] += float(magnitude)

    total = hist.sum()
    if total <= 0:
        return DirectionInfo()

    hist_norm = hist / total

    # 主方向
    dom_idx = int(np.argmax(hist_norm))
    dom_angle = dom_idx * 10 + 5
    dom_strength = float(hist_norm[dom_idx])

    # 次方向（与主方向相差 >30°）
    sec_angle = -1.0
    sec_strength = 0.0
    for i in range(bins):
        if abs(i * 10 + 5 - dom_angle) > 30 and hist_norm[i] > sec_strength:
            sec_strength = float(hist_norm[i])
            sec_angle = i * 10 + 5

    # 判断是否为对角线趋势
    diagonal_bins = [3, 4, 5, 12, 13, 14]  # 30-60°, 120-150°
    diag_ratio = sum(hist_norm[i] for i in diagonal_bins if i < bins)
    is_diagonal = diag_ratio > 0.5

    # 方向描述
    direction_desc = _angle_to_chinese_desc(dom_angle)

    return DirectionInfo(
        dominant_angle=dom_angle,
        dominant_strength=dom_strength,
        secondary_angle=sec_angle,
        secondary_strength=sec_strength,
        is_diagonal=is_diagonal,
        direction_desc=direction_desc,
    )


def _angle_to_chinese_desc(angle: float) -> str:
    """将角度转换为中文方向描述"""
    angle = angle % 180
    if angle < 15 or angle >= 165:
        return "水平（左右方向）"
    elif 15 <= angle < 35:
        return "左上到右下（偏水平）"
    elif 35 <= angle < 55:
        return "左上到右下（对角线）"
    elif 55 <= angle < 75:
        return "左上到右下（偏垂直）"
    elif 75 <= angle < 105:
        return "垂直（上下方向）"
    elif 105 <= angle < 125:
        return "左下到右上（偏垂直）"
    elif 125 <= angle < 145:
        return "左下到右上（对角线）"
    elif 145 <= angle < 165:
        return "左下到右上（偏水平）"
    return "未知方向"


# ---------------------------------------------------------------------------
# 7. 路径几何验证
# ---------------------------------------------------------------------------

def validate_path(
    points: Dict[str, Any],
    img_w: int,
    img_h: int,
    cv_result: CVPreprocessResult,
) -> Dict[str, Any]:
    """
    对 LLM 输出的起承转合路径进行几何验证。

    注意：points 中的坐标是像素值（由 _parse_llm_result 的 pct_to_px 转换），
    而 cv_result 中的坐标是百分比 (0-100)。
    此函数内部将像素坐标统一转换为百分比进行比较。

    检查项：
    1. 起是否在边缘（x 或 y 接近 0/100%）
    2. 承/转是否在主要画材的重心附近
    3. 路径方向是否与画面主干方向一致
    4. 合是否在题跋/印章附近
    5. 路径是否形成合理的几何形状（非退化）

    返回验证结果和建议修正。
    """
    issues: List[str] = []
    suggestions: List[str] = []
    score = 100  # 起始分

    qi = points.get("qi", {})
    cheng_list = points.get("cheng_list", [])
    zhuan_list = points.get("zhuan_list", [])
    he = points.get("he", {})

    # 将像素坐标转换为百分比，与 cv_result 坐标系统一致
    def px_to_pct(px_val, dim_size):
        return float(px_val) / max(dim_size, 1) * 100

    qi_x, qi_y = px_to_pct(qi.get("x", img_w // 2), img_w), px_to_pct(qi.get("y", img_h // 2), img_h)
    he_x, he_y = px_to_pct(he.get("x", img_w // 2), img_w), px_to_pct(he.get("y", img_h // 2), img_h)

    # ---- 1. 检查起是否在边缘 ----
    edge_margin = 15  # 百分比
    qi_on_edge = (qi_x <= edge_margin or qi_x >= 100 - edge_margin or
                  qi_y <= edge_margin or qi_y >= 100 - edge_margin)
    if not qi_on_edge:
        issues.append(f"起在画面内部({qi_x:.0f}%, {qi_y:.0f}%)，不在边缘")
        # 建议使用 CV 检测到的最佳入画点
        if cv_result.edge_entries:
            best = cv_result.edge_entries[0]
            suggestions.append(
                f"建议将起移至{best.edge}边缘附近({best.x:.0f}%, {best.y:.0f}%)"
            )
        score -= 15

    # ---- 2. 检查承/转是否在画材重心附近 ----
    major_centers = [(m.centroid_pct[0], m.centroid_pct[1])
                     for m in cv_result.major_materials]

    for label, pt_list in [("承", cheng_list), ("转", zhuan_list)]:
        for pt in pt_list:
            px, py = px_to_pct(pt.get("x", img_w // 2), img_w), px_to_pct(pt.get("y", img_h // 2), img_h)
            if not major_centers:
                break
            # 找最近的画材重心
            min_dist = min(
                np.sqrt((px - mx) ** 2 + (py - my) ** 2)
                for mx, my in major_centers
            )
            # 如果距离超过画面对角线的 15%，可能不在画材重心上
            diag = np.sqrt(100 ** 2 + 100 ** 2)
            if min_dist > diag * 0.15:
                issues.append(f"{label}({px:.0f}%, {py:.0f}%)偏离最近画材重心较远(距离{min_dist:.1f}%)")
                # 找最近的画材重心作为建议
                nearest_idx = min(
                    range(len(major_centers)),
                    key=lambda i: np.sqrt((px - major_centers[i][0]) ** 2 +
                                          (py - major_centers[i][1]) ** 2)
                )
                nx, ny = major_centers[nearest_idx]
                suggestions.append(f"建议将{label}移至最近画材重心({nx:.0f}%, {ny:.0f}%)")
                score -= 10

    # ---- 3. 检查路径方向一致性 ----
    if cv_result.direction.dominant_angle >= 0 and cheng_list:
        cheng = cheng_list[0]
        cx, cy = px_to_pct(cheng.get("x", img_w // 2), img_w), px_to_pct(cheng.get("y", img_h // 2), img_h)
        path_angle = np.degrees(np.arctan2(cy - qi_y, cx - qi_x)) % 180
        angle_diff = abs(path_angle - cv_result.direction.dominant_angle)
        angle_diff = min(angle_diff, 180 - angle_diff)
        if angle_diff > 60 and cv_result.direction.dominant_strength > 0.2:
            issues.append(
                f"路径方向({path_angle:.0f}°)与画面主干方向({cv_result.direction.dominant_angle:.0f}°)偏差较大"
            )
            score -= 10

    # ---- 4. 检查合是否在题跋/印章附近 ----
    has_near_inscription = False
    has_near_seal = False
    for insc in cv_result.inscriptions:
        dist = np.sqrt((he_x - insc.x) ** 2 + (he_y - insc.y) ** 2)
        if dist < 25:
            has_near_inscription = True
            break

    for seal in cv_result.seals:
        dist = np.sqrt((he_x - seal.x) ** 2 + (he_y - seal.y) ** 2)
        if dist < 20:
            has_near_seal = True
            break

    if cv_result.inscriptions and not has_near_inscription and not has_near_seal:
        # 如果有题跋但合不在附近
        insc = cv_result.inscriptions[0]
        dist = np.sqrt((he_x - insc.x) ** 2 + (he_y - insc.y) ** 2)
        if dist > 30:
            issues.append(f"合({he_x:.0f}%, {he_y:.0f}%)不在题跋({insc.x:.0f}%, {insc.y:.0f}%)附近")
            suggestions.append(f"建议将合移至题跋附近({insc.x:.0f}%, {insc.y:.0f}%)")
            score -= 10

    # ---- 5. 检查路径是否形成合理几何形状 ----
    all_points = [(qi_x, qi_y)]
    for pt in cheng_list:
        all_points.append((px_to_pct(pt.get("x", img_w // 2), img_w),
                           px_to_pct(pt.get("y", img_h // 2), img_h)))
    for pt in zhuan_list:
        all_points.append((px_to_pct(pt.get("x", img_w // 2), img_w),
                           px_to_pct(pt.get("y", img_h // 2), img_h)))
    all_points.append((he_x, he_y))

    if len(all_points) >= 3:
        # 检查共线性（所有点不应几乎在一条直线上）
        pts = np.array(all_points, dtype=np.float32)
        # 用 PCA 检查：如果第一主成分解释了 >95% 的方差，说明接近线性
        mean_pt = np.mean(pts, axis=0)
        centered = pts - mean_pt
        cov = np.dot(centered.T, centered)
        eigenvalues = np.linalg.eigvalsh(cov)
        if eigenvalues[0] > 0:
            linearity = eigenvalues[-1] / sum(eigenvalues)
            if linearity > 0.95:
                issues.append("起承转合路径接近直线，缺乏转折变化")
                score -= 15

        # 检查路径点间距是否合理（不应太近或太远）
        for i in range(len(all_points) - 1):
            d = np.sqrt(
                (all_points[i][0] - all_points[i + 1][0]) ** 2 +
                (all_points[i][1] - all_points[i + 1][1]) ** 2
            )
            if d < 5:
                issues.append(f"路径点{i + 1}到点{i + 2}距离太近({d:.1f}%)，可能重合")
                score -= 5

    score = max(0, min(100, score))

    return {
        "score": score,
        "issues": issues,
        "suggestions": suggestions,
        "passed": score >= 70,
    }


# ---------------------------------------------------------------------------
# 8. 生成 LLM 上下文
# ---------------------------------------------------------------------------

def _build_llm_context(result: CVPreprocessResult) -> str:
    """
    将 CV 预处理结果格式化为 LLM 可理解的文本，
    注入到 prompt 中辅助 AI 决策。
    """
    lines = []
    lines.append("【CV 预分析数据】（供参考，帮助你更精确地标定起承转合）")
    lines.append("")

    # 画材信息
    major = result.major_materials
    if major:
        lines.append(f"检测到 {len(major)} 个主要画材：")
        for i, m in enumerate(major):
            cx_pct, cy_pct = m.centroid_pct
            lines.append(
                f"  画材{i + 1}：面积占比 {m.pixel_ratio:.1%}，"
                f"精确重心 ({cx_pct:.0f}%, {cy_pct:.0f}%)，"
                f"靠近{m.edge_proximity}边缘"
            )
        lines.append("")

    # 边缘入画点
    entries = result.edge_entries
    if entries:
        lines.append("推荐的「起」候选位置（按置信度排序）：")
        for i, e in enumerate(entries[:4]):
            lines.append(
                f"  候选{i + 1}：{e.edge}边缘 ({e.x:.0f}%, {e.y:.0f}%)"
                f"，置信度 {e.confidence:.0%}"
            )
        lines.append("")

    # 印章信息
    seals = result.seals
    if seals:
        lines.append(f"检测到 {len(seals)} 个印章：")
        for i, s in enumerate(seals):
            lines.append(
                f"  印章{i + 1}：({s.x:.0f}%, {s.y:.0f}%)，"
                f"{'圆形' if s.shape == 'circle' else '方形'}"
            )
        lines.append("")

    # 题跋信息
    inscs = result.inscriptions
    if inscs:
        lines.append(f"检测到题跋区域：")
        for i, insc in enumerate(inscs):
            lines.append(
                f"  题跋{i + 1}：位置 {insc.position}，"
                f"中心 ({insc.x:.0f}%, {insc.y:.0f}%)"
            )
        lines.append("")

    # 边缘密度
    ed = result.edge_density
    lines.append("四边笔墨密度分布：")
    lines.append(f"  上边缘: {ed.top_density:.2f} | 下边缘: {ed.bottom_density:.2f}")
    lines.append(f"  左边缘: {ed.left_density:.2f} | 右边缘: {ed.right_density:.2f}")
    lines.append(f"  主导入画边缘: {ed.dominant_entry_edge}")
    lines.append("")

    # 主干方向
    d = result.direction
    if d.direction_desc:
        lines.append(f"画面主干方向: {d.direction_desc}（角度 {d.dominant_angle:.0f}°，强度 {d.dominant_strength:.0%}）")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主函数：CV 预处理
# ---------------------------------------------------------------------------

def run_cv_preprocess(img_bgr: np.ndarray) -> CVPreprocessResult:
    """
    执行完整的 CV 预处理流程，返回所有提取的几何信息。

    此函数应在 LLM 分析之前调用，结果注入 prompt。
    预计算 gray/hsv 避免子函数重复转换。
    """
    logger.info("Starting CV preprocess for 起承转合 analysis")

    # 预计算常用的颜色空间转换（避免子函数重复计算）
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # 1. 画材检测
    materials = _detect_materials(img_bgr, gray=gray, hsv=hsv)
    major_materials = [m for m in materials if m.is_major]
    logger.info(f"  Materials: {len(materials)} total, {len(major_materials)} major")

    # 2. 边缘入画点
    edge_entries = _detect_edge_entries(img_bgr, gray=gray)
    logger.info(f"  Edge entries: {len(edge_entries)} candidates")

    # 3. 印章检测
    seals = _detect_seals(img_bgr, hsv=hsv)
    logger.info(f"  Seals: {len(seals)} detected")

    # 4. 题跋检测
    inscriptions = _detect_inscriptions(img_bgr, gray=gray)
    logger.info(f"  Inscriptions: {len(inscriptions)} detected")

    # 5. 边缘密度
    edge_density = _compute_edge_density(img_bgr, gray=gray)

    # 6. 主干方向
    direction = _detect_main_direction(img_bgr, gray=gray)

    result = CVPreprocessResult(
        materials=materials,
        major_materials=major_materials,
        edge_entries=edge_entries,
        seals=seals,
        inscriptions=inscriptions,
        edge_density=edge_density,
        direction=direction,
    )

    # 7. 生成 LLM 上下文
    result.llm_context = _build_llm_context(result)

    logger.info("CV preprocess complete")
    return result
