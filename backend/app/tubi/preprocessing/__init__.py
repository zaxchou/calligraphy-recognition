"""
预处理标准化模块

Phase 0: 输入预处理标准化层
所有画作先经过统一预处理，消除底色/扫描差异，再进入后续CV/LLM处理流程。
"""

from .standardizer import preprocess_standardize, StandardizedImage
from .group_classifier import classify_image_group, PaintingGroup, GroupClassification

__all__ = [
    "preprocess_standardize",
    "StandardizedImage",
    "classify_image_group",
    "PaintingGroup",
    "GroupClassification",
]