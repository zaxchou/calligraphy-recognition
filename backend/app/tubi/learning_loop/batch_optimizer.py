"""
批量优化器

定期全量跑评估，调优CV参数和LLM规律。

策略：
1. 加载所有有标注的数据
2. 运行当前CV-First流程
3. 计算IoU等指标
4. 分析哪个画群效果最差
5. 自动调整该画群的CV参数
"""

import json
import os
from typing import Dict, List, Tuple
import numpy as np

from app.core.database import SessionLocal
from app.models.tiba_analysis import TibaAnalysis


def calculate_iou(mask1: np.ndarray, mask2: np.ndarray) -> float:
    """计算两个mask的IoU"""
    intersection = np.logical_and(mask1 > 0, mask2 > 0).sum()
    union = np.logical_or(mask1 > 0, mask2 > 0).sum()
    return float(intersection) / float(union) if union > 0 else 0.0


def run_batch_optimization() -> Dict:
    """
    运行批量优化
    
    返回优化报告
    """
    db = SessionLocal()
    try:
        # 加载所有有标注的记录
        records = db.query(TibaAnalysis).filter(
            TibaAnalysis.regions != None,
            TibaAnalysis.regions != ''
        ).all()
        
        if len(records) < 10:
            return {
                "success": False,
                "error": "Not enough annotated records for optimization",
                "record_count": len(records),
            }
        
        # 按画群分组统计（需要先有画群分类结果）
        # 这里简化处理，实际运行时应该有画群标签
        
        report = {
            "success": True,
            "record_count": len(records),
            "message": f"Loaded {len(records)} annotated records for batch optimization",
            "groups_analyzed": [],
            "recommendations": [],
        }
        
        return report
    finally:
        db.close()
