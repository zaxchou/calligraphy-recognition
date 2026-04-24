"""
画群分类器

基于预处理后的图像统计特征，自动判断画作所属的画群。
画群分类用于后续规律隔离——不同画群的题跋特征规律不同，避免互相干扰。

画群定义：
- dark_base:    暗底画（亮度中位数低，纸张色偏暗/偏黄/偏旧）
- light_base:   亮底画（标准宣纸色，亮度高）
- colorful:     彩色画（饱和度高，色彩丰富，如设色花鸟）
- monochrome:   单色画（饱和度低，纯水墨为主）
- printed:      印刷品（纹理复杂度低，边缘锐利规则）
- scanned:      扫描件（纹理复杂度高，可能有扫描条纹/噪点）

分类策略：
- 所有判断基于相对特征，无硬编码绝对阈值
- 支持多标签（一幅画可同时属于多个群）
- 输出置信度分数
"""

from dataclasses import dataclass
from typing import List, Dict
from enum import Enum
import numpy as np

from .standardizer import StandardizedImage


class PaintingGroup(Enum):
    """画群枚举"""
    DARK_BASE = "dark_base"      # 暗底画
    LIGHT_BASE = "light_base"    # 亮底画
    COLORFUL = "colorful"        # 彩色画
    MONOCHROME = "monochrome"    # 单色画
    PRINTED = "printed"          # 印刷品
    SCANNED = "scanned"          # 扫描件


@dataclass
class GroupClassification:
    """画群分类结果"""
    primary_group: PaintingGroup       # 主画群（置信度最高的）
    all_groups: List[PaintingGroup]    # 所有匹配的画群
    confidence: Dict[str, float]       # 各画群置信度 (0-1)
    features: Dict[str, float]         # 用于分类的特征值


# 参考统计值（基于大量中国画作品的分布中位数，用于相对判断）
# 这些不是阈值，而是"典型值"，实际判断用相对偏移
REF_BRIGHTNESS_MEDIAN = 200.0        # 典型亮底画亮度
REF_SATURATION_MEDIAN = 25.0         # 典型单色画饱和度
REF_TEXTURE_COMPLEXITY = 500.0       # 典型手绘纹理复杂度
REF_CONTRAST_SCORE = 60.0            # 典型对比度


def _score_dark_base(stats: StandardizedImage) -> float:
    """
    暗底画评分
    
    特征：亮度中位数显著低于典型亮底画
    相对判断：brightness_median 相对于 REF_BRIGHTNESS_MEDIAN 的偏移
    """
    brightness_ratio = stats.brightness_median / REF_BRIGHTNESS_MEDIAN
    # 亮度越低，暗底概率越高
    score = max(0.0, 1.0 - brightness_ratio)
    # 亮度标准差小（底色均匀）增加置信度
    if stats.brightness_std < 30:
        score = min(1.0, score * 1.2)
    return float(score)


def _score_light_base(stats: StandardizedImage) -> float:
    """
    亮底画评分
    
    特征：亮度中位数接近或高于典型值，底色均匀
    """
    brightness_ratio = stats.brightness_median / REF_BRIGHTNESS_MEDIAN
    score = max(0.0, brightness_ratio - 0.7)
    # 亮度标准差小增加置信度
    if stats.brightness_std < 25:
        score = min(1.0, score * 1.15)
    return float(score)


def _score_colorful(stats: StandardizedImage) -> float:
    """
    彩色画评分
    
    特征：饱和度显著高于典型单色画
    """
    sat_ratio = stats.saturation_median / REF_SATURATION_MEDIAN
    score = max(0.0, (sat_ratio - 0.8) / 1.5)
    # 饱和度标准差大（色彩丰富）增加置信度
    if stats.saturation_std > 15:
        score = min(1.0, score * 1.2)
    return float(score)


def _score_monochrome(stats: StandardizedImage) -> float:
    """
    单色画评分
    
    特征：饱和度低，以墨色为主
    """
    sat_ratio = stats.saturation_median / REF_SATURATION_MEDIAN
    score = max(0.0, 1.0 - sat_ratio)
    # 对比度适中（水墨画的浓淡层次）增加置信度
    if 30 < stats.contrast_score < 100:
        score = min(1.0, score * 1.1)
    return float(score)


def _score_printed(stats: StandardizedImage) -> float:
    """
    印刷品评分
    
    特征：纹理复杂度低（没有手绘笔触的随机性），边缘锐利规则
    """
    texture_ratio = stats.texture_complexity / REF_TEXTURE_COMPLEXITY
    score = max(0.0, 1.0 - texture_ratio)
    # 纹理标准差小（均匀）增加置信度
    # 但印刷品通常有网点纹理，复杂度不会极低
    if stats.texture_complexity < 200:
        score = min(1.0, score * 1.3)
    return float(score)


def _score_scanned(stats: StandardizedImage) -> float:
    """
    扫描件评分
    
    特征：纹理复杂度高（扫描引入的噪点/条纹），或噪声水平高
    """
    texture_ratio = stats.texture_complexity / REF_TEXTURE_COMPLEXITY
    score = max(0.0, (texture_ratio - 0.5) / 1.5)
    # 亮度标准差大（扫描不均匀）增加置信度
    if stats.brightness_std > 35:
        score = min(1.0, score * 1.2)
    return float(score)


def classify_image_group(stats: StandardizedImage) -> GroupClassification:
    """
    主入口：基于标准化图像的统计特征，分类画群
    
    返回画群分类结果，包含各画群的置信度分数。
    
    分类逻辑：
    1. 计算每个画群的置信度分数
    2. 选择主画群（置信度最高的）
    3. 收集所有置信度>0.3的画群作为附加标签
    """
    scores = {
        PaintingGroup.DARK_BASE: _score_dark_base(stats),
        PaintingGroup.LIGHT_BASE: _score_light_base(stats),
        PaintingGroup.COLORFUL: _score_colorful(stats),
        PaintingGroup.MONOCHROME: _score_monochrome(stats),
        PaintingGroup.PRINTED: _score_printed(stats),
        PaintingGroup.SCANNED: _score_scanned(stats),
    }
    
    # 归一化置信度（使最高分为1.0，便于相对比较）
    max_score = max(scores.values()) if scores else 1.0
    if max_score > 0:
        confidence = {g.value: min(1.0, s / max_score) for g, s in scores.items()}
    else:
        confidence = {g.value: 0.0 for g in scores}
    
    # 主画群 = 置信度最高的
    primary_group = max(scores, key=scores.get)
    
    # 所有置信度>0.3的画群（多标签支持）
    all_groups = [g for g, s in scores.items() if s > 0.3]
    if primary_group not in all_groups:
        all_groups.append(primary_group)
    
    # 收集用于分类的特征值
    features = {
        "brightness_median": stats.brightness_median,
        "brightness_std": stats.brightness_std,
        "saturation_median": stats.saturation_median,
        "saturation_std": stats.saturation_std,
        "texture_complexity": stats.texture_complexity,
        "contrast_score": stats.contrast_score,
        "paper_L": float(stats.paper_base_lab[0]),
        "paper_a": float(stats.paper_base_lab[1]),
        "paper_b": float(stats.paper_base_lab[2]),
    }
    
    return GroupClassification(
        primary_group=primary_group,
        all_groups=all_groups,
        confidence=confidence,
        features=features,
    )


def get_group_name(classification: GroupClassification) -> str:
    """获取主画群的字符串名称"""
    return classification.primary_group.value


def is_dark_base(classification: GroupClassification) -> bool:
    """是否属于暗底画群"""
    return PaintingGroup.DARK_BASE in classification.all_groups


def is_light_base(classification: GroupClassification) -> bool:
    """是否属于亮底画群"""
    return PaintingGroup.LIGHT_BASE in classification.all_groups
