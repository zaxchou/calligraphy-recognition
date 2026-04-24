"""
Advanced CV analysis for潘天寿 composition rules.

Provides region density, line crossings, element counting,
direction trends, triangle detection, and dense-area gap analysis.
All functions accept BGR image + edge map + binary mask,
returning lightweight dataclass results.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RegionDensity:
    """Density of foreground (ink) in 9 regions + 4 edges + 4 corners."""
    # Main 9-grid (3x3)
    top_left: float = 0.0
    top_center: float = 0.0
    top_right: float = 0.0
    mid_left: float = 0.0
    mid_center: float = 0.0
    mid_right: float = 0.0
    bot_left: float = 0.0
    bot_center: float = 0.0
    bot_right: float = 0.0
    # Row/col aggregates
    top_row: float = 0.0
    mid_row: float = 0.0
    bot_row: float = 0.0
    left_col: float = 0.0
    center_col: float = 0.0
    right_col: float = 0.0
    # Key ratios
    top_bot_ratio: float = 1.0  # top_row / bot_row
    left_right_ratio: float = 1.0  # left_col / right_col
    center_vs_avg: float = 1.0  # mid_center / avg(all 9)
    min_cell: float = 0.0
    max_cell: float = 0.0
    # Bottom edge density (for "not touching bottom" check)
    bottom_edge_density: float = 0.0  # density in bottom 3% strip


@dataclass
class LineCrossings:
    """Line intersection analysis from Hough transform."""
    total_crossings: int = 0
    # Single-point clusters (bad: many lines cross at same spot)
    max_cluster_size: int = 0
    single_point_crossings: int = 0  # crossings where >2 lines meet at one spot
    # Cross type breakdown
    horizontal_vertical_crosses: int = 0  # near-90° crosses (十字形)
    acute_crosses: int = 0  # sharp angle crosses (good: 女字形)
    parallel_line_pairs: int = 0  # nearly parallel line pairs
    # Line orientation summary
    dominant_angle: float = -1.0  # degrees [0, 180)
    angle_concentration: float = 0.0  # how concentrated the angles are [0, 1]


@dataclass
class ElementAnalysis:
    """Connected component / element analysis."""
    element_count: int = 0
    large_elements: int = 0  # >5% of image area
    small_elements: int = 0  # <1% of image area
    area_ratio_max_min: float = 1.0  # largest / smallest element
    avg_distance: float = 0.0
    min_distance: float = 0.0
    max_distance: float = 0.0
    distance_std: float = 0.0  # std of pairwise distances
    # Spacing uniformity (low = evenly spaced = bad)
    spacing_uniformity: float = 1.0  # distance_std / avg_distance
    # Element area distribution
    top_heavy: bool = False  # upper half has more area
    bottom_heavy: bool = False
    # Nearest neighbor stats
    avg_nearest_neighbor: float = 0.0
    min_nearest_neighbor: float = 0.0
    # Isolated element check
    isolated_elements: int = 0  # elements far from others


@dataclass
class DirectionTrends:
    """Main direction / trend analysis."""
    dominant_direction: float = -1.0  # degrees [0, 180)
    dominant_strength: float = 0.0  # [0, 1]
    secondary_direction: float = -1.0
    secondary_strength: float = 0.0
    # Conflict detection
    opposing_trends: int = 0  # number of opposing direction pairs (>150° apart)
    has_major_conflict: bool = False  # two strong opposing trends
    # Diagonal preference
    diagonal_ratio: float = 0.0  # ratio of diagonal (30-60°, 120-150°) lines
    horizontal_vertical_ratio: float = 0.0  # ratio of H+V lines
    # Start/end zone density (for 开合 analysis)
    start_zone_density: float = 0.0  # density near image edges
    end_zone_density: float = 0.0


@dataclass
class TriangleInfo:
    """Triangle layout detection from top-3 elements."""
    has_triangle: bool = False
    triangle_area_ratio: float = 0.0  # triangle area / image area
    is_equilateral: bool = False
    side_ratio_min_max: float = 1.0  # min/max side ratio (1.0 = equilateral)
    triangle_type: str = "none"  # "equilateral", "isosceles", "scalene", "none"
    # Three-point collinearity check
    collinearity_score: float = 0.0  # 0 = collinear, 1 = well-formed triangle
    vertex_coords: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class DenseAreaGaps:
    """Gap / breathing-room analysis inside dense regions."""
    dense_cell_count: int = 0  # number of dense cells (>threshold)
    dense_area_ratio: float = 0.0  # total dense area / image area
    dense_internal_blank_ratio: float = 0.0  # blank pixels inside dense areas
    dense_gap_count: int = 0  # number of gaps (small blank regions) inside dense areas
    # Comparison
    sparse_cell_count: int = 0
    dense_sparse_ratio: float = 0.0  # dense density / sparse density
    # Rhythm: variation between adjacent cells
    rhythm_score: float = 0.0  # 0 = flat, 1 = strong alternation


@dataclass
class AdvancedMetrics:
    """All advanced CV metrics combined."""
    region: RegionDensity = field(default_factory=RegionDensity)
    crossings: LineCrossings = field(default_factory=LineCrossings)
    elements: ElementAnalysis = field(default_factory=ElementAnalysis)
    trends: DirectionTrends = field(default_factory=DirectionTrends)
    triangle: TriangleInfo = field(default_factory=TriangleInfo)
    gaps: DenseAreaGaps = field(default_factory=DenseAreaGaps)


# ---------------------------------------------------------------------------
# 1. Region Density Analysis
# ---------------------------------------------------------------------------

def compute_region_density(bw: np.ndarray) -> RegionDensity:
    """Compute foreground density in 3x3 grid + edges + corners."""
    h, w = bw.shape[:2]
    fg = (bw == 0).astype(np.uint8)

    rh, rw = h // 3, w // 3

    cells = {}
    names_2d = [
        ("top_left", 0, 0), ("top_center", 0, 1), ("top_right", 0, 2),
        ("mid_left", 1, 0), ("mid_center", 1, 1), ("mid_right", 1, 2),
        ("bot_left", 2, 0), ("bot_center", 2, 1), ("bot_right", 2, 2),
    ]
    for name, ri, ci in names_2d:
        cell = fg[ri * rh:(ri + 1) * rh, ci * rw:(ci + 1) * rw]
        cells[name] = float(np.mean(cell))

    top_row = (cells["top_left"] + cells["top_center"] + cells["top_right"]) / 3
    mid_row = (cells["mid_left"] + cells["mid_center"] + cells["mid_right"]) / 3
    bot_row = (cells["bot_left"] + cells["bot_center"] + cells["bot_right"]) / 3
    left_col = (cells["top_left"] + cells["mid_left"] + cells["bot_left"]) / 3
    center_col = (cells["top_center"] + cells["mid_center"] + cells["bot_center"]) / 3
    right_col = (cells["top_right"] + cells["mid_right"] + cells["bot_right"]) / 3

    avg_all = np.mean(list(cells.values()))
    all_vals = list(cells.values())

    top_bot_ratio = top_row / max(bot_row, 1e-9)
    left_right_ratio = left_col / max(right_col, 1e-9)
    center_vs_avg = cells["mid_center"] / max(avg_all, 1e-9)

    # Bottom 3% strip density (for "not touching bottom")
    strip_h = max(h // 30, 1)
    bottom_strip = fg[h - strip_h:, :]
    bottom_edge_density = float(np.mean(bottom_strip))

    return RegionDensity(
        **cells,
        top_row=top_row, mid_row=mid_row, bot_row=bot_row,
        left_col=left_col, center_col=center_col, right_col=right_col,
        top_bot_ratio=top_bot_ratio,
        left_right_ratio=left_right_ratio,
        center_vs_avg=center_vs_avg,
        min_cell=min(all_vals), max_cell=max(all_vals),
        bottom_edge_density=bottom_edge_density,
    )


# ---------------------------------------------------------------------------
# 2. Line Crossing Detection
# ---------------------------------------------------------------------------

def _line_angle(x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    angle = np.degrees(np.arctan2(dy, dx)) % 180
    return angle


def _angle_diff(a1: float, a2: float) -> float:
    """Smallest angle between two directions [0, 90]."""
    d = abs(a1 - a2) % 180
    return min(d, 180 - d)


def _seg_intersection(p1, p2, p3, p4) -> Optional[Tuple[float, float]]:
    """Find intersection of segments p1-p2 and p3-p4. Returns (x,y) or None."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def compute_line_crossings(edges: np.ndarray) -> LineCrossings:
    """Detect line crossings using HoughLinesP."""
    h, w = edges.shape[:2]
    min_len = int(0.2 * max(w, h))
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=60, minLineLength=min_len, maxLineGap=15
    )
    if lines is None or len(lines) < 2:
        return LineCrossings()

    segments = []
    angles = []
    for seg in lines[:, 0, :]:
        x1, y1, x2, y2 = seg
        segments.append(((float(x1), float(y1)), (float(x2), float(y2))))
        angles.append(_line_angle(x1, y1, x2, y2))

    # Find all intersections
    intersections = []
    hv_crosses = 0
    acute_crosses = 0
    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            pt = _seg_intersection(segments[i][0], segments[i][1],
                                  segments[j][0], segments[j][1])
            if pt is not None:
                intersections.append(pt)
                diff = _angle_diff(angles[i], angles[j])
                if 75 <= diff <= 105:
                    hv_crosses += 1
                elif diff < 45:
                    acute_crosses += 1

    # Cluster intersections to find single-point crossings
    single_point = 0
    max_cluster = 0
    if intersections:
        pts = np.array(intersections, dtype=np.float32)
        # DBSCAN-like: count points within small radius
        cluster_radius = min(w, h) * 0.03
        for pt in intersections:
            dists = np.sqrt(np.sum((pts - np.array(pt)) ** 2, axis=1))
            nearby = int(np.sum(dists < cluster_radius))
            if nearby > max_cluster:
                max_cluster = nearby
            if nearby >= 3:
                single_point += 1
        single_point = min(single_point, len(intersections))

    # Parallel line pairs
    parallel_pairs = 0
    for i in range(len(angles)):
        for j in range(i + 1, len(angles)):
            if _angle_diff(angles[i], angles[j]) < 8:
                parallel_pairs += 1

    # Angle histogram
    bins = 18  # 10° each
    hist = np.zeros(bins)
    for a in angles:
        idx = int(a / 10) % bins
        hist[idx] += 1
    total = max(hist.sum(), 1)
    dom_idx = int(np.argmax(hist))
    dom_angle = dom_idx * 10 + 5
    concentration = float(hist[dom_idx] / total)

    return LineCrossings(
        total_crossings=len(intersections),
        max_cluster_size=max_cluster,
        single_point_crossings=single_point,
        horizontal_vertical_crosses=hv_crosses,
        acute_crosses=acute_crosses,
        parallel_line_pairs=parallel_pairs,
        dominant_angle=dom_angle,
        angle_concentration=concentration,
    )


# ---------------------------------------------------------------------------
# 3. Element Counting & Contour Analysis
# ---------------------------------------------------------------------------

def compute_element_analysis(bw: np.ndarray) -> ElementAnalysis:
    """Analyze connected components (ink elements)."""
    h, w = bw.shape[:2]
    total_area = h * w

    fg = (bw == 0).astype(np.uint8)
    # Clean up noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=1)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel, iterations=1)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        fg, connectivity=8
    )

    # Filter: skip tiny noise (<0.05% of image) and background (label 0)
    min_area = total_area * 0.0005
    elements = []
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue
        cx = stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH] / 2
        cy = stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT] / 2
        elements.append({
            "area": area, "cx": cx, "cy": cy,
            "bbox": (stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP],
                     stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]),
        })

    n = len(elements)
    if n == 0:
        return ElementAnalysis()

    areas = [e["area"] for e in elements]
    area_ratio = max(areas) / max(min(areas), 1)
    large = sum(1 for a in areas if a > total_area * 0.05)
    small = sum(1 for a in areas if a < total_area * 0.01)

    # Top/bottom weight
    top_area = sum(a for e, a in zip(elements, areas) if e["cy"] < h / 2)
    bot_area = sum(areas) - top_area
    top_heavy = top_area > bot_area * 1.3
    bottom_heavy = bot_area > top_area * 1.3

    # Pairwise distances
    if n >= 2:
        coords = np.array([[e["cx"], e["cy"]] for e in elements])
        dists = []
        for i in range(n):
            for j in range(i + 1, n):
                d = float(np.linalg.norm(coords[i] - coords[j]))
                dists.append(d)
        avg_dist = np.mean(dists)
        min_dist = min(dists)
        max_dist = max(dists)
        dist_std = float(np.std(dists))
        spacing_uni = dist_std / max(avg_dist, 1e-9)

        # Nearest neighbor
        nn_dists = []
        for i in range(n):
            nn = min(float(np.linalg.norm(coords[i] - coords[j]))
                     for j in range(n) if j != i)
            nn_dists.append(nn)
        avg_nn = float(np.mean(nn_dists))
        min_nn = float(min(nn_dists))

        # Isolated elements (>2x avg nearest neighbor distance)
        iso_thresh = avg_nn * 2.5
        isolated = sum(1 for d in nn_dists if d > iso_thresh)
    else:
        avg_dist = min_dist = max_dist = dist_std = 0.0
        spacing_uni = 1.0
        avg_nn = min_nn = 0.0
        isolated = 0

    return ElementAnalysis(
        element_count=n,
        large_elements=large,
        small_elements=small,
        area_ratio_max_min=min(area_ratio, 999.0),
        avg_distance=avg_dist,
        min_distance=min_dist,
        max_distance=max_dist,
        distance_std=dist_std,
        spacing_uniformity=spacing_uni,
        top_heavy=top_heavy,
        bottom_heavy=bottom_heavy,
        avg_nearest_neighbor=avg_nn,
        min_nearest_neighbor=min_nn,
        isolated_elements=isolated,
    )


# ---------------------------------------------------------------------------
# 4. Direction / Trend Analysis
# ---------------------------------------------------------------------------

def compute_direction_trends(edges: np.ndarray) -> DirectionTrends:
    """Analyze direction trends from edge gradients."""
    h, w = edges.shape[:2]
    gx = cv2.Sobel(edges, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(edges, cv2.CV_32F, 0, 1, ksize=3)
    mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=False)

    mask = mag > np.percentile(mag, 60)
    ang_m = ang[mask]
    mag_m = mag[mask]

    if ang_m.size < 10:
        return DirectionTrends()

    # 18-bin histogram (10° each)
    bins = 18
    hist = np.zeros(bins, dtype=np.float64)
    idx = np.floor((ang_m % np.pi) / (np.pi / bins)).astype(int)
    idx = np.clip(idx, 0, bins - 1)
    for i, m in zip(idx, mag_m):
        hist[i] += float(m)

    total = hist.sum()
    if total <= 0:
        return DirectionTrends()

    hist_norm = hist / total

    # Dominant direction
    dom_idx = int(np.argmax(hist_norm))
    dom_angle = dom_idx * 10 + 5
    dom_strength = float(hist_norm[dom_idx])

    # Secondary direction (must be >30° away from dominant)
    sec_angle = -1.0
    sec_strength = 0.0
    for i in range(bins):
        if abs(i * 10 + 5 - dom_angle) > 30 and hist_norm[i] > sec_strength:
            sec_strength = float(hist_norm[i])
            sec_angle = i * 10 + 5

    # Opposing trends (>150° apart, both with >15% strength)
    opposing = 0
    strong_bins = [(i, hist_norm[i]) for i in range(bins) if hist_norm[i] > 0.15]
    for i, (bi, bs) in enumerate(strong_bins):
        for bj, bjs in strong_bins[i + 1:]:
            diff = abs(bi * 10 - bj * 10)
            diff = min(diff, 180 - diff)
            if diff > 150:
                opposing += 1

    has_conflict = opposing >= 1 and dom_strength > 0.25 and sec_strength > 0.15

    # Diagonal vs H/V ratio
    diagonal_bins = [3, 4, 5, 12, 13, 14]  # 30-60°, 120-150°
    hv_bins = [0, 1, 8, 9]  # 0-20°, 80-100°
    diag_ratio = sum(hist_norm[i] for i in diagonal_bins if i < bins)
    hv_ratio = sum(hist_norm[i] for i in hv_bins if i < bins)

    # Start zone density (edge strips 10% from each border)
    border = max(min(h, w) // 10, 5)
    start_zone = np.zeros_like(edges)
    start_zone[:border, :] = 1
    start_zone[-border:, :] = 1
    start_zone[:, :border] = 1
    start_zone[:, -border:] = 1
    start_density = float(np.mean(edges[start_zone > 0]) / 255.0)
    end_density = start_density  # symmetric in this simple model

    return DirectionTrends(
        dominant_direction=dom_angle,
        dominant_strength=dom_strength,
        secondary_direction=sec_angle,
        secondary_strength=sec_strength,
        opposing_trends=opposing,
        has_major_conflict=has_conflict,
        diagonal_ratio=diag_ratio,
        horizontal_vertical_ratio=hv_ratio,
        start_zone_density=start_density,
        end_zone_density=end_density,
    )


# ---------------------------------------------------------------------------
# 5. Triangle Detection
# ---------------------------------------------------------------------------

def compute_triangle_info(bw: np.ndarray) -> TriangleInfo:
    """Detect triangle layout from top-N elements by area."""
    h, w = bw.shape[:2]
    fg = (bw == 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=1)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(fg, 8)
    total_area = h * w
    min_area = total_area * 0.001

    elems = []
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue
        cx = float(centroids[i][0])
        cy = float(centroids[i][1])
        elems.append((area, cx, cy))

    if len(elems) < 3:
        return TriangleInfo()

    # Sort by area descending, take top 3
    elems.sort(key=lambda x: x[0], reverse=True)
    pts = [(e[1], e[2]) for e in elems[:3]]

    # Compute side lengths
    def dist(a, b):
        return float(np.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2))

    sides = sorted([dist(pts[0], pts[1]), dist(pts[1], pts[2]), dist(pts[2], pts[0])])

    # Collinearity: area of triangle / bounding area
    tri_area = abs(0.5 * (
        pts[0][0] * (pts[1][1] - pts[2][1]) +
        pts[1][0] * (pts[2][1] - pts[0][1]) +
        pts[2][0] * (pts[0][1] - pts[1][1])
    ))
    max_side = max(sides)
    collinearity = tri_area / max(max_side ** 2, 1e-9)

    # Side ratio (min/max)
    side_ratio = sides[0] / max(sides[2], 1e-9)

    # Type classification
    tri_type = "none"
    if collinearity > 0.05:
        tri_type = "scalene"
        if side_ratio > 0.85:
            tri_type = "equilateral"
        elif side_ratio > 0.7:
            tri_type = "isosceles"
    else:
        tri_type = "none"

    tri_area_ratio = tri_area / max(total_area, 1)

    return TriangleInfo(
        has_triangle=collinearity > 0.05,
        triangle_area_ratio=tri_area_ratio,
        is_equilateral=side_ratio > 0.85,
        side_ratio_min_max=side_ratio,
        triangle_type=tri_type,
        collinearity_score=min(collinearity, 1.0),
        vertex_coords=pts,
    )


# ---------------------------------------------------------------------------
# 6. Dense Area Gap Analysis
# ---------------------------------------------------------------------------

def compute_dense_area_gaps(bw: np.ndarray) -> DenseAreaGaps:
    """Analyze gaps (breathing room) inside dense regions."""
    h, w = bw.shape[:2]
    fg = (bw == 0).astype(np.uint8)

    grid = 10
    cell_h = max(h // grid, 1)
    cell_w = max(w // grid, 1)

    densities = []
    for i in range(grid):
        for j in range(grid):
            cell = fg[i * cell_h:(i + 1) * cell_h, j * cell_w:(j + 1) * cell_w]
            densities.append(float(np.mean(cell)))

    densities = np.array(densities)
    median_d = float(np.median(densities))

    # Dense cells: above median * 1.3
    threshold = median_d * 1.3
    dense_mask = densities > threshold
    sparse_mask = densities < median_d * 0.7
    dense_count = int(np.sum(dense_mask))
    sparse_count = int(np.sum(sparse_mask))

    # Dense internal blank: look at blank pixels WITHIN the bounding box of dense cells
    dense_area_ratio = float(dense_count / max(len(densities), 1))

    # Find dense region bounding box and measure internal blank
    dense_cells = np.where(dense_mask)[0]
    if len(dense_cells) > 0:
        # Map back to image coordinates
        min_idx = dense_cells.min()
        max_idx = dense_cells.max()
        min_r, min_c = min_idx // grid, min_idx % grid
        max_r, max_c = max_idx // grid, max_idx % grid
        y0, y1 = min_r * cell_h, (max_r + 1) * cell_h
        x0, x1 = min_c * cell_w, (max_c + 1) * cell_w
        region = bw[y0:y1, x0:x1]
        if region.size > 0:
            dense_internal_blank = float(np.mean(region == 255))
        else:
            dense_internal_blank = 0.0
    else:
        dense_internal_blank = 0.0

    # Count gaps: in dense cells, count sub-cells that are blank
    gap_count = 0
    for idx in dense_cells:
        r, c = idx // grid, idx % grid
        cell = fg[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
        # Subdivide into 2x2
        sh, sw = cell_h // 2, cell_w // 2
        for sr in range(2):
            for sc in range(2):
                sub = cell[sr * sh:(sr + 1) * sh, sc * sw:(sc + 1) * sw]
                if np.mean(sub) < 0.3:  # mostly blank
                    gap_count += 1

    # Rhythm: variation between adjacent cells
    if len(densities) > 1:
        diffs = np.abs(np.diff(densities))
        rhythm = float(np.mean(diffs) / max(np.mean(densities), 1e-9))
    else:
        rhythm = 0.0

    avg_dense = float(np.mean(densities[dense_mask])) if dense_count > 0 else 0.0
    avg_sparse = float(np.mean(densities[sparse_mask])) if sparse_count > 0 else 0.0
    ds_ratio = avg_dense / max(avg_sparse, 1e-9)

    return DenseAreaGaps(
        dense_cell_count=dense_count,
        dense_area_ratio=dense_area_ratio,
        dense_internal_blank_ratio=dense_internal_blank,
        dense_gap_count=gap_count,
        sparse_cell_count=sparse_count,
        dense_sparse_ratio=ds_ratio,
        rhythm_score=min(rhythm, 1.0),
    )


# ---------------------------------------------------------------------------
# Master: compute all advanced metrics
# ---------------------------------------------------------------------------

def compute_advanced_metrics(bw: np.ndarray, edges: np.ndarray) -> AdvancedMetrics:
    """Compute all advanced CV metrics from binary mask and edge map."""
    return AdvancedMetrics(
        region=compute_region_density(bw),
        crossings=compute_line_crossings(edges),
        elements=compute_element_analysis(bw),
        trends=compute_direction_trends(edges),
        triangle=compute_triangle_info(bw),
        gaps=compute_dense_area_gaps(bw),
    )
