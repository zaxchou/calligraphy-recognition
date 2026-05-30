"""
印章mask提取策略

核心思路：
- 印章在HSV空间有独特的颜色特征（红色/朱砂色为主）
- 不使用固定HSV范围，而是计算与全图主色的偏差
- 印章通常是规则的方形/圆形，有特定面积范围

输出：二值mask，印章区域为255
"""

import cv2
import numpy as np
from typing import Optional


def extract_seal_mask(
    img_bgr: np.ndarray,
    paper_lab: np.ndarray,
    min_area_ratio: float = 0.0005,   # 最小面积比（相对全图）
    max_area_ratio: float = 0.05,      # 最大面积比
) -> np.ndarray:
    """
    提取印章mask
    
    参数：
        img_bgr: 预处理后的BGR图像
        paper_lab: 纸张底色LAB值
        min_area_ratio: 最小面积比例
        max_area_ratio: 最大面积比例
    
    返回：
        二值mask，印章区域为255
    """
    h, w = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    
    # 计算全图主色（排除极暗极亮区域）
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    valid_mask = (gray > 20) & (gray < 240)
    valid_hsv = hsv[valid_mask]
    
    if len(valid_hsv) < 100:
        return np.zeros((h, w), dtype=np.uint8)
    
    # 主色的HSV中位数
    main_h = float(np.median(valid_hsv[:, 0]))
    main_s = float(np.median(valid_hsv[:, 1]))
    main_v = float(np.median(valid_hsv[:, 2]))
    
    # 策略1: 颜色偏差检测
    # 印章颜色与主色的偏差（H通道环形距离）
    h_channel = hsv[:, :, 0].astype(np.float32)
    s_channel = hsv[:, :, 1].astype(np.float32)
    v_channel = hsv[:, :, 2].astype(np.float32)
    
    # H通道环形距离（OpenCV H范围0-179）
    h_diff = np.abs(h_channel - main_h)
    h_diff = np.minimum(h_diff, 179 - h_diff)
    
    # S和V的偏差
    s_diff = np.abs(s_channel - main_s)
    v_diff = np.abs(v_channel - main_v)
    
    # 综合颜色偏差分数
    # 印章通常：H偏差大（红色vs黄色纸张），S高，V中等
    color_deviation = (h_diff / 90.0) * 0.4 + (s_diff / 255.0) * 0.3 + (v_diff / 255.0) * 0.3
    
    # 相对阈值：偏差大于全图偏差的中位数
    dev_median = float(np.median(color_deviation[valid_mask]))
    dev_threshold = dev_median * 2.5
    seal_candidates = (color_deviation > dev_threshold).astype(np.uint8) * 255
    
    # 策略2: 饱和度辅助（印章通常高饱和）
    sat_relative = s_channel / max(1.0, main_s)
    high_sat = (sat_relative > 1.8).astype(np.uint8) * 255
    
    # 融合
    seal_mask = cv2.bitwise_and(seal_candidates, high_sat)
    
    # 策略3: 形态学过滤（印章通常规则形状）
    # 连通域分析，过滤掉不符合印章特征的连通域
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(seal_mask, connectivity=8)
    
    result = np.zeros((h, w), dtype=np.uint8)
    total_area = h * w
    min_pixels = int(total_area * min_area_ratio)
    max_pixels = int(total_area * max_area_ratio)
    
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_pixels or area > max_pixels:
            continue
        
        # 长宽比检查（印章通常近似方形）
        width = stats[i, cv2.CC_STAT_WIDTH]
        height = stats[i, cv2.CC_STAT_HEIGHT]
        if width == 0 or height == 0:
            continue
        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio > 3.0:  # 太细长，不是印章
            continue
        
        #  solidity检查（印章通常比较实心）
        component_mask = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            hull = cv2.convexHull(contours[0])
            hull_area = cv2.contourArea(hull)
            if hull_area > 0:
                solidity = float(area) / hull_area
                if solidity < 0.4:  # 太松散，不是印章
                    continue
        
        result[labels == i] = 255
    
    return result
