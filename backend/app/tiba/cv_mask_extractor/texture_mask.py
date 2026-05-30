"""
纹理密度mask提取策略

核心思路：
- 文字区域有高频纹理（笔画边缘多）
- 绘画区域有特定方向的纹理（竹叶、花瓣等）
- 留白区域纹理最少
- 使用相对密度排名而非固定阈值

输出：归一化密度图 (0-255) + 二值mask
"""

import cv2
import numpy as np


def extract_texture_mask(
    img_bgr: np.ndarray,
    paper_lab: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    提取纹理密度mask
    
    参数：
        img_bgr: 预处理后的BGR图像
        paper_lab: 纸张底色LAB值
    
    返回：
        (density_map, binary_mask)
        - density_map: 归一化纹理密度图 (H, W), uint8, 0-255
        - binary_mask: 二值mask，高密度区域为255
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # 1. 多尺度纹理特征
    # Laplacian（各向同性边缘）
    laplacian = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))
    
    # Sobel方向梯度
    sobel_x = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    sobel_y = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    
    # 2. 局部纹理密度（使用滑动窗口）
    window_size = max(5, min(21, int(min(h, w) / 40)))
    if window_size % 2 == 0:
        window_size += 1
    
    # 综合纹理响应
    texture_response = laplacian + 0.5 * sobel_x + 0.5 * sobel_y
    
    # 局部均值滤波获取密度
    texture_density = cv2.blur(texture_response, (window_size, window_size))
    
    # 3. 归一化到0-255
    density_max = float(np.max(texture_density))
    density_min = float(np.min(texture_density))
    if density_max > density_min:
        density_map = ((texture_density - density_min) / (density_max - density_min) * 255).astype(np.uint8)
    else:
        density_map = np.zeros((h, w), dtype=np.uint8)
    
    # 4. 相对阈值：基于密度分布的百分位
    # 使用全图密度的高百分位作为阈值
    density_values = density_map.reshape(-1).astype(np.float32)
    
    # 高纹理区域 = 密度高于75百分位
    high_thresh = np.percentile(density_values, 75)
    # 中纹理区域 = 密度高于50百分位
    mid_thresh = np.percentile(density_values, 50)
    
    # 文字通常有最高的纹理密度（笔画边缘密集）
    text_like = (density_map > high_thresh).astype(np.uint8) * 255
    
    # 绘画有中高密度纹理
    paint_like = ((density_map > mid_thresh) & (density_map <= high_thresh)).astype(np.uint8) * 255
    
    # 合并（文字+绘画区域）
    combined = cv2.bitwise_or(text_like, paint_like)
    
    # 5. 形态学优化
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    return density_map, combined
