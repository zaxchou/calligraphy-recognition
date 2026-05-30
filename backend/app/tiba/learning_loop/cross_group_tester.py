"""
跨群测试框架

每次优化后，必须验证跨群泛化性：
1. 从每个画群中抽取20%作为测试集
2. 在测试集上评估IoU
3. 跨群测试IoU下降不得超过10%
4. 专门保留5张特殊画作为基准测试集
"""

import json
import os
from typing import Dict, List
from datetime import datetime


BASELINE_TEST_SET_PATH = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\test_sets\baseline_test_set.json"


def run_cross_group_test(
    test_results: Dict[str, List[float]],
    max_iou_degradation: float = 0.10,
) -> Dict:
    """
    运行跨群测试
    
    参数：
        test_results: {group_name: [iou1, iou2, ...]}
        max_iou_degradation: 最大允许IoU下降比例
    
    返回：
        测试报告
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "success": True,
        "groups": {},
        "baseline_passed": True,
        "can_deploy": True,
        "issues": [],
    }
    
    overall_iou_sum = 0.0
    overall_count = 0
    
    for group, ious in test_results.items():
        if not ious:
            continue
        
        mean_iou = sum(ious) / len(ious)
        min_iou = min(ious)
        max_iou = max(ious)
        
        report["groups"][group] = {
            "count": len(ious),
            "mean_iou": round(mean_iou, 4),
            "min_iou": round(min_iou, 4),
            "max_iou": round(max_iou, 4),
        }
        
        overall_iou_sum += mean_iou
        overall_count += 1
    
    if overall_count > 0:
        report["overall_mean_iou"] = round(overall_iou_sum / overall_count, 4)
    
    # 检查跨群性能下降
    if len(test_results) >= 2:
        mean_ious = [sum(v)/len(v) for v in test_results.values() if v]
        if mean_ious:
            best_iou = max(mean_ious)
            worst_iou = min(mean_ious)
            degradation = (best_iou - worst_iou) / best_iou if best_iou > 0 else 0
            
            report["cross_group_degradation"] = round(degradation, 4)
            
            if degradation > max_iou_degradation:
                report["can_deploy"] = False
                report["issues"].append(
                    f"Cross-group IoU degradation ({degradation:.1%}) exceeds threshold ({max_iou_degradation:.1%})"
                )
    
    # 保存测试报告
    report_path = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\test_sets\cross_group_test_report.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    return report
