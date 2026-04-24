"""
批量只读评估脚本

对Ground Truth数据集批量执行CV-First分析，计算IoU并输出报告。
全程只读，不修改数据库。
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import asdict

import cv2
import numpy as np

from .gt_loader import load_ground_truth, GroundTruthRecord
from .iou_evaluator import evaluate_image, IoUResult


def ensure_backend_path():
    """确保backend目录在sys.path中"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


def run_single_evaluation(
    record: GroundTruthRecord,
    verbose: bool = False,
) -> Optional[Dict]:
    """
    对单张图执行CV-First分析并评估IoU
    
    返回:
        Dict 包含 image_id, title, result(IoUResult), 和错误信息
        None 如果分析失败
    """
    image_path = record.filepath
    
    # 读取图像获取实际尺寸
    img = cv2.imread(image_path)
    if img is None:
        print(f"  ERROR: Cannot read image {image_path}")
        return None
    
    h, w = img.shape[:2]
    
    # 导入CV-First分析模块（延迟导入，避免循环依赖）
    ensure_backend_path()
    from app.tubi.integration import run_cv_first_analysis
    
    # 运行CV-First分析
    try:
        if verbose:
            print(f"  Running CV-First on {record.image_id} ({w}x{h})...")
        
        start_time = time.time()
        result = run_cv_first_analysis(image_path, w, h)
        elapsed = time.time() - start_time
        
        if not result.get("success", False):
            print(f"  ERROR: CV-First failed for {record.image_id}: {result.get('error', 'Unknown')}")
            return None
        
        pred_regions = result.get("regions", {})
        
        # 评估IoU
        iou_result = evaluate_image(
            pred_regions=pred_regions,
            gt_regions=record.regions,
            orig_w=w,
            orig_h=h,
        )
        
        return {
            "image_id": record.image_id,
            "title": record.title,
            "width": w,
            "height": h,
            "elapsed_seconds": round(elapsed, 2),
            "cv_group": result.get("group", "unknown"),
            "cv_confidence": result.get("confidence", 0.0),
            "inscription_iou": iou_result.inscription_iou,
            "painting_iou": iou_result.painting_iou,
            "blank_iou": iou_result.blank_iou,
            "overall_iou": iou_result.overall_iou,
            "gt_insc_area": iou_result.gt_insc_area,
            "gt_paint_area": iou_result.gt_paint_area,
            "gt_blank_area": iou_result.gt_blank_area,
            "pred_insc_area": iou_result.pred_insc_area,
            "pred_paint_area": iou_result.pred_paint_area,
            "pred_blank_area": iou_result.pred_blank_area,
            "error_types": iou_result.error_types,
            "pred_insc_count": len(pred_regions.get("inscription_regions", [])),
            "pred_paint_count": len(pred_regions.get("painting_regions", [])),
            "pred_blank_count": len(pred_regions.get("blank_regions", [])),
            "gt_insc_count": len(record.regions.get("inscription_regions", [])),
            "gt_paint_count": len(record.regions.get("painting_regions", [])),
            "gt_blank_count": len(record.regions.get("blank_regions", [])),
        }
        
    except Exception as e:
        print(f"  ERROR: Exception for {record.image_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_batch_evaluation(
    records: Optional[List[GroundTruthRecord]] = None,
    output_dir: Optional[str] = None,
    verbose: bool = True,
    limit: Optional[int] = None,
) -> str:
    """
    批量评估主入口
    
    参数:
        records: Ground Truth记录列表，None=自动从数据库加载
        output_dir: 报告输出目录，None=自动生成
        verbose: 是否打印进度
        limit: 限制评估数量（用于测试），None=全部
    
    返回:
        str: 报告文件路径
    """
    if records is None:
        records = load_ground_truth()
    
    if limit:
        records = records[:limit]
    
    total = len(records)
    print(f"[BatchEval] Starting evaluation of {total} images...")
    
    results = []
    failed = []
    
    for i, record in enumerate(records):
        if verbose:
            print(f"[{i+1}/{total}] {record.image_id} - {record.title}")
        
        result = run_single_evaluation(record, verbose=verbose)
        if result:
            results.append(result)
            if verbose:
                print(f"  -> IoU: insc={result['inscription_iou']:.3f}, paint={result['painting_iou']:.3f}, blank={result['blank_iou']:.3f}, overall={result['overall_iou']:.3f}")
                if result['error_types']:
                    print(f"  -> Errors: {result['error_types']}")
        else:
            failed.append(record.image_id)
    
    # 汇总统计
    stats = compute_summary_stats(results)
    
    # 生成报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_images": total,
        "successful": len(results),
        "failed": len(failed),
        "failed_ids": failed,
        "summary": stats,
        "results": results,
    }
    
    # 保存报告
    if output_dir is None:
        report_base = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..",
            "data", "evaluation_reports"
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(report_base, f"batch_eval_{timestamp}")
    
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "report.json")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n[BatchEval] Done!")
    print(f"  Successful: {len(results)}/{total}")
    print(f"  Failed: {len(failed)}")
    print(f"  Mean IoU: inscription={stats['mean_insc_iou']:.3f}, painting={stats['mean_paint_iou']:.3f}, blank={stats['mean_blank_iou']:.3f}")
    print(f"  Overall IoU: {stats['mean_overall_iou']:.3f}")
    print(f"  Report saved to: {report_path}")
    
    return report_path


def compute_summary_stats(results: List[Dict]) -> Dict:
    """计算汇总统计"""
    if not results:
        return {}
    
    def _mean(key: str) -> float:
        vals = [r[key] for r in results if r[key] is not None]
        return sum(vals) / len(vals) if vals else 0.0
    
    def _median(key: str) -> float:
        vals = sorted([r[key] for r in results if r[key] is not None])
        n = len(vals)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return vals[n // 2]
        return (vals[n // 2 - 1] + vals[n // 2]) / 2
    
    def _percentile(key: str, p: float) -> float:
        vals = sorted([r[key] for r in results if r[key] is not None])
        if not vals:
            return 0.0
        idx = int(len(vals) * p / 100.0)
        idx = max(0, min(idx, len(vals) - 1))
        return vals[idx]
    
    # 错误类型统计
    error_counts = {}
    for r in results:
        for et in r.get("error_types", []):
            error_counts[et] = error_counts.get(et, 0) + 1
    
    return {
        "mean_insc_iou": _mean("inscription_iou"),
        "median_insc_iou": _median("inscription_iou"),
        "p10_insc_iou": _percentile("inscription_iou", 10),
        "p90_insc_iou": _percentile("inscription_iou", 90),
        "mean_paint_iou": _mean("painting_iou"),
        "median_paint_iou": _median("painting_iou"),
        "p10_paint_iou": _percentile("painting_iou", 10),
        "p90_paint_iou": _percentile("painting_iou", 90),
        "mean_blank_iou": _mean("blank_iou"),
        "median_blank_iou": _median("blank_iou"),
        "mean_overall_iou": _mean("overall_iou"),
        "median_overall_iou": _median("overall_iou"),
        "p10_overall_iou": _percentile("overall_iou", 10),
        "p90_overall_iou": _percentile("overall_iou", 90),
        "error_type_counts": error_counts,
    }


if __name__ == "__main__":
    # 命令行入口
    import argparse
    parser = argparse.ArgumentParser(description="Batch evaluate CV-First on Ground Truth")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of images")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    parser.add_argument("--quiet", action="store_true", help="Quiet mode")
    args = parser.parse_args()
    
    run_batch_evaluation(
        limit=args.limit,
        output_dir=args.output,
        verbose=not args.quiet,
    )
