"""
文字区域mask提取策略

核心思路：
- 文字区域有强烈的行列结构特征（水平/垂直方向的周期性）
- 使用投影分析检测周期性密集区域
- 相对阈值：基于全图投影的统计值判断

输出：二值mask，文字区域为255
"""

import cv2
import numpy as np
from typing import Tuple


def extract_text_mask(
    img_bgr: np.ndarray,
    paper_lab: np.ndarray,
) -> np.ndarray:
    """
    提取文字区域mask
    
    参数：
        img_bgr: 预处理后的BGR图像
        paper_lab: 纸张底色LAB值
    
    返回：
        二值mask，文字区域为255
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # 1. 获取墨迹候选
    paper_L = float(paper_lab[0])
    darkness_factor = max(0.3, min(0.7, (255 - paper_L) / 100.0))
    relative_thresh = int(paper_L * (1.0 - darkness_factor * 0.3))
    _, ink_candidates = cv2.threshold(gray, relative_thresh, 255, cv2.THRESH_BINARY_INV)
    
    # 2. 计算水平和垂直投影
    h_proj = np.sum(ink_candidates, axis=1) / 255.0  # 每行的墨迹像素数
    v_proj = np.sum(ink_candidates, axis=0) / 255.0  # 每列的墨迹像素数
    
    # 3. 检测周期性（文字行列结构）
    # 计算投影的局部最大值密度
    def detect_periodicity(proj: np.ndarray, window_size: int = 15) -> np.ndarray:
        """检测投影的周期性强度"""
        proj_smooth = np.convolve(proj, np.ones(window_size)/window_size, mode='same')
        # 局部峰值
        peaks = np.zeros_like(proj)
        for i in range(1, len(proj)-1):
            if proj_smooth[i] > proj_smooth[i-1] and proj_smooth[i] > proj_smooth[i+1]:
                peaks[i] = proj_smooth[i]
        return peaks
    
    h_peaks = detect_periodicity(h_proj, window_size=max(5, h // 80))
    v_peaks = detect_periodicity(v_proj, window_size=max(5, w // 80))
    
    # 4. 相对阈值：峰值强度超过投影均值的一定倍数
    h_mean = float(np.mean(h_proj))
    v_mean = float(np.mean(v_proj))
    
    h_peak_threshold = h_mean * 1.5
    v_peak_threshold = v_mean * 1.5
    
    # 5. 构建文字区域mask
    text_mask = np.zeros((h, w), dtype=np.uint8)
    
    # 水平方向：找到有周期性峰值的行
    h_text_rows = h_peaks > h_peak_threshold
    # 垂直方向：找到有周期性峰值的列
    v_text_cols = v_peaks > v_peak_threshold
    
    # 文字区域 = 既有水平周期性又有垂直周期性的区域
    for y in range(h):
        if h_text_rows[y]:
            for x in range(w):
                if v_text_cols[x] and ink_candidates[y, x] > 0:
                    text_mask[y, x] = 255
    
    # 6. 扩展和优化
    # 闭运算连接相邻文字
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
    text_mask = cv2.morphologyEx(text_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # 开运算去除孤立噪点
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    text_mask = cv2.morphologyEx(text_mask, cv2.MORPH_OPEN, kernel_open, iterations=1)
    
    return text_mask
