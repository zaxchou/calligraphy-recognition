"""
IoU计算引擎：多边形填充 → Mask → 像素级交并比

核心功能：
1. 将多边形列表填充为二值mask
2. 计算两个mask的IoU
3. 评估单张图的预测regions vs ground truth
"""

import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class IoUResult:
    """单张图的IoU评估结果"""
    inscription_iou: float
    painting_iou: float
    blank_iou: float
    overall_iou: float
    # 各区域面积（像素）
    gt_insc_area: int
    gt_paint_area: int
    gt_blank_area: int
    pred_insc_area: int
    pred_paint_area: int
    pred_blank_area: int
    # 错误类型标签
    error_types: List[str]


def polygons_to_mask(polygons: List[Dict], width: int, height: int) -> np.ndarray:
    """
    将多边形列表填充为二值mask
    
    参数:
        polygons: 多边形列表，每个多边形格式: {"type": "polygon", "points": [{"x": float, "y": float}, ...]}
        width: 图像宽度
        height: 图像高度
    
    返回:
        np.ndarray: 二值mask (H, W), uint8, 255=填充区域
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    
    for poly in polygons:
        points = poly.get("points", [])
        if len(points) < 3:
            continue
        
        # 提取坐标
        pts = np.array([[int(p["x"]), int(p["y"])] for p in points], dtype=np.int32)
        pts = pts.reshape((-1, 1, 2))
        
        cv2.fillPoly(mask, [pts], 255)
    
    return mask


def compute_iou(pred_mask: np.ndarray, gt_mask: np.ndarray) -> float:
    """
    计算两mask的交并比 (Intersection over Union)
    
    IoU = |pred ∩ gt| / |pred ∪ gt|
    
    参数:
        pred_mask: 预测mask, uint8, 255=前景
        gt_mask: ground truth mask, uint8, 255=前景
    
    返回:
        float: IoU值 [0.0, 1.0]
    """
    pred_bin = (pred_mask > 0).astype(np.uint8)
    gt_bin = (gt_mask > 0).astype(np.uint8)
    
    intersection = np.logical_and(pred_bin, gt_bin).sum()
    union = np.logical_or(pred_bin, gt_bin).sum()
    
    if union == 0:
        # 两者都为空 → 视为完美匹配
        return 1.0 if intersection == 0 else 0.0
    
    return float(intersection) / float(union)


def compute_class_iou(pred_mask: np.ndarray, gt_mask: np.ndarray) -> Tuple[float, int, int]:
    """
    计算单类别的IoU及面积信息
    
    返回: (iou, gt_area, pred_area)
    """
    pred_bin = (pred_mask > 0).astype(np.uint8)
    gt_bin = (gt_mask > 0).astype(np.uint8)
    
    intersection = int(np.logical_and(pred_bin, gt_bin).sum())
    union = int(np.logical_or(pred_bin, gt_bin).sum())
    gt_area = int(gt_bin.sum())
    pred_area = int(pred_bin.sum())
    
    if union == 0:
        return (1.0 if intersection == 0 else 0.0, gt_area, pred_area)
    
    return float(intersection) / float(union), gt_area, pred_area


def classify_errors(
    pred_regions: Dict,
    gt_regions: Dict,
    insc_iou: float,
    paint_iou: float,
    blank_iou: float,
    gt_areas: Dict[str, int],
    pred_areas: Dict[str, int],
) -> List[str]:
    """
    基于IoU结果和区域信息分类错误类型
    
    错误类型:
    - fragmentation: 碎片化（预测区域数量 >> GT区域数量，IoU低但非零）
    - false_negative: 漏检（GT有但预测完全为空或IoU≈0）
    - false_positive: 误检（预测有但GT为空或IoU≈0）
    - category_confusion: 类别混淆（不同类别间的面积显著不匹配）
    - boundary_error: 边界偏差（IoU在0.3-0.7之间，检测到但不准）
    """
    errors = []
    
    gt_insc = gt_regions.get("inscription_regions", [])
    gt_paint = gt_regions.get("painting_regions", [])
    gt_blank = gt_regions.get("blank_regions", [])
    
    pred_insc = pred_regions.get("inscription_regions", [])
    pred_paint = pred_regions.get("painting_regions", [])
    pred_blank = pred_regions.get("blank_regions", [])
    
    # Type A: 碎片化 - 预测区域数量显著多于GT，且IoU低
    total_gt = len(gt_insc) + len(gt_paint) + len(gt_blank)
    total_pred = len(pred_insc) + len(pred_paint) + len(pred_blank)
    if total_pred > total_gt * 2 and total_gt > 0:
        errors.append("fragmentation")
    
    # Type B: 漏检 - GT有但预测IoU极低
    if gt_areas["insc"] > 100 and insc_iou < 0.1:
        errors.append("false_negative_insc")
    if gt_areas["paint"] > 100 and paint_iou < 0.1:
        errors.append("false_negative_paint")
    if gt_areas["blank"] > 100 and blank_iou < 0.1:
        errors.append("false_negative_blank")
    
    # Type C: 误检 - 预测有但GT极少或没有，IoU极低
    if pred_areas["insc"] > 100 and gt_areas["insc"] < 100:
        errors.append("false_positive_insc")
    if pred_areas["paint"] > 100 and gt_areas["paint"] < 100:
        errors.append("false_positive_paint")
    if pred_areas["blank"] > 100 and gt_areas["blank"] < 100:
        errors.append("false_positive_blank")
    
    # Type D: 类别混淆 - 题跋面积被预测为绘画，或反之
    # 简单判断：如果题跋IoU很低但绘画IoU较高，且GT题跋面积不小
    if gt_areas["insc"] > 500 and insc_iou < 0.2 and paint_iou > 0.3:
        errors.append("category_confusion_insc_to_paint")
    if gt_areas["paint"] > 500 and paint_iou < 0.2 and insc_iou > 0.3:
        errors.append("category_confusion_paint_to_insc")
    
    # Type E: 边界偏差 - IoU在中等范围
    medium_iou_count = sum(1 for iou in [insc_iou, paint_iou, blank_iou] if 0.2 <= iou < 0.6)
    if medium_iou_count >= 2:
        errors.append("boundary_error")
    
    return errors


def evaluate_image(
    pred_regions: Dict,
    gt_regions: Dict,
    orig_w: int,
    orig_h: int,
) -> IoUResult:
    """
    评估单张图：预测regions vs Ground Truth
    
    参数:
        pred_regions: 预测结果 {"inscription_regions": [...], "painting_regions": [...], "blank_regions": [...]}
        gt_regions: Ground Truth {"inscription_regions": [...], "painting_regions": [...], "blank_regions": [...]}
        orig_w: 原始图像宽度
        orig_h: 原始图像高度
    
    返回:
        IoUResult: 包含各类IoU和错误类型
    """
    # 转mask
    pred_insc_mask = polygons_to_mask(pred_regions.get("inscription_regions", []), orig_w, orig_h)
    pred_paint_mask = polygons_to_mask(pred_regions.get("painting_regions", []), orig_w, orig_h)
    pred_blank_mask = polygons_to_mask(pred_regions.get("blank_regions", []), orig_w, orig_h)
    
    gt_insc_mask = polygons_to_mask(gt_regions.get("inscription_regions", []), orig_w, orig_h)
    gt_paint_mask = polygons_to_mask(gt_regions.get("painting_regions", []), orig_w, orig_h)
    gt_blank_mask = polygons_to_mask(gt_regions.get("blank_regions", []), orig_w, orig_h)
    
    # 计算各类IoU
    insc_iou, gt_insc_area, pred_insc_area = compute_class_iou(pred_insc_mask, gt_insc_mask)
    paint_iou, gt_paint_area, pred_paint_area = compute_class_iou(pred_paint_mask, gt_paint_mask)
    blank_iou, gt_blank_area, pred_blank_area = compute_class_iou(pred_blank_mask, gt_blank_mask)
    
    # 综合IoU: 按GT面积加权平均
    total_gt_area = gt_insc_area + gt_paint_area + gt_blank_area
    if total_gt_area > 0:
        overall_iou = (
            insc_iou * gt_insc_area +
            paint_iou * gt_paint_area +
            blank_iou * gt_blank_area
        ) / total_gt_area
    else:
        overall_iou = 0.0
    
    # 错误分类
    gt_areas = {"insc": gt_insc_area, "paint": gt_paint_area, "blank": gt_blank_area}
    pred_areas = {"insc": pred_insc_area, "paint": pred_paint_area, "blank": pred_blank_area}
    error_types = classify_errors(
        pred_regions, gt_regions,
        insc_iou, paint_iou, blank_iou,
        gt_areas, pred_areas,
    )
    
    return IoUResult(
        inscription_iou=insc_iou,
        painting_iou=paint_iou,
        blank_iou=blank_iou,
        overall_iou=overall_iou,
        gt_insc_area=gt_insc_area,
        gt_paint_area=gt_paint_area,
        gt_blank_area=gt_blank_area,
        pred_insc_area=pred_insc_area,
        pred_paint_area=pred_paint_area,
        pred_blank_area=pred_blank_area,
        error_types=error_types,
    )
