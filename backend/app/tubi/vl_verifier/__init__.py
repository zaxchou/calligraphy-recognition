"""
VL校验模块

Phase 4: VL校验层

当LLM分类置信度低时，自动调用VL模型进行校验。
策略：
- 只对低置信度区域进行裁切校验
- 复用现有系统的VL调用能力
- 校验结果用于修正分类
"""

from .verifier import verify_low_confidence_regions

__all__ = ["verify_low_confidence_regions"]
