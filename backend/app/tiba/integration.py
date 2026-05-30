"""
CV-First新流程集成入口

完整处理流程：
预处理标准化 → CV多策略mask → LLM分群分类 → VL校验 → 生成regions

此模块作为tubi_worker的替代分析路径，保留所有其他后处理功能。
"""

import os
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple

from app.tiba.preprocessing import preprocess_standardize, classify_image_group
from app.tiba.cv_mask_extractor import ensemble_masks
from app.tiba.llm_classifier import classify_regions
from app.tiba.vl_verifier import verify_low_confidence_regions
from app.services.tiba_mask_refiner import mask_to_regions


def run_cv_first_analysis(image_path: str, image_width: int, image_height: int) -> Dict:
    """
    运行CV-First分析流程
    
    参数：
        image_path: 原始图像路径
        image_width: 图像宽度
        image_height: 图像高度
    
    返回：
        {
            "success": True/False,
            "regions": {
                "inscription_regions": [...],
                "painting_regions": [...],
                "blank_regions": [...],
            },
            "analysis_note": "...",
            "confidence": 0.85,
            "group": "dark_base",
            "used_vl": False,
        }
    """
    try:
        print(f"[CV-First] Starting analysis: {image_path}")
        
        # Phase 0: 预处理标准化
        print("[CV-First] Phase 0: Preprocessing...")
        std_img = preprocess_standardize(image_path)
        print(f"[CV-First] Preprocessing done. Group features: L={std_img.brightness_median:.1f}, S={std_img.saturation_median:.1f}")
        
        # 画群分类
        group = classify_image_group(std_img)
        print(f"[CV-First] Painting group: {group.primary_group.value}, confidence: {group.confidence}")
        
        # Phase 2: CV多策略mask提取
        print("[CV-First] Phase 2: CV mask extraction...")
        masks = ensemble_masks(std_img)
        
        h, w = std_img.image.shape[:2]
        insc_px = cv2.countNonZero(masks.inscription_candidates)
        paint_px = cv2.countNonZero(masks.painting_candidates)
        print(f"[CV-First] CV masks: inscription={insc_px}px, painting={paint_px}px")
        
        # Phase 3: LLM语义分类
        print("[CV-First] Phase 3: LLM classification...")
        classification = classify_regions(std_img, group, masks, use_llm=True)
        print(f"[CV-First] LLM classification: {len(classification.regions)} regions, overall_conf={classification.overall_confidence:.2f}")
        
        # Phase 4: VL校验（低置信度区域）
        print("[CV-First] Phase 4: VL verification...")
        if classification.low_confidence_count > 0:
            verified = verify_low_confidence_regions(
                image_path=image_path,
                classification=classification,
                inscription_candidates=masks.inscription_candidates,
                confidence_threshold=0.6,
                max_verify_count=3,
            )
            used_vl = any(v.used_vl for v in verified)
            print(f"[CV-First] VL verification done. Used VL: {used_vl}")
        else:
            verified = None
            used_vl = False
            print("[CV-First] No low-confidence regions, skipping VL")
        
        # 生成最终regions
        # 根据LLM分类结果从两类候选中筛选：
        # - inscription_regions = 所有被判为"inscription"的区域（无论来自哪类候选）
        # - painting_regions = 所有被判为"painting"的区域
        insc_mask_filtered = np.zeros_like(masks.inscription_candidates)
        paint_mask_filtered = np.zeros_like(masks.painting_candidates)
        
        if classification.regions and len(classification.regions) > 0 and masks.region_features:
            # 对两类候选分别做连通域分析
            num_labels_insc, labels_insc, stats_insc, centroids_insc = cv2.connectedComponentsWithStats(
                masks.inscription_candidates, connectivity=8
            )
            num_labels_paint, labels_paint, stats_paint, centroids_paint = cv2.connectedComponentsWithStats(
                masks.painting_candidates, connectivity=8
            )
            
            for region in classification.regions:
                region_id = region.region_id
                if region_id < len(masks.region_features):
                    feature = masks.region_features[region_id]
                    cc_label = feature.get("cc_label")
                    source = feature.get("source", "")
                    
                    if region.category == "inscription":
                        if source == "inscription_candidate" and cc_label is not None and 0 < cc_label < num_labels_insc:
                            insc_mask_filtered[labels_insc == cc_label] = 255
                        elif source == "painting_candidate" and cc_label is not None and 0 < cc_label < num_labels_paint:
                            paint_mask_filtered[labels_paint == cc_label] = 255
                    elif region.category == "painting":
                        if source == "inscription_candidate" and cc_label is not None and 0 < cc_label < num_labels_insc:
                            paint_mask_filtered[labels_insc == cc_label] = 255  # 被误判为题跋候选的绘画区域，移到绘画
                        elif source == "painting_candidate" and cc_label is not None and 0 < cc_label < num_labels_paint:
                            paint_mask_filtered[labels_paint == cc_label] = 255
            
            # 如果某类过滤后为空，回退到原mask
            if cv2.countNonZero(insc_mask_filtered) == 0:
                insc_mask_filtered = masks.inscription_candidates.copy()
            if cv2.countNonZero(paint_mask_filtered) == 0:
                paint_mask_filtered = masks.painting_candidates.copy()
        else:
            insc_mask_filtered = masks.inscription_candidates.copy()
            paint_mask_filtered = masks.painting_candidates.copy()
        
        scale = std_img.scale_ratio
        
        inscription_regions = _mask_to_polygon_regions(
            insc_mask_filtered, w, h, scale, max_regions=5
        )
        painting_regions = _mask_to_polygon_regions(
            paint_mask_filtered, w, h, scale, max_regions=5
        )
        
        # 计算留白区域：合并题跋和绘画mask后取反，再做闭运算减少碎片
        combined_mask = cv2.bitwise_or(masks.inscription_candidates, masks.painting_candidates)
        blank_mask = cv2.bitwise_not(combined_mask)
        # 形态学闭运算：合并相近的留白碎片
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        blank_mask = cv2.morphologyEx(blank_mask, cv2.MORPH_CLOSE, kernel)
        blank_regions = _mask_to_polygon_regions(blank_mask, w, h, scale, max_regions=3)
        
        # 构建分析说明
        analysis_note = _build_analysis_note(group, classification, std_img)
        
        # 映射回原始图像坐标
        orig_w, orig_h = std_img.original_size
        inscription_regions = _scale_regions_to_original(inscription_regions, scale, orig_w, orig_h)
        painting_regions = _scale_regions_to_original(painting_regions, scale, orig_w, orig_h)
        blank_regions = _scale_regions_to_original(blank_regions, scale, orig_w, orig_h)
        
        return {
            "success": True,
            "regions": {
                "inscription_regions": inscription_regions,
                "painting_regions": painting_regions,
                "blank_regions": blank_regions,
            },
            "analysis_note": analysis_note,
            "confidence": classification.overall_confidence,
            "group": group.primary_group.value,
            "used_vl": used_vl,
            "_meta": {
                "pipeline": "cv_first",
                "preprocessing": std_img.clahe_params,
                "group_classification": group.confidence,
                "cv_features_count": len(masks.region_features),
            }
        }
    
    except Exception as e:
        print(f"[CV-First] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "regions": {
                "inscription_regions": [],
                "painting_regions": [],
                "blank_regions": [],
            },
        }


def _mask_to_polygon_regions(mask: np.ndarray, width: int, height: int, scale: float, max_regions: int = 5) -> List[Dict]:
    """将mask转换为多边形regions格式（像素坐标，与原有流程兼容）"""
    regions = []

    # 先做闭运算合并相近的碎片，减少碎片化
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 查找轮廓
    contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 基于图像面积计算最小过滤面积（提高门槛，进一步减少碎片）
    image_area = width * height
    min_area = max(500, int(image_area * 0.0005))  # 至少500px，或图像面积的0.05%

    items = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        # 简化轮廓
        peri = cv2.arcLength(contour, True)
        epsilon = max(0.5, peri * 0.003)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        if approx is None or len(approx) < 3:
            continue

        pts = approx.reshape(-1, 2).tolist()
        items.append((area, pts))

    # 按面积从大到小排序，只取前max_regions个
    items.sort(key=lambda t: t[0], reverse=True)

    for _, pts in items[:max_regions]:
        # 返回像素坐标（与原有mask_to_regions兼容）
        regions.append({
            "points": [{"x": int(x), "y": int(y)} for x, y in pts],
            "type": "polygon",
        })

    return regions


def _scale_regions_to_original(regions: List[Dict], scale: float, orig_w: int, orig_h: int) -> List[Dict]:
    """将预处理图（2048px长边）上的像素坐标映射回原始图像像素坐标"""
    if scale <= 0 or scale >= 1.0:
        return regions

    scaled = []
    for region in regions:
        new_region = dict(region)
        if "points" in region and isinstance(region["points"], list):
            new_points = []
            for p in region["points"]:
                new_points.append({
                    "x": int(round(p["x"] / scale)),
                    "y": int(round(p["y"] / scale)),
                })
            new_region["points"] = new_points
        scaled.append(new_region)
    return scaled


def _build_analysis_note(group, classification, std_img) -> str:
    """构建分析说明"""
    group_name = group.primary_group.value
    
    notes = [
        f"画作类型：{group_name}",
        f"分析置信度：{classification.overall_confidence:.0%}",
        f"检测到题跋区域：{sum(1 for r in classification.regions if r.category == 'inscription')}个",
        f"检测到绘画区域：{sum(1 for r in classification.regions if r.category == 'painting')}个",
    ]
    
    if classification.low_confidence_count > 0:
        notes.append(f"低置信度区域：{classification.low_confidence_count}个（已触发VL校验）")
    
    return "\n".join(notes)
