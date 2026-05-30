"""
纯 BBox 优化策略分析：
1. VL bbox vs GT 的面积比（系统性偏差）
2. 碎片化合并的效果
3. 适度膨胀/收缩的最优参数

对 15 张随机图做统计，找到最优的 bbox 调整策略
"""

import os
import sys
import json
import random
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.tiba.evaluation.gt_loader import load_ground_truth
from app.tiba.evaluation.iou_evaluator import compute_iou, polygons_to_mask
from app.tiba.evaluation.grabcut_refiner import merge_nearby_regions
from app.tiba.evaluation.vl_segmentation_probe import probe_single_image


def regions_to_mask(regions, width, height):
    """将 regions 列表转为 mask（归一化坐标）"""
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


def expand_bbox(bbox, ratio, w, h):
    """膨胀 bbox（归一化坐标），ratio 是每边膨胀的比例"""
    cx = (bbox["x1"] + bbox["x2"]) / 2
    cy = (bbox["y1"] + bbox["y2"]) / 2
    bw = bbox["x2"] - bbox["x1"]
    bh = bbox["y2"] - bbox["y1"]
    new_bw = bw * (1 + ratio)
    new_bh = bh * (1 + ratio)
    return {
        "x1": max(0, cx - new_bw / 2),
        "y1": max(0, cy - new_bh / 2),
        "x2": min(1, cx + new_bw / 2),
        "y2": min(1, cy + new_bh / 2),
    }


def run_bbox_optimization():
    records = load_ground_truth(artist="李鱓")
    random.seed(42)
    test_records = random.sample(records, min(15, len(records)))

    print("=" * 80)
    print("纯 BBox 优化策略分析（15图随机测试）")
    print("=" * 80)

    # 测试不同膨胀比例
    expand_ratios = [0.0, 0.02, 0.05, 0.08, 0.10, 0.15]
    # 测试合并 vs 不合并
    merge_options = [False, True]

    results = []

    for idx, rec in enumerate(test_records):
        print(f"\n[{idx+1}/15] {rec.title} ({rec.width}x{rec.height})")

        if not os.path.exists(rec.filepath):
            print(f"  文件不存在，跳过")
            continue

        # 1. 调用 VL
        vl_result = probe_single_image(rec, use_polygon=False, prompt_version="v3_self_critique")
        if not vl_result or not vl_result.get("success"):
            print("  VL 调用失败")
            continue

        vl_data = vl_result.get("vl_result", {})
        vl_insc = vl_data.get("inscription_regions", [])
        vl_paint = vl_data.get("painting_regions", [])

        h, w = rec.height, rec.width

        # GT mask
        gt_insc = polygons_to_mask(rec.regions.get("inscription_regions", []), w, h)
        gt_paint = polygons_to_mask(rec.regions.get("painting_regions", []), w, h)
        gt_combined = np.maximum(gt_insc, gt_paint)

        entry = {"title": rec.title, "width": w, "height": h}

        for merge in merge_options:
            for ratio in expand_ratios:
                # 合并（可选）
                if merge:
                    insc = merge_nearby_regions(vl_insc, w, h)
                    paint = merge_nearby_regions(vl_paint, w, h)
                else:
                    insc = vl_insc
                    paint = vl_paint

                # 膨胀（可选）
                if ratio > 0:
                    insc_exp = [expand_bbox(r, ratio, w, h) if "x1" in r else r for r in insc]
                    paint_exp = [expand_bbox(r, ratio, w, h) if "x1" in r else r for r in paint]
                else:
                    insc_exp = insc
                    paint_exp = paint

                # 构建 mask
                insc_mask = regions_to_mask(insc_exp, w, h)
                paint_mask = regions_to_mask(paint_exp, w, h)
                combined = np.maximum(insc_mask, paint_mask)

                # 计算 IoU
                i_iou = compute_iou(insc_mask, gt_insc)
                p_iou = compute_iou(paint_mask, gt_paint)
                o_iou = compute_iou(combined, gt_combined)

                key = f"merge={merge}_exp={ratio:.2f}"
                entry[key] = {"i": i_iou, "p": p_iou, "o": o_iou}

                if ratio == 0.0 and not merge:
                    print(f"  Baseline: I={i_iou:.3f} P={p_iou:.3f} O={o_iou:.3f}")

        results.append(entry)

    # 汇总
    print(f"\n{'=' * 80}")
    print("汇总：不同策略的平均 IoU")
    print(f"{'=' * 80}")

    print(f"\n  {'策略':<30} {'平均I':>8} {'平均P':>8} {'平均O':>8}")
    print(f"  {'-'*60}")

    for merge in merge_options:
        for ratio in expand_ratios:
            key = f"merge={merge}_exp={ratio:.2f}"
            avg_i = sum(r[key]["i"] for r in results if key in r) / max(1, len([r for r in results if key in r]))
            avg_p = sum(r[key]["p"] for r in results if key in r) / max(1, len([r for r in results if key in r]))
            avg_o = sum(r[key]["o"] for r in results if key in r) / max(1, len([r for r in results if key in r]))
            merge_str = "合并" if merge else "原始"
            print(f"  {merge_str+'+膨胀'+str(int(ratio*100))+'%':<30} {avg_i:>8.3f} {avg_p:>8.3f} {avg_o:>8.3f}")

    # 找最优
    best_key = None
    best_o = 0
    for merge in merge_options:
        for ratio in expand_ratios:
            key = f"merge={merge}_exp={ratio:.2f}"
            avg_o = sum(r[key]["o"] for r in results if key in r) / max(1, len([r for r in results if key in r]))
            if avg_o > best_o:
                best_o = avg_o
                best_key = key

    print(f"\n  最优策略: {best_key} (Overall={best_o:.3f})")

    # 保存报告
    report_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "data", "evaluation_reports", "vl_probe",
        f"bbox_optimization_{__import__('time').strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"results": results, "best_key": best_key, "best_o": best_o}, f, ensure_ascii=False, indent=2)
    print(f"\n报告保存: {report_dir}")


if __name__ == "__main__":
    run_bbox_optimization()
