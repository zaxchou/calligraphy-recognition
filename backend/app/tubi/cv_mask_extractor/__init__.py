"""
CV多策略mask提取模块

Phase 2: CV多策略mask提取器

提供5种全相对阈值的mask提取策略：
1. 自适应阈值墨迹mask（相对局部均值）
2. 颜色偏差印章mask（相对全图主色）
3. 行列投影文字mask（相对周期性）
4. 纹理密度mask（相对密度排名）
5. 连通域分类mask（相对面积/长宽比）

所有阈值基于当前图像统计值自适应计算，无硬编码固定阈值。
"""

from .ink_mask import extract_ink_mask
from .seal_mask import extract_seal_mask
from .text_mask import extract_text_mask
from .texture_mask import extract_texture_mask
from .connected_mask import extract_connected_mask
from .ensemble import ensemble_masks, MaskSet

__all__ = [
    "extract_ink_mask",
    "extract_seal_mask",
    "extract_text_mask",
    "extract_texture_mask",
    "extract_connected_mask",
    "ensemble_masks",
    "MaskSet",
]
