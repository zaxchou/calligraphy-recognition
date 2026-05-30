"""
LLM语义分类模块

Phase 3: LLM语义分类器

基于CV输出的候选区域特征向量，结合画群规律库，
使用LLM进行语义分类，判断每个候选区域是题跋/绘画/留白。

核心设计：
- LLM只做语义判断，不直接看图像
- 输入是CV提取的确定性数值特征
- 规律按画群分类，新图自动匹配对应画群规律
- 输出分类结果 + 置信度
"""

from .classifier import classify_regions, ClassifiedRegion, ClassificationResult
from .rule_library import RuleLibrary, load_rule_library, save_rule_library

__all__ = [
    "classify_regions",
    "ClassifiedRegion",
    "ClassificationResult",
    "RuleLibrary",
    "load_rule_library",
    "save_rule_library",
]
