"""
Local batch reprocess script - no LLM API needed
Uses local CV algorithm (grid density) to recalculate inscription percentage + regenerate annotated images
"""
import sys
import os
import io
import json
import time
import argparse
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from PIL import Image

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.path_utils import normalize_path
from app.models.tubi_analysis import TubiAnalysis
from app.services.tubi_auto_params import compute_tubi_params
from app.services.auto_tags import compute_tags
from app.services.tubi_mask_refiner import detect_inscription_grid_density, regions_to_mask
from app.services.siliconflow_service import calculate_area_stats
from app.services.inscription_position_analyzer import analyze_inscription_position
from app.api.tubi import ANNOTATED_DIR, draw_annotated_image

settings = get_settings()

# 标注图红色（BGR）
RED_BGR = (60, 60, 220)


def reprocess_one(record, dry_run=False):
    """重处理单条记录，返回 (success, message)"""
    image_id = record.image_id
    filepath = record.filepath
    width = record.image_width or 0
    height = record.image_height or 0

    # 基础检查
    if not filepath or not os.path.isfile(filepath):
        return False, f"文件不存在: {filepath}"

    if width == 0 or height == 0:
        try:
            with Image.open(filepath) as img:
                width, height = img.size
        except Exception as e:
            return False, f"读取图像尺寸失败: {e}"

    # 获取已有 regions（LLM 之前返回的种子数据）
    regions = record.regions or {}
    if not isinstance(regions, dict):
        regions = {}

    insc_regions = regions.get("inscription_regions", []) or []
    if not insc_regions:
        # 没有 LLM 种子数据，无法做本地精修
        return False, "无 inscription_regions 种子数据"

    if dry_run:
        return True, f"DRY RUN: 有 {len(insc_regions)} 个题跋种子区域"

    # ---- 本地计算开始 ----
    try:
        # 1. 计算自动参数
        auto = compute_tubi_params(filepath, width, height, regions)
        insc_auto = (auto or {}).get("insc") or {}

        # 2. 网格密度法检测题跋
        inscription_mask = None
        try:
            refined_insc = detect_inscription_grid_density(
                image_path=filepath,
                inscription_regions=insc_regions,
                image_width=width,
                image_height=height,
                expand_x_ratio=float(insc_auto.get("expand_x_ratio", 0.22)),
                expand_x_min=int(insc_auto.get("expand_x_min", 48)),
                expand_y_ratio=float(insc_auto.get("expand_y_ratio", 0.10)),
                density_thresh_core=float(insc_auto.get("density_thresh_core", 0.055)),
                density_thresh_expand=float(insc_auto.get("density_thresh_expand", 0.120)),
                return_mask=True,
                debug_dir=None,
            )
            if refined_insc.get("ok"):
                inscription_mask = refined_insc.get("mask")
        except Exception as e:
            print(f"    网格密度法异常: {e}")

        # 3. 如果网格密度法失败，回退到种子 mask
        if inscription_mask is None:
            try:
                inscription_seed_mask = regions_to_mask(insc_regions, width, height)
                if cv2.countNonZero(inscription_seed_mask) > 0:
                    inscription_mask = inscription_seed_mask
            except Exception:
                pass

        if inscription_mask is None:
            return False, "无法生成题跋 mask"

        # 4. 计算面积占比（只有题跋比）
        total_pixels = float(width * height)
        insc_px = float(cv2.countNonZero(inscription_mask))
        inscription_percent = float(round(insc_px / total_pixels * 100.0, 2)) if total_pixels > 0 else 0.0

        # 5. 更新 regions meta
        try:
            meta = regions.get("_meta") if isinstance(regions, dict) else None
            if not isinstance(meta, dict):
                meta = {}
            meta["auto_params"] = {k: v for k, v in (auto or {}).items() if k in ("paint", "insc", "expand", "seal")}
            meta["auto_metrics"] = (auto or {}).get("metrics") or {}
            meta["provider"] = "local_batch_reprocess"
            meta["normalized_regions"] = True
            regions["_meta"] = meta
        except Exception:
            pass

        # 6. 重新计算 area_stats
        try:
            area_stats = calculate_area_stats(regions, width, height)
        except Exception:
            area_stats = {"inscription_percent": 0.0, "painting_percent": 0.0, "blank_percent": 0.0}
        area_stats["inscription_percent"] = inscription_percent
        area_stats["painting_percent"] = 0.0
        area_stats["blank_percent"] = 0.0

        # 7. 生成标注图（只画题跋红色叠加）
        annotated_filename = f"annotated_{image_id}.jpg"
        annotated_path = os.path.join(ANNOTATED_DIR, annotated_filename)
        annotated_image_path = None
        try:
            img_bgr = cv2.imread(filepath, cv2.IMREAD_COLOR)
            if img_bgr is not None and cv2.countNonZero(inscription_mask) > 0:
                red = np.zeros_like(img_bgr)
                red[:, :, 0] = RED_BGR[0]  # B
                red[:, :, 1] = RED_BGR[1]  # G
                red[:, :, 2] = RED_BGR[2]  # R
                ins_blend = cv2.addWeighted(img_bgr, 0.50, red, 0.50, 0.0)
                cv2.copyTo(ins_blend, inscription_mask, img_bgr)
                cv2.imwrite(annotated_path, img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                annotated_image_path = normalize_path(annotated_path)
        except Exception as e:
            print(f"    标注图生成异常: {e}")

        # 9. 位置分析
        try:
            position_analysis = analyze_inscription_position(regions, width, height)
        except Exception:
            position_analysis = {}

        # 10. 写入数据库
        db = SessionLocal()
        try:
            rec = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
            if rec:
                rec.regions = regions
                rec.inscription_percent = inscription_percent
                rec.painting_percent = 0.0
                rec.blank_percent = 0.0
                rec.position_analysis = position_analysis
                rec.analysis_note = (rec.analysis_note or "") + " [本地重处理v4]"
                rec.image_width = width
                rec.image_height = height
                if annotated_image_path:
                    rec.annotated_image_path = annotated_image_path
                rec.status = "analyzed"
                # 自动标签持久化
                try:
                    record_for_tags = {
                        "title": rec.title,
                        "period_phase": rec.period_phase,
                        "artwork_height_cm": rec.artwork_height_cm,
                        "artwork_width_cm": rec.artwork_width_cm,
                        "content_analysis": rec.content_analysis,
                        "material_tags": rec.material_tags,
                    }
                    auto_tags = compute_tags(record_for_tags)
                    if auto_tags:
                        existing_tags = []
                        if rec.tags:
                            try:
                                existing_tags = json.loads(rec.tags) if isinstance(rec.tags, str) else rec.tags
                            except Exception:
                                existing_tags = []
                        if not isinstance(existing_tags, list):
                            existing_tags = []
                        for tag in auto_tags:
                            if tag not in existing_tags:
                                existing_tags.append(tag)
                        rec.tags = json.dumps(existing_tags, ensure_ascii=False)
                except Exception as e:
                    print(f"  [警告] 自动标签持久化失败: {e}")
                db.commit()
        finally:
            db.close()

        return True, f"题跋比={inscription_percent}%"

    except Exception as e:
        return False, f"处理异常: {e}\n{traceback.format_exc()}"


def main():
    parser = argparse.ArgumentParser(description="本地批量重处理题跋分析")
    parser.add_argument("--force", action="store_true", help="强制重处理所有记录（包括v4已完成的）")
    parser.add_argument("--dry-run", action="store_true", help="只看不做")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(TubiAnalysis)
        if not args.force:
            # 只处理旧算法记录（painting_percent > 0 或 blank_percent > 0）
            query = query.filter(
                (TubiAnalysis.painting_percent > 0) | (TubiAnalysis.blank_percent > 0)
            )

        records = query.all()
        total = len(records)
    finally:
        db.close()

    if total == 0:
        print("没有需要重处理的记录。")
        return

    print(f"{'DRY RUN - ' if args.dry_run else ''}需要重处理: {total} 条记录")
    print("=" * 60)

    success = 0
    failed = 0
    skipped = 0
    start_time = time.time()

    for i, record in enumerate(records):
        image_id = record.image_id
        fname = record.filename or ""
        old_insc = record.inscription_percent or 0

        ok, msg = reprocess_one(record, dry_run=args.dry_run)

        elapsed = time.time() - start_time
        if i > 0:
            avg = elapsed / i
            eta = avg * (total - i)
            eta_str = f"ETA {eta:.0f}s"
        else:
            eta_str = ""

        status = "✅" if ok else "❌"
        print(f"  [{i+1}/{total}] {status} {image_id[:8]} {fname[:20]:20s} ins={old_insc:.1f}%→{msg} {eta_str}")

        if ok:
            success += 1
        else:
            failed += 1

    elapsed = time.time() - start_time
    print("=" * 60)
    print(f"完成！成功={success}, 失败={failed}, 跳过={skipped}, 耗时={elapsed:.1f}s")

    if failed > 0:
        print(f"\n失败记录需要 LLM API 单独处理（无种子数据的情况）")


if __name__ == "__main__":
    main()
