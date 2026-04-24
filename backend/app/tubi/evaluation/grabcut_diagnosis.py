"""
GrabCut 根因分析 v2：直接从已有报告 + VL 调用，量化 GrabCut 修剪问题

关键修复：正确处理 bbox 格式（x1,y1,x2,y2）和 polygon 格式（points）
"""

import os
import sys
import json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.tubi.evaluation.gt_loader import load_ground_truth
from app.tubi.evaluation.iou_evaluator import compute_iou
from app.tubi.evaluation.grabcut_refiner import refine_regions
from app.tubi.evaluation.vl_segmentation_probe import probe_single_image

TEST_IMAGES = ["荷花图", "土墙蝶花图", "煮茶图"]


def regions_to_mask(regions, width, height, normalized=True):
    """将 regions 列表转为 mask，同时支持 bbox 和 polygon 格式
    
    Args:
        normalized: True=坐标是归一化的(0-1)，False=坐标是像素值
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    for r in regions:
        if "points" in r and r["points"] and len(r["points"]) >= 3:
            if normalized:
                pts = np.array([[int(p["x"] * width), int(p["y"] * height)] for p in r["points"]], dtype=np.int32)
            else:
                pts = np.array([[int(p["x"]), int(p["y"])] for p in r["points"]], dtype=np.int32)
            cv2.fillPoly(mask, [pts], 255)
        elif "x1" in r:
            if normalized:
                x1 = max(0, int(r["x1"] * width))
                y1 = max(0, int(r["y1"] * height))
                x2 = min(width, int(r["x2"] * width))
                y2 = min(height, int(r["y2"] * height))
            else:
                x1 = max(0, int(r["x1"]))
                y1 = max(0, int(r["y1"]))
                x2 = min(width, int(r["x2"]))
                y2 = min(height, int(r["y2"]))
            if x2 > x1 and y2 > y1:
                mask[y1:y2, x1:x2] = 255
    return mask


def analyze_grabcut_diagnosis():
    records = load_ground_truth(artist="李鱓")
    test_records = [r for r in records if r.title in TEST_IMAGES]

    print("=" * 80)
    print("GRABCUT 根因分析 v2：量化留白修剪问题")
    print("=" * 80)

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

        # 2. 构建 BBox mask（同时支持 bbox 和 polygon 格式）
        bbox_insc_mask = regions_to_mask(vl_insc, w, h)
        bbox_paint_mask = regions_to_mask(vl_paint, w, h)
        bbox_combined = np.maximum(bbox_insc_mask, bbox_paint_mask)

        # 3. GT mask（坐标是像素值！用 iou_evaluator 的 polygons_to_mask）
        from app.tubi.evaluation.iou_evaluator import polygons_to_mask as gt_polygons_to_mask
        gt_insc = gt_polygons_to_mask(rec.regions.get("inscription_regions", []), w, h)
        gt_paint = gt_polygons_to_mask(rec.regions.get("painting_regions", []), w, h)
        gt_blank = gt_polygons_to_mask(rec.regions.get("blank_regions", []), w, h)
        gt_combined = np.maximum(gt_insc, gt_paint)

        # 4. 运行 GrabCut
        img = cv2.imread(rec.filepath)
        refined_insc, refined_paint = refine_regions(img, vl_insc, vl_paint)

        # 5. 构建 GrabCut mask
        gc_insc_mask = regions_to_mask(refined_insc, w, h)
        gc_paint_mask = regions_to_mask(refined_paint, w, h)
        overlap = (gc_insc_mask > 0) & (gc_paint_mask > 0)
        gc_paint_mask[overlap] = 0
        gc_combined = np.maximum(gc_insc_mask, gc_paint_mask)

        # 6. 计算各项指标
        bbox_iou = compute_iou(bbox_combined, gt_combined)
        gc_iou = compute_iou(gc_combined, gt_combined)

        # 面积
        bbox_area = int(np.sum(bbox_combined > 0))
        gc_area = int(np.sum(gc_combined > 0))
        gt_area = int(np.sum(gt_combined > 0))

        # 面积缩减率
        gc_shrink_ratio = gc_area / bbox_area if bbox_area > 0 else 0
        gt_coverage_ratio = gt_area / bbox_area if bbox_area > 0 else 0

        # GrabCut 修剪掉的区域中，有多少属于 GT（即"误修剪"）
        trimmed = (bbox_combined > 0) & (gc_combined == 0)
        trimmed_in_gt = trimmed & (gt_combined > 0)
        trimmed_out_gt = trimmed & (gt_combined == 0)
        trimmed_correct = int(np.sum(trimmed_out_gt))  # 正确修剪（真背景）
        trimmed_wrong = int(np.sum(trimmed_in_gt))     # 错误修剪（GT前景被删）
        trimmed_total = int(np.sum(trimmed))

        # GrabCut 新增的区域中，有多少属于 GT
        added = (gc_combined > 0) & (bbox_combined == 0)
        added_in_gt = added & (gt_combined > 0)
        added_out_gt = added & (gt_combined == 0)
        added_correct = int(np.sum(added_in_gt))
        added_wrong = int(np.sum(added_out_gt))

        # TP/FP/FN 分析
        bbox_tp = int(np.sum((bbox_combined > 0) & (gt_combined > 0)))
        bbox_fp = int(np.sum((bbox_combined > 0) & (gt_combined == 0)))
        bbox_fn = int(np.sum((bbox_combined == 0) & (gt_combined > 0)))

        gc_tp = int(np.sum((gc_combined > 0) & (gt_combined > 0)))
        gc_fp = int(np.sum((gc_combined > 0) & (gt_combined == 0)))
        gc_fn = int(np.sum((gc_combined == 0) & (gt_combined > 0)))

        print(f"\n  IoU 对比:")
        print(f"    BBox Overall:    {bbox_iou:.3f}")
        print(f"    GrabCut Overall: {gc_iou:.3f}")
        print(f"    变化: {gc_iou - bbox_iou:+.3f}")

        print(f"\n  面积分析:")
        print(f"    BBox面积: {bbox_area:>12,} px")
        print(f"    GT面积:   {gt_area:>12,} px  (GT/BBox = {gt_coverage_ratio:.1%})")
        print(f"    GC面积:   {gc_area:>12,} px  (GC/BBox = {gc_shrink_ratio:.1%})")

        if trimmed_total > 0:
            print(f"\n  GrabCut 修剪分析:")
            print(f"    修剪总量:       {trimmed_total:>12,} px")
            print(f"    正确修剪(真背景): {trimmed_correct:>12,} px ({trimmed_correct/trimmed_total:.1%})")
            print(f"    错误修剪(GT前景): {trimmed_wrong:>12,} px ({trimmed_wrong/trimmed_total:.1%})")
        else:
            print(f"\n  GrabCut 无修剪（GC面积 >= BBox面积）")

        added_total = int(np.sum(added))
        if added_total > 0:
            print(f"\n  GrabCut 新增分析:")
            print(f"    新增总量:       {added_total:>12,} px")
            print(f"    正确新增(GT前景): {added_correct:>12,} px ({added_correct/added_total:.1%})")
            print(f"    错误新增(假前景): {added_wrong:>12,} px ({added_wrong/added_total:.1%})")

        print(f"\n  TP/FP/FN 对比:")
        print(f"    {'':>10} {'TP':>12} {'FP':>12} {'FN':>12}")
        print(f"    {'BBox':>10} {bbox_tp:>12,} {bbox_fp:>12,} {bbox_fn:>12,}")
        print(f"    {'GrabCut':>10} {gc_tp:>12,} {gc_fp:>12,} {gc_fn:>12,}")
        print(f"    {'变化':>10} {gc_tp-bbox_tp:>+12,} {gc_fp-bbox_fp:>+12,} {gc_fn-bbox_fn:>+12,}")

        # 分区域分析
        print(f"\n  分区域 IoU:")
        for name, vl_mask, gc_mask, gt_mask in [
            ("题跋", bbox_insc_mask, gc_insc_mask, gt_insc),
            ("绘画", bbox_paint_mask, gc_paint_mask, gt_paint),
        ]:
            b_iou = compute_iou(vl_mask, gt_mask)
            g_iou = compute_iou(gc_mask, gt_mask)
            b_area = int(np.sum(vl_mask > 0))
            g_area = int(np.sum(gc_mask > 0))
            gt_a = int(np.sum(gt_mask > 0))
            if b_area > 0:
                print(f"    {name}: BBox={b_iou:.3f} GC={g_iou:.3f} Δ={g_iou-b_iou:+.3f} | "
                      f"面积: BBox={b_area:,} GC={g_area:,} GT={gt_a:,} GC/BBox={g_area/b_area:.1%}")
            else:
                print(f"    {name}: BBox面积=0, 跳过")


if __name__ == "__main__":
    analyze_grabcut_diagnosis()
