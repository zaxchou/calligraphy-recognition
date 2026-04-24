"""
面积计算模块
确保题跋、绘画、留白三类区域面积总和为100%
处理区域重叠和边界问题
"""

from typing import List, Dict, Tuple
import cv2
import numpy as np
from .polygon_utils import (
    calculate_polygon_area,
    calculate_polygon_overlap_area,
    rectangle_to_polygon,
    point_in_polygon
)


def region_to_polygon(region: Dict) -> List[Dict[str, float]]:
    """
    将区域转换为多边形格式
    
    Args:
        region: 区域数据（矩形或多边形）
    
    Returns:
        多边形顶点列表
    """
    if "points" in region and isinstance(region["points"], list):
        return region["points"]
    elif "x1" in region and "y1" in region and "x2" in region and "y2" in region:
        return rectangle_to_polygon(
            region["x1"], region["y1"],
            region["x2"], region["y2"]
        )
    return []


def calculate_region_area_accurate(region: Dict) -> float:
    """
    精确计算单个区域面积
    
    Args:
        region: 区域数据
    
    Returns:
        区域面积
    """
    polygon = region_to_polygon(region)
    if len(polygon) >= 3:
        return calculate_polygon_area(polygon)
    return 0.0


def calculate_overlap_between_regions(regions1: List[Dict], regions2: List[Dict]) -> float:
    """
    计算两组区域之间的重叠面积
    
    Args:
        regions1: 第一组区域
        regions2: 第二组区域
    
    Returns:
        重叠面积
    """
    total_overlap = 0.0
    
    for reg1 in regions1:
        poly1 = region_to_polygon(reg1)
        if len(poly1) < 3:
            continue
        
        for reg2 in regions2:
            poly2 = region_to_polygon(reg2)
            if len(poly2) < 3:
                continue
            
            overlap = calculate_polygon_overlap_area(poly1, poly2)
            total_overlap += overlap
    
    return total_overlap


def calculate_area_stats_fillpoly(
    regions: Dict,
    image_width: int,
    image_height: int
) -> Dict:
    """
    基于 cv2.fillPoly 的像素级精确面积统计

    原理：将多边形区域光栅化到 mask，用 np.count_nonzero 精确计数。
    优先级：题跋(1) > 绘画(2) > 留白(3)，按留白→绘画→题跋的顺序 fillPoly，
    后绘制的覆盖先绘制的，自然实现优先级。

    相比旧版像素采样法（sample_step=8 时 ±3% 误差），此方法零误差。
    速度：1000x1000 图像约 5ms（vs 采样法 2-10s）。
    """
    total_area = image_width * image_height
    if total_area <= 0 or image_width <= 0 or image_height <= 0:
        return {
            "total_area": 0,
            "inscription_area": 0,
            "painting_area": 0,
            "blank_area": 0,
            "inscription_percent": 0.0,
            "painting_percent": 0.0,
            "blank_percent": 100.0,
            "region_counts": {
                "inscription_regions": 0,
                "painting_regions": 0,
                "blank_regions": 0,
            },
        }

    # mask 值: 0=未分类, 1=题跋, 2=绘画, 3=留白
    # 按优先级从低到高绘制：留白→绘画→题跋，高优先级覆盖低优先级
    mask = np.zeros((image_height, image_width), dtype=np.uint8)

    region_types = [
        ("blank_regions", 3),
        ("painting_regions", 2),
        ("inscription_regions", 1),
    ]

    region_counts = {}
    for key, val in region_types:
        count = 0
        for r in regions.get(key, []) or []:
            poly = region_to_polygon(r)
            if len(poly) < 3:
                continue
            # 坐标缩放：如果坐标是基于原始尺寸的，需要缩放到当前mask尺寸
            # 但这里假设坐标已经基于传入的 image_width/image_height
            # 所以直接使用，不进行额外缩放
            pts = np.array([[int(p["x"]), int(p["y"])] for p in poly], dtype=np.int32)
            # 确保坐标在有效范围内
            pts = np.clip(pts, 0, [image_width - 1, image_height - 1])
            cv2.fillPoly(mask, [pts], val)
            count += 1
        region_counts[key] = count

    insc_px = int(np.count_nonzero(mask == 1))
    paint_px = int(np.count_nonzero(mask == 2))
    blank_labeled_px = int(np.count_nonzero(mask == 3))
    # 未被任何区域覆盖的像素也归为留白
    blank_px = blank_labeled_px + int(np.count_nonzero(mask == 0))

    if total_area <= 0:
        blank_px = 0
        total_area = 1  # 避免除零

    inscription_percent = (insc_px / total_area * 100.0) if total_area > 0 else 0.0
    painting_percent = (paint_px / total_area * 100.0) if total_area > 0 else 0.0
    blank_percent = 100.0 - inscription_percent - painting_percent

    return {
        "total_area": total_area,
        "inscription_area": round(total_area * inscription_percent / 100.0, 2),
        "painting_area": round(total_area * painting_percent / 100.0, 2),
        "blank_area": round(total_area * blank_percent / 100.0, 2),
        "inscription_percent": round(inscription_percent, 2),
        "painting_percent": round(painting_percent, 2),
        "blank_percent": round(blank_percent, 2),
        "region_counts": region_counts,
    }


def calculate_area_stats_with_overlap_correction(
    regions: Dict,
    image_width: int,
    image_height: int
) -> Dict:
    """
    计算面积统计，优先使用 cv2.fillPoly 像素级精确计算确保三类区域严格互斥
    如果 cv2 不可用则 fallback 到旧版像素采样方法

    优先级：题跋 > 绘画 > 留白
    每个像素点只能属于一种区域类型

    Args:
        regions: 区域数据字典
        image_width: 图像宽度
        image_height: 图像高度

    Returns:
        面积统计结果
    """
    try:
        return calculate_area_stats_fillpoly(regions, image_width, image_height)
    except Exception:
        # fallback 到旧版像素采样方法
        if image_width * image_height > 1000000:
            sample_step = 8
        elif image_width * image_height > 500000:
            sample_step = 6
        elif image_width * image_height > 200000:
            sample_step = 4
        else:
            sample_step = 2
        return calculate_pixel_based_area_stats_exclusive(
            regions, image_width, image_height, sample_step=sample_step
        )


def calculate_pixel_based_area_stats_exclusive(
    regions: Dict,
    image_width: int,
    image_height: int,
    sample_step: int = 2
) -> Dict:
    """
    基于像素采样的面积统计（严格互斥版本）
    
    优先级：题跋 > 绘画 > 留白
    每个像素点只能被归类到一种区域
    
    Args:
        regions: 区域数据
        image_width: 图像宽度
        image_height: 图像高度
        sample_step: 采样步长（像素），越小越精确但越慢
    
    Returns:
        面积统计结果
    """
    # 将区域转换为多边形列表
    inscription_polys = [region_to_polygon(r) for r in regions.get("inscription_regions", [])]
    painting_polys = [region_to_polygon(r) for r in regions.get("painting_regions", [])]
    blank_polys = [region_to_polygon(r) for r in regions.get("blank_regions", [])]
    
    # 过滤无效多边形
    inscription_polys = [p for p in inscription_polys if len(p) >= 3]
    painting_polys = [p for p in painting_polys if len(p) >= 3]
    blank_polys = [p for p in blank_polys if len(p) >= 3]
    
    # 采样统计
    inscription_pixels = 0
    painting_pixels = 0
    blank_pixels = 0
    total_sampled = 0
    
    for y in range(0, image_height, sample_step):
        for x in range(0, image_width, sample_step):
            point = {"x": x, "y": y}
            total_sampled += 1
            
            # 按优先级检查点是否在区域内
            # 优先级1：题跋
            in_inscription = any(point_in_polygon(point, poly) for poly in inscription_polys)
            if in_inscription:
                inscription_pixels += 1
                continue
            
            # 优先级2：绘画
            in_painting = any(point_in_polygon(point, poly) for poly in painting_polys)
            if in_painting:
                painting_pixels += 1
                continue
            
            # 优先级3：留白
            in_blank = any(point_in_polygon(point, poly) for poly in blank_polys)
            if in_blank:
                blank_pixels += 1
                continue
            
            # 如果不在任何区域内，归为留白
            blank_pixels += 1
    
    # 计算百分比
    if total_sampled > 0:
        inscription_percent = (inscription_pixels / total_sampled) * 100
        painting_percent = (painting_pixels / total_sampled) * 100
        blank_percent = (blank_pixels / total_sampled) * 100
    else:
        inscription_percent = 0
        painting_percent = 0
        blank_percent = 100
    
    # 严格确保总和为100%
    total_percent = inscription_percent + painting_percent + blank_percent
    if abs(total_percent - 100) > 0.001:
        # 将差值加到留白上（留白优先级最低，作为兜底）
        blank_percent += (100 - total_percent)
    
    # 最终校验
    final_total = inscription_percent + painting_percent + blank_percent
    if abs(final_total - 100) > 0.01:
        # 如果还有误差，按比例调整
        scale = 100 / final_total
        inscription_percent *= scale
        painting_percent *= scale
        blank_percent *= scale
    
    # 估算实际面积
    pixel_area = sample_step * sample_step
    total_area = image_width * image_height
    
    # 根据百分比计算实际面积（确保与百分比一致）
    inscription_area = total_area * (inscription_percent / 100)
    painting_area = total_area * (painting_percent / 100)
    blank_area = total_area * (blank_percent / 100)
    
    return {
        "total_area": total_area,
        "inscription_area": round(inscription_area, 2),
        "painting_area": round(painting_area, 2),
        "blank_area": round(blank_area, 2),
        "inscription_percent": round(inscription_percent, 2),
        "painting_percent": round(painting_percent, 2),
        "blank_percent": round(blank_percent, 2),
        "sample_info": {
            "sample_step": sample_step,
            "total_sampled": total_sampled
        },
        "region_counts": {
            "inscription_regions": len(inscription_polys),
            "painting_regions": len(painting_polys),
            "blank_regions": len(blank_polys)
        }
    }


def calculate_pixel_based_area_stats(
    regions: Dict,
    image_width: int,
    image_height: int,
    sample_step: int = 5
) -> Dict:
    """
    基于像素采样的面积统计（更精确但较慢）
    
    Args:
        regions: 区域数据
        image_width: 图像宽度
        image_height: 图像高度
        sample_step: 采样步长（像素）
    
    Returns:
        面积统计结果
    """
    # 将区域转换为多边形
    inscription_polys = [region_to_polygon(r) for r in regions.get("inscription_regions", [])]
    painting_polys = [region_to_polygon(r) for r in regions.get("painting_regions", [])]
    blank_polys = [region_to_polygon(r) for r in regions.get("blank_regions", [])]
    
    # 过滤无效多边形
    inscription_polys = [p for p in inscription_polys if len(p) >= 3]
    painting_polys = [p for p in painting_polys if len(p) >= 3]
    blank_polys = [p for p in blank_polys if len(p) >= 3]
    
    # 采样统计
    inscription_pixels = 0
    painting_pixels = 0
    blank_pixels = 0
    total_sampled = 0
    
    for y in range(0, image_height, sample_step):
        for x in range(0, image_width, sample_step):
            point = {"x": x, "y": y}
            total_sampled += 1
            
            # 按优先级检查点是否在区域内
            in_inscription = any(point_in_polygon(point, poly) for poly in inscription_polys)
            if in_inscription:
                inscription_pixels += 1
                continue
            
            in_painting = any(point_in_polygon(point, poly) for poly in painting_polys)
            if in_painting:
                painting_pixels += 1
                continue
            
            in_blank = any(point_in_polygon(point, poly) for poly in blank_polys)
            if in_blank:
                blank_pixels += 1
                continue
            
            # 如果不在任何区域内，归为留白
            blank_pixels += 1
    
    # 计算百分比
    if total_sampled > 0:
        inscription_percent = (inscription_pixels / total_sampled) * 100
        painting_percent = (painting_pixels / total_sampled) * 100
        blank_percent = (blank_pixels / total_sampled) * 100
    else:
        inscription_percent = 0
        painting_percent = 0
        blank_percent = 100
    
    # 确保总和为100%
    total_percent = inscription_percent + painting_percent + blank_percent
    if abs(total_percent - 100) > 0.01:
        blank_percent += (100 - total_percent)
    
    # 估算实际面积
    pixel_area = sample_step * sample_step
    total_area = image_width * image_height
    
    return {
        "total_area": total_area,
        "inscription_area": inscription_pixels * pixel_area,
        "painting_area": painting_pixels * pixel_area,
        "blank_area": blank_pixels * pixel_area,
        "inscription_percent": round(inscription_percent, 2),
        "painting_percent": round(painting_percent, 2),
        "blank_percent": round(blank_percent, 2),
        "sample_info": {
            "sample_step": sample_step,
            "total_sampled": total_sampled
        }
    }
