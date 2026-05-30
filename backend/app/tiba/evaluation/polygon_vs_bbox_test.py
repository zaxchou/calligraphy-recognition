"""
Polygon vs BBox 对比测试
验证 VL 输出多边形是否能比矩形框获得更高的 IoU
"""
import os
import sys
import json
import time

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _BASE)

from dotenv import load_dotenv
load_dotenv(os.path.join(_BASE, ".env"))

import numpy as np

from app.tiba.evaluation.vl_segmentation_probe import (
    probe_single_image, load_ground_truth,
    regions_to_mask, polygons_to_mask, compute_iou,
    visualize_comparison,
)


def run_polygon_vs_bbox_test(images_to_test=None):
    """
    对同一张图分别测试 polygon 模式和 bbox 模式，对比 IoU
    """
    print("=" * 70)
    print("POLYGON vs BBOX A/B TEST")
    print("=" * 70)

    records = load_ground_truth(artist="李鱓")
    print(f"Loaded {len(records)} GT records")

    if images_to_test:
        test_records = []
        for identifier in images_to_test:
            for r in records:
                if identifier in (r.title, r.image_id, str(r.id)):
                    test_records.append(r)
                    break
    else:
        # 默认前3张
        test_records = records[:3]

    print(f"\nTesting {len(test_records)} images:")
    for r in test_records:
        print(f"  - {r.title or r.image_id} ({r.width}x{r.height})")

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(_BASE, "data", "evaluation_reports", "vl_probe", f"polygon_test_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    all_results = []

    for record in test_records:
        print(f"\n{'#'*70}")
        print(f"# IMAGE: {record.title or record.image_id}")
        print(f"{'#'*70}")

        # ── BBox 模式（V3 self-critique）──
        print(f"\n>>> MODE: BBOX (v3_self_critique)")
        bbox_result = probe_single_image(record, use_polygon=False, prompt_version="v3_self_critique")

        # ── Polygon 模式（V3 polygon）──
        print(f"\n>>> MODE: POLYGON (v3_polygon)")
        poly_result = probe_single_image(record, use_polygon=True, prompt_version="v3_polygon")

        # 保存对比结果
        entry = {
            "image_id": record.image_id,
            "title": record.title,
        }

        if bbox_result.get("success"):
            entry["bbox"] = bbox_result["bbox_iou"]
            # 检查bbox结果中是否有polygon格式的regions
            insc_regions = bbox_result["vl_result"].get("inscription_regions", [])
            has_poly_bbox = any("points" in r for r in insc_regions)
            print(f"  [BBox mode] VL returned polygon format: {has_poly_bbox}")

        if poly_result.get("success"):
            entry["polygon"] = poly_result["bbox_iou"]
            # 检查polygon结果中实际返回了什么格式
            insc_regions = poly_result["vl_result"].get("inscription_regions", [])
            has_points = any("points" in r for r in insc_regions)
            has_bbox = any("x1" in r for r in insc_regions)
            print(f"  [Polygon mode] VL returned points: {has_points}, bbox: {has_bbox}")

        if "bbox" in entry and "polygon" in entry:
            entry["delta"] = {
                "insc_delta": entry["polygon"]["inscription_iou"] - entry["bbox"]["inscription_iou"],
                "paint_delta": entry["polygon"]["painting_iou"] - entry["bbox"]["painting_iou"],
                "overall_delta": entry["polygon"]["overall_iou"] - entry["bbox"]["overall_iou"],
            }
            print(f"\n>>> COMPARISON:")
            print(f"  BBox:    I={entry['bbox']['inscription_iou']:.3f} P={entry['bbox']['painting_iou']:.3f} O={entry['bbox']['overall_iou']:.3f}")
            print(f"  Polygon: I={entry['polygon']['inscription_iou']:.3f} P={entry['polygon']['painting_iou']:.3f} O={entry['polygon']['overall_iou']:.3f}")
            print(f"  Delta:   I={entry['delta']['insc_delta']:+.3f} P={entry['delta']['paint_delta']:+.3f} O={entry['delta']['overall_delta']:+.3f}")

        all_results.append(entry)

        # 可视化：Polygon vs BBox 对比图
        if bbox_result.get("success") and poly_result.get("success"):
            # BBox masks
            bbox_insc = regions_to_mask(bbox_result["vl_result"]["inscription_regions"], record.width, record.height)
            bbox_paint = regions_to_mask(bbox_result["vl_result"]["painting_regions"], record.width, record.height)
            # Polygon masks
            poly_insc = regions_to_mask(poly_result["vl_result"]["inscription_regions"], record.width, record.height)
            poly_paint = regions_to_mask(poly_result["vl_result"]["painting_regions"], record.width, record.height)

            from app.tiba.evaluation.vl_segmentation_probe import visualize_hybrid_comparison
            vis_path = os.path.join(out_dir, f"vis_{record.image_id}_compare.jpg")
            visualize_hybrid_comparison(
                record.filepath, record,
                bbox_insc, bbox_paint,
                poly_insc, poly_paint,
                bbox_result["bbox_iou"], poly_result["bbox_iou"],
                vis_path,
            )

    # 汇总报告
    report = {
        "timestamp": ts,
        "test_count": len(test_records),
        "results": all_results,
    }

    both_success = [r for r in all_results if "bbox" in r and "polygon" in r]
    if both_success:
        report["bbox_summary"] = {
            "avg_insc_iou": sum(r["bbox"]["inscription_iou"] for r in both_success) / len(both_success),
            "avg_paint_iou": sum(r["bbox"]["painting_iou"] for r in both_success) / len(both_success),
            "avg_overall_iou": sum(r["bbox"]["overall_iou"] for r in both_success) / len(both_success),
        }
        report["polygon_summary"] = {
            "avg_insc_iou": sum(r["polygon"]["inscription_iou"] for r in both_success) / len(both_success),
            "avg_paint_iou": sum(r["polygon"]["painting_iou"] for r in both_success) / len(both_success),
            "avg_overall_iou": sum(r["polygon"]["overall_iou"] for r in both_success) / len(both_success),
        }
        report["improvement"] = {
            "insc_delta": report["polygon_summary"]["avg_insc_iou"] - report["bbox_summary"]["avg_insc_iou"],
            "paint_delta": report["polygon_summary"]["avg_paint_iou"] - report["bbox_summary"]["avg_paint_iou"],
            "overall_delta": report["polygon_summary"]["avg_overall_iou"] - report["bbox_summary"]["avg_overall_iou"],
        }

    report_path = os.path.join(out_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"POLYGON vs BBOX REPORT: {report_path}")
    if "bbox_summary" in report:
        print(f"BBox Summary:    I={report['bbox_summary']['avg_insc_iou']:.3f} P={report['bbox_summary']['avg_paint_iou']:.3f} O={report['bbox_summary']['avg_overall_iou']:.3f}")
        print(f"Polygon Summary: I={report['polygon_summary']['avg_insc_iou']:.3f} P={report['polygon_summary']['avg_paint_iou']:.3f} O={report['polygon_summary']['avg_overall_iou']:.3f}")
        print(f"Improvement:     I={report['improvement']['insc_delta']:+.3f} P={report['improvement']['paint_delta']:+.3f} O={report['improvement']['overall_delta']:+.3f}")
    print(f"{'='*60}\n")

    return report


if __name__ == "__main__":
    run_polygon_vs_bbox_test()
