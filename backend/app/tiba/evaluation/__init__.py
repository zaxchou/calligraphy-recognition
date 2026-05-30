"""
CV-First Ground Truth 评估模块

基于143张手动标注数据，系统化优化分割算法
"""

from .iou_evaluator import compute_iou, evaluate_image, polygons_to_mask
from .gt_loader import load_ground_truth, GroundTruthRecord

__all__ = [
    "compute_iou",
    "evaluate_image", 
    "polygons_to_mask",
    "load_ground_truth",
    "GroundTruthRecord",
]
