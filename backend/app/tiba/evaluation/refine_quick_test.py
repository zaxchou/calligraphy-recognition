"""
方案A快速验证：3张图跑 GrabCut 精修（Polygon prompt）

用法:
    cd backend
    python -m app.tubi.evaluation.refine_quick_test

测试图：荷花图、土墙蝶花图、煮茶图（之前A/B测试过的3张）
对比：BBox baseline vs Polygon baseline vs Polygon+GrabCut refined
"""

import json
import os
import sys

# 把项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.tiba.evaluation.vl_segmentation_probe import (
    run_probe,
    probe_single_image,
    load_ground_truth,
    regions_to_mask,
    visualize_hybrid_comparison,
    compute_iou,
    polygons_to_mask,
)
from app.tiba.evaluation import grabcut_refiner
import numpy as np


TEST_IMAGES = ["荷花图", "土墙蝶花图", "煮茶图"]

def run_quick_test():
    """快速验证：3张图，对比 BBox / Polygon / Polygon+GrabCut"""
    print("=" * 70)
    print("方案A快速验证：3张图 x 3种模式")
    print("=" * 70)

    records = load_ground_truth(artist="李鱓")
    test_records = []
    for title in TEST_IMAGES:
        for r in records:
            if r.title == title:
                test_records.append(r)
                break

    print(f"测试图片: {[r.title for r in test_records]}")

    results = []

    for record in test_records:
        print(f"\n{'#'*70}")
        print(f"# IMAGE: {record.title}")
        print(f"{'#'*70}")

        entry = {"image_id": record.image_id, "title": record.title}

        # 1. BBox baseline (v3_self_critique)
        print("\n>>> MODE 1: BBox (v3_self_critique)")
        bbox_result = probe_single_image(record, use_polygon=False, prompt_version="v3_self_critique")
        if bbox_result.get("success"):
            entry["bbox"] = bbox_result["bbox_iou"]
            print(f"  BBox IoU: I={entry['bbox']['inscription_iou']:.3f} P={entry['bbox']['painting_iou']:.3f} O={entry['bbox']['overall_iou']:.3f}")

        # 2. Polygon baseline (v3_polygon)
        print("\n>>> MODE 2: Polygon (v3_polygon)")
        poly_result = probe_single_image(record, use_polygon=True, prompt_version="v3_polygon")
        if poly_result.get("success"):
            entry["polygon"] = poly_result["bbox_iou"]  # 虽然叫bbox_iou，但实际是多边形mask计算的
            print(f"  Polygon IoU: I={entry['polygon']['inscription_iou']:.3f} P={entry['polygon']['painting_iou']:.3f} O={entry['polygon']['overall_iou']:.3f}")

        # 3. Polygon + GrabCut Refinement
        print("\n>>> MODE 3: Polygon + GrabCut Refinement")
        if poly_result.get("success"):
            try:
                refined = grabcut_refiner.run_grabcut_refinement(
                    record.filepath,
                    poly_result["vl_result"]["inscription_regions"],
                    poly_result["vl_result"]["painting_regions"],
                )

                gt_insc = polygons_to_mask(record.regions.get("inscription_regions", []), record.width, record.height)
                gt_paint = polygons_to_mask(record.regions.get("painting_regions", []), record.width, record.height)

                insc_iou = compute_iou(refined["inscription_mask"], gt_insc)
                paint_iou = compute_iou(refined["painting_mask"], gt_paint)
                gt_total = np.logical_or(gt_insc > 0, gt_paint > 0)
                pred_total = np.logical_or(refined["inscription_mask"] > 0, refined["painting_mask"] > 0)
                overall_iou = compute_iou(pred_total.astype(np.uint8) * 255, gt_total.astype(np.uint8) * 255)

                entry["refined"] = {
                    "inscription_iou": insc_iou,
                    "painting_iou": paint_iou,
                    "overall_iou": overall_iou,
                }
                print(f"  Refined IoU: I={insc_iou:.3f} P={paint_iou:.3f} O={overall_iou:.3f}")

                # 计算改善
                if "polygon" in entry:
                    delta_o = overall_iou - entry["polygon"]["overall_iou"]
                    delta_i = insc_iou - entry["polygon"]["inscription_iou"]
                    delta_p = paint_iou - entry["polygon"]["painting_iou"]
                    print(f"  Improvement vs Polygon: I={delta_i:+.3f} P={delta_p:+.3f} O={delta_o:+.3f}")

            except Exception as e:
                print(f"  ERROR: GrabCut refinement failed: {e}")
                import traceback
                traceback.print_exc()

        results.append(entry)

    # 汇总
    print(f"\n{'='*70}")
    print("汇总对比")
    print(f"{'='*70}")
    print(f"{'作品':<12} {'BBox O':>8} {'Poly O':>8} {'Refine O':>8} {'d(Ref-Poly)':>12}")
    print("-" * 60)

    bbox_os = []
    poly_os = []
    refine_os = []

    for r in results:
        bbox_o = r.get("bbox", {}).get("overall_iou", 0)
        poly_o = r.get("polygon", {}).get("overall_iou", 0)
        refine_o = r.get("refined", {}).get("overall_iou", 0)
        delta = refine_o - poly_o if r.get("refined") else 0

        print(f"{r['title']:<12} {bbox_o:>8.3f} {poly_o:>8.3f} {refine_o:>8.3f} {delta:>+12.3f}")

        if r.get("bbox"): bbox_os.append(bbox_o)
        if r.get("polygon"): poly_os.append(poly_o)
        if r.get("refined"): refine_os.append(refine_o)

    print("-" * 60)
    if bbox_os:
        print(f"{'平均':<12} {sum(bbox_os)/len(bbox_os):>8.3f} {sum(poly_os)/len(poly_os):>8.3f} {sum(refine_os)/len(refine_os):>8.3f} {sum(refine_os)/len(refine_os)-sum(poly_os)/len(poly_os):>+12.3f}")

    # 保存报告
    import time
    from app.tiba.evaluation.vl_segmentation_probe import REPORT_DIR
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(REPORT_DIR, f"refine_quick_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    report_path = os.path.join(out_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_images": TEST_IMAGES,
            "results": results,
            "summary": {
                "avg_bbox_overall": sum(bbox_os)/len(bbox_os) if bbox_os else 0,
                "avg_polygon_overall": sum(poly_os)/len(poly_os) if poly_os else 0,
                "avg_refined_overall": sum(refine_os)/len(refine_os) if refine_os else 0,
            }
        }, f, ensure_ascii=False, indent=2)

    print(f"\n报告保存: {report_path}")
    return results


if __name__ == "__main__":
    run_quick_test()
