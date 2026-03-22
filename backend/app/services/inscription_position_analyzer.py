"""
题跋位置分析模块
分析题跋在画面中的位置和布局形式
"""

from typing import List, Dict, Tuple
import math


def analyze_inscription_position(regions: Dict, image_width: int, image_height: int) -> Dict:
    """
    分析题跋在画面中的位置和布局形式
    
    Args:
        regions: 区域数据，包含 inscription_regions
        image_width: 图像宽度
        image_height: 图像高度
    
    Returns:
        {
            "position": "左上/右上/左下/右下/中间/...",
            "layout_type": "边角式/拦边封角式/穿插式/满布式/独立式",
            "layout_description": "详细描述",
            "coverage_ratio": 0.15,
            "edge_distance": {"left": 0.1, "right": 0.8, "top": 0.1, "bottom": 0.9}
        }
    """
    inscription_regions = regions.get("inscription_regions", [])
    painting_regions = regions.get("painting_regions", [])
    
    if not inscription_regions:
        return {
            "position": "无题跋",
            "layout_type": "无题跋",
            "layout_description": "画面中未检测到题跋区域",
            "coverage_ratio": 0,
            "edge_distance": {}
        }
    
    # 计算题跋区域的整体边界框
    all_points = []
    for region in inscription_regions:
        if "points" in region and isinstance(region["points"], list):
            all_points.extend(region["points"])
    
    if not all_points:
        return {
            "position": "未知",
            "layout_type": "未知",
            "layout_description": "无法解析题跋区域",
            "coverage_ratio": 0,
            "edge_distance": {}
        }
    
    # 计算边界框
    min_x = min(p["x"] for p in all_points)
    max_x = max(p["x"] for p in all_points)
    min_y = min(p["y"] for p in all_points)
    max_y = max(p["y"] for p in all_points)
    
    # 计算中心点
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    
    # 判断位置
    position = determine_position(center_x, center_y, image_width, image_height)
    
    # 计算与边缘的距离（像素值）
    margin_left = min_x
    margin_right = image_width - max_x
    margin_top = min_y
    margin_bottom = image_height - max_y
    
    # 计算与边缘的距离（归一化）
    edge_distance = {
        "left": min_x / image_width,
        "right": (image_width - max_x) / image_width,
        "top": min_y / image_height,
        "bottom": (image_height - max_y) / image_height
    }
    
    # 计算覆盖率
    inscription_area = calculate_regions_area(inscription_regions)
    total_area = image_width * image_height
    coverage_ratio = inscription_area / total_area if total_area > 0 else 0
    
    # 计算与绘画区域的重叠比例
    overlap_ratio = calculate_overlap_ratio(inscription_regions, painting_regions)
    
    # 判断布局类型
    layout_type, layout_description = determine_layout_type(
        inscription_regions, painting_regions, 
        edge_distance, coverage_ratio,
        image_width, image_height
    )
    
    return {
        "position": position,
        "layout_type": layout_type,
        "layout_description": layout_description,
        "coverage_ratio": round(coverage_ratio, 4),
        "overlap_ratio": round(overlap_ratio, 4),
        "margin_left": margin_left,
        "margin_right": margin_right,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom,
        "edge_distance": {k: round(v, 4) for k, v in edge_distance.items()}
    }


def determine_position(center_x: float, center_y: float, image_width: int, image_height: int) -> str:
    """根据中心点判断题跋位置"""
    # 归一化坐标
    nx = center_x / image_width
    ny = center_y / image_height
    
    # 定义区域阈值
    left_threshold = 0.33
    right_threshold = 0.67
    top_threshold = 0.33
    bottom_threshold = 0.67
    
    # 判断位置
    if nx < left_threshold and ny < top_threshold:
        return "左上"
    elif nx > right_threshold and ny < top_threshold:
        return "右上"
    elif nx < left_threshold and ny > bottom_threshold:
        return "左下"
    elif nx > right_threshold and ny > bottom_threshold:
        return "右下"
    elif nx < left_threshold:
        return "左侧"
    elif nx > right_threshold:
        return "右侧"
    elif ny < top_threshold:
        return "上方"
    elif ny > bottom_threshold:
        return "下方"
    else:
        return "中间"


def calculate_regions_area(regions: List[Dict]) -> float:
    """计算区域总面积"""
    total_area = 0.0
    for region in regions:
        if "points" in region and len(region["points"]) >= 3:
            area = calculate_polygon_area(region["points"])
            total_area += area
        elif "x1" in region and "y1" in region and "x2" in region and "y2" in region:
            area = (region["x2"] - region["x1"]) * (region["y2"] - region["y1"])
            total_area += area
    return total_area


def calculate_polygon_area(points: List[Dict]) -> float:
    """使用 shoelace 公式计算多边形面积"""
    n = len(points)
    if n < 3:
        return 0.0
    
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i]["x"] * points[j]["y"]
        area -= points[j]["x"] * points[i]["y"]
    
    return abs(area) / 2.0


def determine_layout_type(
    inscription_regions: List[Dict], 
    painting_regions: List[Dict],
    edge_distance: Dict,
    coverage_ratio: float,
    image_width: int,
    image_height: int
) -> Tuple[str, str]:
    """
    判断题跋布局类型
    
    规则：
    1. 边角式：题跋集中在画面四角或边缘，与边缘距离小
    2. 拦边封角式：题跋沿边缘形成"L"形或"U"形包围
    3. 穿插式：题跋与绘画区域有较多重叠
    4. 满布式：题跋覆盖大面积（>30%）
    5. 独立式：题跋集中在某个空白区域，与绘画分离
    """
    
    # 检查是否满布式
    if coverage_ratio > 0.30:
        return "满布式", "题跋覆盖大面积画面，几乎不留空白，体现了画家将书法与绘画融为一体的创作理念"
    
    # 计算题跋区域数量
    region_count = len(inscription_regions)
    
    # 检查边缘距离
    min_edge_dist = min(edge_distance.values())
    max_edge_dist = max(edge_distance.values())
    
    # 检查是否边角式（靠近边缘，且区域数量较少）
    if min_edge_dist < 0.1 and region_count <= 2:
        return "边角式", "题跋集中在画面四角或边缘，保持了画面的主体空间，是传统文人画常见的题跋方式"
    
    # 检查是否拦边封角式（沿边缘分布，形成包围）
    edge_count = sum(1 for d in edge_distance.values() if d < 0.15)
    if edge_count >= 2:
        return "拦边封角式", "题跋沿边缘形成包围之势，既界定了画面边界，又与中心绘画形成呼应"
    
    # 检查与绘画区域的重叠
    overlap_ratio = calculate_overlap_ratio(inscription_regions, painting_regions)
    if overlap_ratio > 0.3:
        return "穿插式", "题跋书写在绘画主体的空隙之间，与画面内容相互穿插，体现了书画同源的艺术追求"
    
    # 默认为独立式
    return "独立式", "题跋集中在某个空白区域，与绘画主体分离，保持了各自的独立性"


def calculate_overlap_ratio(inscription_regions: List[Dict], painting_regions: List[Dict]) -> float:
    """计算题跋与绘画区域的重叠比例"""
    if not inscription_regions or not painting_regions:
        return 0.0
    
    # 简化计算：检查题跋区域的中心点有多少在绘画区域内
    overlap_count = 0
    total_count = 0
    
    for ins_region in inscription_regions:
        if "points" not in ins_region:
            continue
        
        points = ins_region["points"]
        if len(points) < 3:
            continue
        
        # 计算题跋区域中心点
        center_x = sum(p["x"] for p in points) / len(points)
        center_y = sum(p["y"] for p in points) / len(points)
        
        total_count += 1
        
        # 检查中心点是否在绘画区域内
        for paint_region in painting_regions:
            if "points" in paint_region and len(paint_region["points"]) >= 3:
                if point_in_polygon({"x": center_x, "y": center_y}, paint_region["points"]):
                    overlap_count += 1
                    break
    
    return overlap_count / total_count if total_count > 0 else 0.0


def point_in_polygon(point: Dict, polygon: List[Dict]) -> bool:
    """判断点是否在多边形内（射线法）"""
    x, y = point["x"], point["y"]
    n = len(polygon)
    inside = False
    
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]["x"], polygon[i]["y"]
        xj, yj = polygon[j]["x"], polygon[j]["y"]
        
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    
    return inside
