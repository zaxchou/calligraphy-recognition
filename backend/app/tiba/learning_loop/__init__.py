"""
迭代学习模块

Phase 5: 迭代学习机制

支持两种学习模式：
1. 实时学习：每次手动标注后，自动对比自动结果和手动结果，更新规律库
2. 批量优化：定期全量跑评估，调优CV参数和LLM规律
3. 跨群测试：每次优化必须通过基准测试集验证
"""

from .realtime_learner import learn_from_manual_annotation
from .batch_optimizer import run_batch_optimization
from .cross_group_tester import run_cross_group_test

__all__ = [
    "learn_from_manual_annotation",
    "run_batch_optimization",
    "run_cross_group_test",
]
