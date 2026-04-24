"""
连通域分类mask提取策略

核心思路：
- 对墨迹mask进行连通域分析
- 根据连通域的面积、长宽比、密度等特征分类
- 文字连通域：小面积、高长宽比、密集
- 印章连通域：中等面积、近方形、实心
- 绘画连通域：大面积、不规则、低密度

输出：分类后的区域mask字典
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple


def extract_connected_mask(
    img_bgr: np.ndarray,
    ink_mask: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    基于连通域特征分类提取mask
    
    参数：
        img_bgr: 预处理后的BGR图像
        ink_mask: 墨迹二值mask
    
    返回：
        字典，包含：
        - text: 文字区域mask
        - seal: 印章区域mask
        - painting: 绘画区域mask
        - noise: 噪点mask
    """
    h, w = img_bgr.shape[:2]
    total_area = h * w
    
    # 连通域分析
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(ink_mask, connectivity=8)
    
    # 初始化各类mask
    text_mask = np.zeros((h, w), dtype=np.uint8)
    seal_mask = np.zeros((h, w), dtype=np.uint8)
    painting_mask = np.zeros((h, w), dtype=np.uint8)
    noise_mask = np.zeros((h, w), dtype=np.uint8)
    
    # 相对阈值：基于全图面积的比例
    # 文字：小连通域（<0.1%全图）
    text_area_max = int(total_area * 0.001)
    # 印章：中等连通域（0.05% - 5%全图）
    seal_area_min = int(total_area * 0.0003)
    seal_area_max = int(total_area * 0.05)
    # 绘画：大连通域（>0.5%全图）
    painting_area_min = int(total_area * 0.005)
    
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        comp_width = stats[i, cv2.CC_STAT_WIDTH]
        comp_height = stats[i, cv2.CC_STAT_HEIGHT]
        
        if comp_width == 0 or comp_height == 0:
            continue
        
        aspect_ratio = max(comp_width, comp_height) / min(comp_width, comp_height)
        
        # 分类逻辑
        if area < 20:  # 极小连通域 = 噪点
            noise_mask[labels == i] = 255
        elif area <= text_area_max and aspect_ratio > 2.0:
            # 小面积 + 高长宽比 = 文字笔画
            text_mask[labels == i] = 255
        elif seal_area_min <= area <= seal_area_max and aspect_ratio < 2.5:
            # 中等面积 + 近方形 = 印章
            # 进一步检查实心度
            component_mask = (labels == i).astype(np.uint8) * 255
            contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                hull = cv2.convexHull(contours[0])
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    solidity = float(area) / hull_area
                    if solidity > 0.5:
                        seal_mask[labels == i] = 255
                    else:
                        painting_mask[labels == i] = 255
                else:
                    seal_mask[labels == i] = 255
            else:
                seal_mask[labels == i] = 255
        elif area >= painting_area_min:
            # 大面积 = 绘画主体
            painting_mask[labels == i] = 255
        elif aspect_ratio > 3.0:
            # 细长条 = 可能是题跋行列
            text_mask[labels == i] = 255
        else:
            # 其他归入绘画
            painting_mask[labels == i] = 255
    
    return {
        "text": text_mask,
        "seal": seal_mask,
        "painting": painting_mask,
        "noise": noise_mask,
    }
