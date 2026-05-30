"""
图像预处理标准化核心模块

功能：
1. 光照校准（CLAHE自适应局部均衡化）
2. 颜色归一化（统一到标准宣纸色彩空间）
3. 噪声过滤（自适应中值滤波）
4. 分辨率归一化（长边2048px）

所有参数基于当前图像统计值自适应计算，无硬编码阈值。
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import cv2
import numpy as np


# 标准宣纸参考色（LAB空间，基于大量李鱓作品统计的中位数）
# L: 亮度(0-255), a: 绿-红(-128~127), b: 蓝-黄(-128~127)
REFERENCE_XUANZHI_LAB = np.array([225.0, 2.0, 12.0], dtype=np.float32)

# 目标输出长边尺寸
TARGET_LONG_EDGE = 2048


@dataclass
class StandardizedImage:
    """标准化后的图像及统计信息"""
    image: np.ndarray                    # 标准化后的BGR图像 (H, W, 3)
    original_path: str                   # 原始图像路径
    original_size: Tuple[int, int]       # 原始尺寸 (width, height)
    scale_ratio: float                   # 缩放比例（标准化/原始）
    
    # 图像统计特征（用于画群分类）
    brightness_median: float             # 亮度中位数 (0-255)
    brightness_std: float                # 亮度标准差
    saturation_median: float             # 饱和度中位数 (0-255)
    saturation_std: float                # 饱和度标准差
    texture_complexity: float            # 纹理复杂度（Laplacian方差）
    paper_base_lab: np.ndarray           # 纸张底色LAB值 (3,)
    contrast_score: float                # 对比度评分 (p90-p10)
    
    # 预处理参数记录（用于调试和复现）
    clahe_params: dict                   # CLAHE参数
    color_shift: np.ndarray              # 颜色偏移量 LAB (3,)


def _estimate_paper_color_lab(img_bgr: np.ndarray, border_ratio: float = 0.08) -> np.ndarray:
    """
    从图像边缘估计纸张底色（LAB空间）
    
    策略：
    - 取图像四边 border_ratio 宽度的区域
    - 过滤掉梯度大的区域（排除墨迹/绘画内容）
    - 用剩余像素的中位数作为纸张色
    
    返回: LAB颜色向量 [L, a, b]
    """
    h, w = img_bgr.shape[:2]
    border = max(5, int(min(h, w) * border_ratio))
    
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    grad = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
    grad_abs = np.abs(grad)
    
    # 构建边缘mask
    edge_mask = np.zeros((h, w), dtype=np.uint8)
    edge_mask[:border, :] = 1
    edge_mask[-border:, :] = 1
    edge_mask[:, :border] = 1
    edge_mask[:, -border:] = 1
    
    # 只保留低梯度区域（纸张，而非墨迹）
    grad_threshold = np.percentile(grad_abs[edge_mask > 0], 60)
    paper_mask = (edge_mask > 0) & (grad_abs < grad_threshold)
    
    if np.count_nonzero(paper_mask) < 100:
        #  fallback：用全图低梯度区域
        grad_threshold = np.percentile(grad_abs, 30)
        paper_mask = grad_abs < grad_threshold
    
    paper_pixels = img_bgr[paper_mask]
    lab_pixels = cv2.cvtColor(paper_pixels.reshape(-1, 1, 3).astype(np.uint8), 
                              cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    
    # 用中位数而非均值，更鲁棒
    paper_lab = np.median(lab_pixels, axis=0)
    return paper_lab


def _adaptive_clahe(img_bgr: np.ndarray) -> Tuple[np.ndarray, dict]:
    """
    自适应CLAHE光照校准
    
    参数自适应逻辑：
    - clipLimit：基于图像对比度自适应，对比度低->限制大，对比度高->限制小
    - tileGridSize：基于图像尺寸自适应
    """
    h, w = img_bgr.shape[:2]
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0].astype(np.float32)
    
    # 自适应计算clipLimit
    contrast = float(np.percentile(l_channel, 90) - np.percentile(l_channel, 10))
    # 对比度低（暗底/淡墨画）需要更强的增强，但上限保护
    clip_limit = float(np.clip(3.0 + (80.0 - contrast) / 20.0, 1.5, 6.0))
    
    # 自适应tileGridSize：小图用小tile，大图用大tile
    tile_size = max(8, min(64, int(min(h, w) / 32)))
    tile_size = tile_size // 8 * 8  # 必须是8的倍数
    if tile_size < 8:
        tile_size = 8
    
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    params = {
        "clip_limit": clip_limit,
        "tile_grid_size": tile_size,
        "original_contrast": contrast,
    }
    return result, params


def _color_normalization(img_bgr: np.ndarray, paper_lab: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    颜色归一化：将画面纸张色统一到标准宣纸色
    
    策略：
    - 计算当前纸张色与标准宣纸色的LAB偏移
    - 对整个图像应用偏移（保持墨迹与纸张的相对关系）
    - 避免过度校正导致色彩失真
    """
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    
    # 计算颜色偏移
    color_shift = REFERENCE_XUANZHI_LAB - paper_lab
    
    # 限制偏移量，防止过度校正（特别是a/b通道）
    max_shift = np.array([40.0, 15.0, 20.0], dtype=np.float32)
    color_shift = np.clip(color_shift, -max_shift, max_shift)
    
    # 应用偏移
    lab_shifted = lab + color_shift.reshape(1, 1, 3)
    
    # 限制到有效范围
    lab_shifted[:, :, 0] = np.clip(lab_shifted[:, :, 0], 0, 255)
    lab_shifted[:, :, 1] = np.clip(lab_shifted[:, :, 1], 0, 255)
    lab_shifted[:, :, 2] = np.clip(lab_shifted[:, :, 2], 0, 255)
    
    result = cv2.cvtColor(lab_shifted.astype(np.uint8), cv2.COLOR_LAB2BGR)
    return result, color_shift


def _adaptive_noise_filter(img_bgr: np.ndarray) -> np.ndarray:
    """
    自适应噪声过滤
    
    策略：
    - 先检测图像噪声水平（边缘区域的标准差）
    - 噪声高->用更强的滤波，噪声低->轻滤波保护细节
    - 使用自适应中值滤波，根据局部统计调整核大小
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # 估计噪声水平（用边缘区域的灰度标准差）
    border = max(5, int(min(h, w) * 0.05))
    border_pixels = np.concatenate([
        gray[:border, :].reshape(-1),
        gray[-border:, :].reshape(-1),
        gray[:, :border].reshape(-1),
        gray[:, -border:].reshape(-1),
    ])
    noise_level = float(np.std(border_pixels))
    
    # 自适应滤波强度
    if noise_level > 25:
        # 高噪声（老旧扫描件/污渍多）：双边滤波+轻中值
        result = cv2.bilateralFilter(img_bgr, d=5, sigmaColor=30, sigmaSpace=30)
        result = cv2.medianBlur(result, ksize=3)
    elif noise_level > 15:
        # 中等噪声：轻双边滤波
        result = cv2.bilateralFilter(img_bgr, d=3, sigmaColor=20, sigmaSpace=20)
    else:
        # 低噪声：极轻微滤波，保护细节
        result = cv2.bilateralFilter(img_bgr, d=3, sigmaColor=10, sigmaSpace=10)
    
    return result


def _resize_long_edge(img_bgr: np.ndarray, target_long_edge: int = TARGET_LONG_EDGE) -> Tuple[np.ndarray, float]:
    """
    分辨率归一化：统一缩放到长边target_long_edge
    
    返回: (缩放后的图像, 缩放比例)
    """
    h, w = img_bgr.shape[:2]
    long_edge = max(h, w)
    
    if long_edge <= target_long_edge:
        return img_bgr.copy(), 1.0
    
    scale = target_long_edge / float(long_edge)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale


def _compute_image_stats(img_bgr: np.ndarray) -> dict:
    """
    计算图像统计特征（用于画群分类）
    
    返回关键统计值：
    - brightness_median: 亮度中位数
    - brightness_std: 亮度标准差
    - saturation_median: 饱和度中位数
    - saturation_std: 饱和度标准差
    - texture_complexity: 纹理复杂度（Laplacian方差）
    - contrast_score: 对比度评分
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # 亮度统计
    brightness_median = float(np.median(gray))
    brightness_std = float(np.std(gray))
    
    # 饱和度统计（排除极暗/极亮区域）
    sat = hsv[:, :, 1].astype(np.float32)
    valid_sat = sat[(gray > 15) & (gray < 240)]
    if len(valid_sat) > 0:
        saturation_median = float(np.median(valid_sat))
        saturation_std = float(np.std(valid_sat))
    else:
        saturation_median = 0.0
        saturation_std = 0.0
    
    # 纹理复杂度（Laplacian方差，越高越复杂）
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    texture_complexity = float(np.var(laplacian))
    
    # 对比度评分（p90-p10）
    p10, p90 = np.percentile(gray.reshape(-1).astype(np.float32), [10, 90])
    contrast_score = float(p90 - p10)
    
    return {
        "brightness_median": brightness_median,
        "brightness_std": brightness_std,
        "saturation_median": saturation_median,
        "saturation_std": saturation_std,
        "texture_complexity": texture_complexity,
        "contrast_score": contrast_score,
    }


def preprocess_standardize(image_path: str) -> StandardizedImage:
    """
    主入口：对输入图像进行完整的预处理标准化
    
    处理流程：
    1. 读取原始图像
    2. 分辨率归一化（长边2048px）
    3. 估计纸张底色（LAB）
    4. 光照校准（自适应CLAHE）
    5. 颜色归一化（统一到标准宣纸色）
    6. 噪声过滤（自适应中值/双边滤波）
    7. 计算统计特征
    
    返回 StandardizedImage 对象
    """
    # 1. 读取图像
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"无法读取图像: {image_path}")
    
    original_h, original_w = img.shape[:2]
    
    # 2. 分辨率归一化
    img_resized, scale = _resize_long_edge(img, TARGET_LONG_EDGE)
    
    # 3. 估计纸张底色（在缩放后的图像上计算，更稳定）
    paper_lab = _estimate_paper_color_lab(img_resized)
    
    # 4. 光照校准
    img_clahe, clahe_params = _adaptive_clahe(img_resized)
    
    # 5. 颜色归一化
    img_normalized, color_shift = _color_normalization(img_clahe, paper_lab)
    
    # 6. 噪声过滤
    img_denoised = _adaptive_noise_filter(img_normalized)
    
    # 7. 计算统计特征（在最终图像上）
    stats = _compute_image_stats(img_denoised)
    
    return StandardizedImage(
        image=img_denoised,
        original_path=image_path,
        original_size=(original_w, original_h),
        scale_ratio=scale,
        brightness_median=stats["brightness_median"],
        brightness_std=stats["brightness_std"],
        saturation_median=stats["saturation_median"],
        saturation_std=stats["saturation_std"],
        texture_complexity=stats["texture_complexity"],
        paper_base_lab=paper_lab,
        contrast_score=stats["contrast_score"],
        clahe_params=clahe_params,
        color_shift=color_shift,
    )


def preprocess_standardize_from_array(img_bgr: np.ndarray, original_path: str = "") -> StandardizedImage:
    """
    从numpy数组进行预处理（用于已有内存中图像的场景）
    """
    original_h, original_w = img_bgr.shape[:2]
    
    img_resized, scale = _resize_long_edge(img_bgr, TARGET_LONG_EDGE)
    paper_lab = _estimate_paper_color_lab(img_resized)
    img_clahe, clahe_params = _adaptive_clahe(img_resized)
    img_normalized, color_shift = _color_normalization(img_clahe, paper_lab)
    img_denoised = _adaptive_noise_filter(img_normalized)
    stats = _compute_image_stats(img_denoised)
    
    return StandardizedImage(
        image=img_denoised,
        original_path=original_path,
        original_size=(original_w, original_h),
        scale_ratio=scale,
        brightness_median=stats["brightness_median"],
        brightness_std=stats["brightness_std"],
        saturation_median=stats["saturation_median"],
        saturation_std=stats["saturation_std"],
        texture_complexity=stats["texture_complexity"],
        paper_base_lab=paper_lab,
        contrast_score=stats["contrast_score"],
        clahe_params=clahe_params,
        color_shift=color_shift,
    )
