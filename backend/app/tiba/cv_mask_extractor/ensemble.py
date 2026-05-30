"""
多策略mask融合模块

将5种CV策略的mask融合为统一的候选区域mask，
输出归一化特征向量供LLM分类器使用。
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import cv2
import numpy as np

from app.tiba.preprocessing import StandardizedImage
from .ink_mask import extract_ink_mask
from .seal_mask import extract_seal_mask
from .text_mask import extract_text_mask
from .texture_mask import extract_texture_mask
from .connected_mask import extract_connected_mask


@dataclass
class MaskSet:
    """多策略mask集合"""
    ink_mask: np.ndarray              # 墨迹mask
    seal_mask: np.ndarray             # 印章mask
    text_mask: np.ndarray             # 文字mask
    texture_density: np.ndarray       # 纹理密度图
    texture_mask: np.ndarray          # 纹理mask
    connected_masks: Dict[str, np.ndarray]  # 连通域分类mask
    
    # 融合后的候选区域
    inscription_candidates: np.ndarray   # 题跋候选区域
    painting_candidates: np.ndarray      # 绘画候选区域
    
    # 每个候选区域的特征向量
    region_features: List[Dict]       # 供LLM分类使用的特征


def ensemble_masks(std_img: StandardizedImage) -> MaskSet:
    """
    主入口：运行所有CV策略并融合结果
    
    参数：
        std_img: 标准化后的图像
    
    返回：
        MaskSet对象，包含所有mask和融合结果
    """
    img = std_img.image
    paper_lab = std_img.paper_base_lab
    
    # 1. 运行各策略
    ink_mask = extract_ink_mask(img, paper_lab)
    seal_mask = extract_seal_mask(img, paper_lab)
    text_mask = extract_text_mask(img, paper_lab)
    texture_density, texture_mask = extract_texture_mask(img, paper_lab)
    connected_masks = extract_connected_mask(img, ink_mask)
    
    # 2. 融合题跋候选区域
    # 题跋 = 文字区域 + 印章区域 + 高纹理密度区域
    inscription_candidates = np.zeros_like(ink_mask)
    inscription_candidates = cv2.bitwise_or(inscription_candidates, text_mask)
    inscription_candidates = cv2.bitwise_or(inscription_candidates, seal_mask)
    # 加入连通域分类中的文字和印章
    inscription_candidates = cv2.bitwise_or(inscription_candidates, connected_masks["text"])
    inscription_candidates = cv2.bitwise_or(inscription_candidates, connected_masks["seal"])
    # 纹理mask中补充（但只取与ink_mask重叠的部分，避免误判）
    texture_ink = cv2.bitwise_and(texture_mask, ink_mask)
    inscription_candidates = cv2.bitwise_or(inscription_candidates, texture_ink)
    
    # 形态学优化
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    inscription_candidates = cv2.morphologyEx(inscription_candidates, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # 3. 融合绘画候选区域（修复：不再是简单的 ink_mask - inscription）
    # 绘画区域必须有：墨迹 + 中等纹理密度（排除空白）
    # 中等纹理密度：density_map > 全图中位数（绘画有笔触纹理，空白纹理低）
    density_flat = texture_density.reshape(-1).astype(np.float32)
    mid_density_thresh = float(np.percentile(density_flat, 50))
    mid_density_mask = (texture_density > mid_density_thresh).astype(np.uint8) * 255
    
    # 基础绘画 = 墨迹 - 题跋，且必须有中等纹理密度
    ink_not_insc = cv2.bitwise_and(ink_mask, cv2.bitwise_not(inscription_candidates))
    painting_candidates = cv2.bitwise_and(ink_not_insc, mid_density_mask)
    
    # 加入连通域分类中的绘画
    painting_candidates = cv2.bitwise_or(painting_candidates, connected_masks["painting"])
    # 纹理mask中的绘画区域（中等密度且非题跋）
    texture_paint = cv2.bitwise_and(texture_mask, cv2.bitwise_not(inscription_candidates))
    painting_candidates = cv2.bitwise_or(painting_candidates, texture_paint)
    
    # 形态学优化（收紧：核从11x11降到7x7）
    kernel_paint = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    painting_candidates = cv2.morphologyEx(painting_candidates, cv2.MORPH_CLOSE, kernel_paint, iterations=1)
    
    # 4. 提取候选区域的特征向量（供LLM分类）
    region_features = _extract_region_features(
        img, ink_mask, seal_mask, text_mask, texture_density,
        inscription_candidates, painting_candidates
    )
    
    return MaskSet(
        ink_mask=ink_mask,
        seal_mask=seal_mask,
        text_mask=text_mask,
        texture_density=texture_density,
        texture_mask=texture_mask,
        connected_masks=connected_masks,
        inscription_candidates=inscription_candidates,
        painting_candidates=painting_candidates,
        region_features=region_features,
    )


def _extract_single_mask_features(
    img: np.ndarray,
    ink_mask: np.ndarray,
    seal_mask: np.ndarray,
    text_mask: np.ndarray,
    texture_density: np.ndarray,
    candidate_mask: np.ndarray,
    source: str,
    h: int,
    w: int,
) -> List[Dict]:
    """从单个候选mask中提取所有连通域的特征"""
    total_pixels = h * w
    features = []
    
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(candidate_mask, connectivity=8)
    
    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < 50:
            continue
        
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        comp_w = int(stats[i, cv2.CC_STAT_WIDTH])
        comp_h = int(stats[i, cv2.CC_STAT_HEIGHT])
        
        region_mask = (labels == i).astype(np.uint8) * 255
        
        area_ratio = float(area) / total_pixels
        
        cx = x + comp_w / 2
        cy = y + comp_h / 2
        center_offset_x = (cx - w / 2) / (w / 2)
        center_offset_y = (cy - h / 2) / (h / 2)
        
        aspect_ratio = max(comp_w, comp_h) / max(1, min(comp_w, comp_h))
        
        ink_in_region = cv2.bitwise_and(ink_mask, region_mask)
        density = float(cv2.countNonZero(ink_in_region)) / max(1, area)
        
        seal_in_region = cv2.bitwise_and(seal_mask, region_mask)
        seal_overlap = float(cv2.countNonZero(seal_in_region)) / max(1, area)
        
        text_in_region = cv2.bitwise_and(text_mask, region_mask)
        text_overlap = float(cv2.countNonZero(text_in_region)) / max(1, area)
        
        texture_in_region = texture_density[region_mask > 0]
        texture_mean = float(np.mean(texture_in_region)) if len(texture_in_region) > 0 else 0.0
        texture_relative = texture_mean / 255.0
        
        features.append({
            "type": "candidate",
            "source": source,
            "cc_label": i,
            "area_ratio": round(area_ratio, 6),
            "center_offset_x": round(center_offset_x, 3),
            "center_offset_y": round(center_offset_y, 3),
            "aspect_ratio": round(aspect_ratio, 2),
            "density": round(density, 3),
            "seal_overlap": round(seal_overlap, 3),
            "text_overlap": round(text_overlap, 3),
            "texture_relative": round(texture_relative, 3),
        })
    
    return features


def _extract_region_features(
    img: np.ndarray,
    ink_mask: np.ndarray,
    seal_mask: np.ndarray,
    text_mask: np.ndarray,
    texture_density: np.ndarray,
    insc_candidates: np.ndarray,
    paint_candidates: np.ndarray,
) -> List[Dict]:
    """
    提取题跋和绘画候选区域的归一化特征向量
    
    现在同时分析两类候选，让LLM能看到所有区域并做出正确分类。
    """
    h, w = img.shape[:2]
    features = []
    
    # 分析题跋候选区域
    insc_features = _extract_single_mask_features(
        img, ink_mask, seal_mask, text_mask, texture_density,
        insc_candidates, "inscription_candidate", h, w
    )
    features.extend(insc_features)
    
    # 分析绘画候选区域（新增：让LLM也能看到被分到绘画候选中的区域）
    paint_features = _extract_single_mask_features(
        img, ink_mask, seal_mask, text_mask, texture_density,
        paint_candidates, "painting_candidate", h, w
    )
    features.extend(paint_features)
    
    return features
    
    return features
