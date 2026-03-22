"""
多边形区域处理工具模块
支持多边形区域的面积计算、点包含检测等功能
"""

from typing import List, Dict, Tuple, Union
import math


def calculate_polygon_area(points: List[Dict[str, float]]) -> float:
    """
    使用鞋带公式（Shoelace formula）计算多边形面积
    
    Args:
        points: 多边形顶点列表，每个点为 {"x": float, "y": float}
    
    Returns:
        多边形面积（绝对值）
    """
    if len(points) < 3:
        return 0.0
    
    area = 0.0
    n = len(points)
    
    for i in range(n):
        j = (i + 1) % n
        area += points[i]["x"] * points[j]["y"]
        area -= points[j]["x"] * points[i]["y"]
    
    return abs(area) / 2.0


def point_in_polygon(point: Dict[str, float], polygon: List[Dict[str, float]]) -> bool:
    """
    使用射线法判断点是否在多边形内
    
    Args:
        point: 点坐标 {"x": float, "y": float}
        polygon: 多边形顶点列表
    
    Returns:
        点是否在多边形内
    """
    if len(polygon) < 3:
        return False
    
    x, y = point["x"], point["y"]
    inside = False
    n = len(polygon)
    
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]["x"], polygon[i]["y"]
        xj, yj = polygon[j]["x"], polygon[j]["y"]
        
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    
    return inside


def calculate_polygon_overlap_area(poly1: List[Dict[str, float]], 
                                   poly2: List[Dict[str, float]]) -> float:
    """
    计算两个多边形的重叠面积（使用Sutherland-Hodgman裁剪算法）
    
    Args:
        poly1: 第一个多边形顶点列表
        poly2: 第二个多边形顶点列表
    
    Returns:
        重叠区域面积
    """
    # 使用Sutherland-Hodgman算法计算多边形交集
    clipped_polygon = sutherland_hodgman_clip(poly1, poly2)
    
    if len(clipped_polygon) < 3:
        return 0.0
    
    return calculate_polygon_area(clipped_polygon)


def sutherland_hodgman_clip(subject_polygon: List[Dict[str, float]], 
                            clip_polygon: List[Dict[str, float]]) -> List[Dict[str, float]]:
    """
    Sutherland-Hodgman多边形裁剪算法
    
    Args:
        subject_polygon: 被裁剪多边形
        clip_polygon: 裁剪窗口多边形
    
    Returns:
        裁剪后的多边形顶点列表
    """
    def inside(p: Dict[str, float], edge_start: Dict[str, float], 
               edge_end: Dict[str, float]) -> bool:
        """检查点是否在边的内侧"""
        return ((edge_end["x"] - edge_start["x"]) * (p["y"] - edge_start["y"]) - 
                (edge_end["y"] - edge_start["y"]) * (p["x"] - edge_start["x"])) >= 0
    
    def compute_intersection(s: Dict[str, float], e: Dict[str, float],
                           edge_start: Dict[str, float], edge_end: Dict[str, float]) -> Dict[str, float]:
        """计算线段与裁剪边的交点"""
        dc = {"x": edge_start["x"] - edge_end["x"], "y": edge_start["y"] - edge_end["y"]}
        dp = {"x": s["x"] - e["x"], "y": s["y"] - e["y"]}
        
        n1 = edge_start["x"] * edge_end["y"] - edge_start["y"] * edge_end["x"]
        n2 = s["x"] * e["y"] - s["y"] * e["x"]
        n3 = 1.0 / (dc["x"] * dp["y"] - dc["y"] * dp["x"])
        
        return {"x": (n1 * dp["x"] - n2 * dc["x"]) * n3, 
                "y": (n1 * dp["y"] - n2 * dc["y"]) * n3}
    
    output_list = subject_polygon[:]
    clip_size = len(clip_polygon)
    
    for i in range(clip_size):
        clip_start = clip_polygon[i]
        clip_end = clip_polygon[(i + 1) % clip_size]
        input_list = output_list[:]
        output_list = []
        
        if not input_list:
            break
        
        s = input_list[-1]
        for e in input_list:
            if inside(e, clip_start, clip_end):
                if not inside(s, clip_start, clip_end):
                    output_list.append(compute_intersection(s, e, clip_start, clip_end))
                output_list.append(e)
            elif inside(s, clip_start, clip_end):
                output_list.append(compute_intersection(s, e, clip_start, clip_end))
            s = e
    
    return output_list


def rectangle_to_polygon(x1: float, y1: float, x2: float, y2: float) -> List[Dict[str, float]]:
    """
    将矩形转换为多边形顶点列表
    
    Args:
        x1, y1: 左上角坐标
        x2, y2: 右下角坐标
    
    Returns:
        多边形顶点列表（顺时针）
    """
    return [
        {"x": x1, "y": y1},
        {"x": x2, "y": y1},
        {"x": x2, "y": y2},
        {"x": x1, "y": y2}
    ]


def normalize_polygon(polygon: List[Dict[str, float]], 
                     image_width: int, image_height: int) -> List[Dict[str, float]]:
    """
    将比例坐标的多边形转换为像素坐标
    
    Args:
        polygon: 比例坐标多边形（0-1范围）
        image_width: 图像宽度
        image_height: 图像高度
    
    Returns:
        像素坐标多边形
    """
    normalized = []
    for point in polygon:
        x = int(max(0, min(1, point.get("x", 0))) * image_width)
        y = int(max(0, min(1, point.get("y", 0))) * image_height)
        normalized.append({"x": x, "y": y})
    return normalized


def calculate_region_area(region: Dict, use_polygon: bool = False) -> float:
    """
    计算单个区域的面积
    
    Args:
        region: 区域数据，可以是矩形(x1,y1,x2,y2)或多边形(points)
        use_polygon: 是否使用多边形计算
    
    Returns:
        区域面积
    """
    if use_polygon and "points" in region:
        return calculate_polygon_area(region["points"])
    elif "x1" in region and "y1" in region and "x2" in region and "y2" in region:
        return (region["x2"] - region["x1"]) * (region["y2"] - region["y1"])
    else:
        return 0.0


def calculate_regions_area_stats(regions: List[Dict], use_polygon: bool = False) -> float:
    """
    计算多个区域的总面积
    
    Args:
        regions: 区域列表
        use_polygon: 是否使用多边形计算
    
    Returns:
        总面积
    """
    total = 0.0
    for region in regions:
        total += calculate_region_area(region, use_polygon)
    return total
