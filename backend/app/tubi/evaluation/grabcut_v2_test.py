"""
GrabCut v2 快速验证：3图对比 BBox / GC v1 / GC v2(合并+保守初始化)
"""

import os
import sys
import json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.tubi.evaluation.gt_loader import load_ground_truth
from app.tubi.evaluation.iou_evaluator import compute_iou, polygons_to_mask
from app.tubi.evaluation.grabcut_refiner import refine_regions, merge_nearby_regions
from app.tubi.evaluation.vl_segmentation_probe import probe_single_image

TEST_IMAGES = ["荷花图", "土墙蝶花图", "煮茶图"]


def regions_to_mask(regions, width, height):
    """将 regions 列表转为 mask，同时支持 bbox 和 polygon 格式（归一化坐标）"""
    mask = np.zeros((height, width), dtype=np.uint8)
    for r in regions:
        if "points" in r and r["points"] and len(r["points"]) >= 3:
            pts = np.array([[int(p["x"] * width), int(p["y"] * height)] for p in r["points"]], dtype=np.int32)
            cv2.fillPoly(mask, [pts], 255)
        elif "x1" in r:
            x1 = max(0, int(r["x1"] * width))
            y1 = max(0, int(r["y1"] * height))
            x2 = min(width, int(r["x2"] * width))
            y2 = min(height, int(r["y2"] * height))
            if x2 > x1 and y2 > y1:
                mask[y1:y2, x1:x2] = 255
    return mask


def run_v2_test():
    records = load_ground_truth(artist="李鱓")
    test_records = [r for r in records if r.title in TEST_IMAGES]

    print("=" * 80)
    print("GRABCUT v2 快速验证：BBox / GC v1 / GC v2(合并+面积约束)")
    print("=" * 80)

    results = []

    for rec in test_records:
        print(f"\n{'─' * 70}")
        print(f"作品: {rec.title} ({rec.width}x{rec.height})")
        print(f"{'─' * 70}")

        if not os.path.exists(rec.filepath):
            print(f"  文件不存在: {rec.filepath}")
            continue

        # 1. 调用 VL 获取 BBox
        vl_result = probe_single_image(rec, use_polygon=False, prompt_version="v3_self_critique")
        if not vl_result or not vl_result.get("success"):
            print("  VL 调用失败")
            continue

        vl_data = vl_result.get("vl_result", {})
        vl_insc = vl_data.get("inscription_regions", [])
        vl_paint = vl_data.get("painting_regions", [])

        h, w = rec.height, rec.width

        # 2. BBox baseline mask
        bbox_insc_mask = regions_to_mask(vl_insc, w, h)
        bbox_paint_mask = regions_to_mask(vl_paint, w, h)
        bbox_combined = np.maximum(bbox_insc_mask, bbox_paint_mask)

        # 3. GT mask
        gt_insc = polygons_to_mask(rec.regions.get("inscription_regions", []), w, h)
        gt_paint = polygons_to_mask(rec.regions.get("painting_regions", []), w, h)
        gt_combined = np.maximum(gt_insc, gt_paint)

        # 4. GrabCut v1（无合并，旧初始化）
        img = cv2.imread(rec.filepath)
        v1_insc, v1_paint = refine_regions(img, vl_insc, vl_paint, merge_nearby=False)
        v1_insc_mask = regions_to_mask(v1_insc, w, h)
        v1_paint_mask = regions_to_mask(v1_paint, w, h)
        overlap1 = (v1_insc_mask > 0) & (v1_paint_mask > 0)
        v1_paint_mask[overlap1] = 0
        v1_combined = np.maximum(v1_insc_mask, v1_paint_mask)

        # 5. GrabCut v2（合并 + 保守初始化——GC_BGD替代GC_PR_BGD）
        v2_insc, v2_paint = refine_regions(img, vl_insc, vl_paint, merge_nearby=True)
        v2_insc_mask = regions_to_mask(v2_insc, w, h)
        v2_paint_mask = regions_to_mask(v2_paint, w, h)
        overlap2 = (v2_insc_mask > 0) & (v2_paint_mask > 0)
        v2_paint_mask[overlap2] = 0
        v2_combined = np.maximum(v2_insc_mask, v2_paint_mask)

        # 6. 计算 IoU
        bbox_i = compute_iou(bbox_insc_mask, gt_insc)
        bbox_p = compute_iou(bbox_paint_mask, gt_paint)
        bbox_o = compute_iou(bbox_combined, gt_combined)

        v1_i = compute_iou(v1_insc_mask, gt_insc)
        v1_p = compute_iou(v1_paint_mask, gt_paint)
        v1_o = compute_iou(v1_combined, gt_combined)

        v2_i = compute_iou(v2_insc_mask, gt_insc)
        v2_p = compute_iou(v2_paint_mask, gt_paint)
        v2_o = compute_iou(v2_combined, gt_combined)

        print(f"\n  结果对比:")
        print(f"  {'方法':<15} {'题跋I':>8} {'绘画P':>8} {'Overall':>8}")
        print(f"  {'-'*40}")
        print(f"  {'BBox baseline':<15} {bbox_i:>8.3f} {bbox_p:>8.3f} {bbox_o:>8.3f}")
        print(f"  {'GC v1':<15} {v1_i:>8.3f} {v1_p:>8.3f} {v1_o:>8.3f}  (Δ={v1_o-bbox_o:+.3f})")
        print(f"  {'GC v2':<15} {v2_i:>8.3f} {v2_p:>8.3f} {v2_o:>8.3f}  (Δ={v2_o-bbox_o:+.3f})")

        results.append({
            "title": rec.title,
            "bbox": {"i": bbox_i, "p": bbox_p, "o": bbox_o},
            "v1": {"i": v1_i, "p": v1_p, "o": v1_o},
            "v2": {"i": v2_i, "p": v2_p, "o": v2_o},
        })

    # 汇总
    print(f"\n{'=' * 80}")
    print("汇总对比")
    print(f"{'=' * 80}")
    print(f"  {'方法':<15} {'平均I':>8} {'平均P':>8} {'平均O':>8}")
    print(f"  {'-'*40}")
    
    for method, key in [("BBox baseline", "bbox"), ("GC v1", "v1"), ("GC v2", "v2")]:
        avg_i = sum(r[key]["i"] for r in results) / len(results)
        avg_p = sum(r[key]["p"] for r in results) / len(results)
        avg_o = sum(r[key]["o"] for r in results) / len(results)
        print(f"  {method:<15} {avg_i:>8.3f} {avg_p:>8.3f} {avg_o:>8.3f}")

    # 保存报告
    report_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "data", "evaluation_reports", "vl_probe",
        f"grabcut_v2_test_{__import__('time').strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n报告保存: {report_dir}")


if __name__ == "__main__":
    run_v2_test()
