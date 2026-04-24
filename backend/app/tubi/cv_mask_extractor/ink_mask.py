"""
墨迹mask提取策略

核心思路：
- 基于局部窗口内的密度与窗口外密度的比值判断墨迹
- 使用自适应阈值（Otsu + 局部均值偏移）而非固定阈值
- 支持暗底/亮底画自适应

输出：二值mask，墨迹区域为255
"""

import cv2
import numpy as np
from typing import Tuple


def extract_ink_mask(
    img_bgr: np.ndarray,
    paper_lab: np.ndarray,
) -> np.ndarray:
    """
    提取墨迹mask
    
    参数：
        img_bgr: 预处理后的BGR图像
        paper_lab: 纸张底色LAB值（用于自适应阈值计算）
    
    返回：
        二值mask (H, W)，墨迹区域为255
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # 策略1: Otsu自适应阈值（全局）
    otsu_val, otsu_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 策略2: 基于纸张亮度的自适应阈值
    # 纸张L值越低（越暗），阈值偏移越大
    paper_L = float(paper_lab[0])
    # 相对阈值：比纸张亮度暗一定比例的区域视为墨迹
    # 暗底画(paper_L低)用更大的偏移，避免把底色当墨迹
    darkness_factor = max(0.3, min(0.7, (255 - paper_L) / 100.0))
    relative_thresh = int(paper_L * (1.0 - darkness_factor * 0.35))
    _, relative_mask = cv2.threshold(gray, relative_thresh, 255, cv2.THRESH_BINARY_INV)
    
    # 策略3: 局部自适应阈值（高斯加权）
    # 块大小基于图像尺寸自适应
    block_size = max(11, min(51, int(min(h, w) / 20)))
    if block_size % 2 == 0:
        block_size += 1
    adaptive_mask = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        C=8
    )
    
    # 策略4: 梯度边缘辅助（适度收紧：2.0x）
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)
    
    grad_mean = float(np.mean(grad_mag))
    grad_threshold = grad_mean * 2.0
    edge_mask = (grad_mag > grad_threshold).astype(np.uint8) * 255
    
    # 策略5: 纹理一致性过滤（新增，宽松阈值）
    # 书法笔画有方差高且方向性强的特点，纸张噪点方差低且均匀
    gray_f = gray.astype(np.float32)
    local_mean = cv2.blur(gray_f, (15, 15))
    local_mean_sq = cv2.blur(gray_f * gray_f, (15, 15))
    local_var = local_mean_sq - local_mean * local_mean
    local_var = np.sqrt(np.maximum(local_var, 0))
    
    # 宽松阈值：只过滤明显均匀的噪点（低于中位数30%）
    var_median = float(np.median(local_var))
    var_threshold = var_median * 0.3
    texture_mask = (local_var > var_threshold).astype(np.uint8) * 255
    
    # 融合策略：核心墨迹保持原有，只对弱路径加约束
    # 核心墨迹 = Otsu和相对阈值交集（不改，确保不漏真墨迹）
    core_ink = cv2.bitwise_and(otsu_mask, relative_mask)
    # 弱墨迹 = adaptive AND relative AND texture（加texture约束去除噪点）
    weak_ink = cv2.bitwise_and(
        cv2.bitwise_and(adaptive_mask, relative_mask),
        texture_mask
    )
    combined = cv2.bitwise_or(core_ink, weak_ink)
    # 边缘补充（适度收紧）
    edge_supplement = cv2.bitwise_and(edge_mask, relative_mask)
    combined = cv2.bitwise_or(combined, edge_supplement)
    
    # 形态学：闭运算核从5x5降到3x3，减少过度连接
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_close, iterations=1)
    
    # 开运算核保持3x3，去除细小噪点
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel_open, iterations=1)
    
    return combined
