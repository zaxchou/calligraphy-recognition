"""
V3 Self-Critique Prompt 扩展测试（15张随机图）
验证 V3 prompt 在更大样本上的稳定性和泛化能力
"""
import os
import sys
import random
import json
import time

# 确保能导入项目模块
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _BASE)

from dotenv import load_dotenv
load_dotenv(os.path.join(_BASE, ".env"))

from app.tubi.evaluation.vl_segmentation_probe import (
    run_probe, probe_single_image, load_ground_truth,
    regions_to_mask, polygons_to_mask, compute_iou,
    visualize_comparison
)
import numpy as np


def run_v3_scale_test(sample_size: int = 15, seed: int = 42):
    """随机选 sample_size 张图，用 V3 prompt 测试"""
    random.seed(seed)

    print("=" * 70)
    print(f"V3 SCALE TEST: {sample_size} random images")
    print(f"Seed: {seed}")
    print("=" * 70)

    records = load_ground_truth(artist="李鱓")
    print(f"Loaded {len(records)} GT records")

    # 排除前3张（已在之前测试中用过）
    excluded = {records[i].image_id for i in range(min(3, len(records)))}
    candidates = [r for r in records if r.image_id not in excluded]

    # 随机选15张
    test_records = random.sample(candidates, min(sample_size, len(candidates)))
    test_ids = [r.title or r.image_id for r in test_records]

    print(f"\nSelected {len(test_records)} images:")
    for i, r in enumerate(test_records, 1):
        print(f"  {i}. {r.title or r.image_id} ({r.width}x{r.height})")

    # 运行测试
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(
        _BASE, "data", "evaluation_reports", "vl_probe", f"v3_scale_{ts}"
    )
    os.makedirs(out_dir, exist_ok=True)

    results = []
    for i, record in enumerate(test_records, 1):
        print(f"\n{'#'*60}")
        print(f"# [{i}/{len(test_records)}] {record.title or record.image_id}")
        print(f"{'#'*60}")

        result = probe_single_image(record, use_hybrid=False, prompt_version="v3_self_critique")
        results.append(result)

        if not result.get("success"):
            print(f"WARNING: Failed for {record.title}")
            continue

        # 可视化
        pred_insc = regions_to_mask(result["vl_result"]["inscription_regions"], record.width, record.height)
        pred_paint = regions_to_mask(result["vl_result"]["painting_regions"], record.width, record.height)
        vis_path = os.path.join(out_dir, f"vis_{record.image_id}.jpg")
        visualize_comparison(record.filepath, record, pred_insc, pred_paint, result["bbox_iou"], vis_path)

    # 生成报告
    successful = [r for r in results if r.get("success")]
    report = {
        "model": "qwen3-vl-plus",
        "prompt_version": "v3_self_critique",
        "timestamp": ts,
        "seed": seed,
        "sample_size": sample_size,
        "test_count": len(results),
        "successful_count": len(successful),
        "results": results,
        "summary": {
            "avg_insc_iou": sum(r["bbox_iou"]["inscription_iou"] for r in successful) / max(1, len(successful)),
            "avg_paint_iou": sum(r["bbox_iou"]["painting_iou"] for r in successful) / max(1, len(successful)),
            "avg_overall_iou": sum(r["bbox_iou"]["overall_iou"] for r in successful) / max(1, len(successful)),
        },
        "image_list": [r.title or r.image_id for r in test_records],
    }

    # 统计分布
    if successful:
        overall_ious = [r["bbox_iou"]["overall_iou"] for r in successful]
        report["distribution"] = {
            "overall_min": min(overall_ious),
            "overall_max": max(overall_ious),
            "overall_std": (sum((x - report["summary"]["avg_overall_iou"])**2 for x in overall_ious) / len(overall_ious)) ** 0.5,
            "above_80": sum(1 for x in overall_ious if x >= 0.80),
            "above_85": sum(1 for x in overall_ious if x >= 0.85),
            "below_70": sum(1 for x in overall_ious if x < 0.70),
        }

    report_path = os.path.join(out_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 控制台输出
    print(f"\n{'='*60}")
    print(f"V3 SCALE TEST COMPLETE")
    print(f"Report: {report_path}")
    print(f"Summary:")
    print(f"  Successful: {report['successful_count']}/{report['test_count']}")
    print(f"  Avg Insc IoU:  {report['summary']['avg_insc_iou']:.3f}")
    print(f"  Avg Paint IoU: {report['summary']['avg_paint_iou']:.3f}")
    print(f"  Avg Overall:   {report['summary']['avg_overall_iou']:.3f}")
    if "distribution" in report:
        d = report["distribution"]
        print(f"  Range: [{d['overall_min']:.3f}, {d['overall_max']:.3f}]  Std: {d['overall_std']:.3f}")
        print(f"  ≥0.80: {d['above_80']}/{len(successful)}  |  ≥0.85: {d['above_85']}/{len(successful)}  |  <0.70: {d['below_70']}/{len(successful)}")
    print(f"{'='*60}\n")

    return report


if __name__ == "__main__":
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    run_v3_scale_test(sample_size=sample_size)
