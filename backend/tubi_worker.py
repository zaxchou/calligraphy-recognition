import time
import concurrent.futures
import os
import cv2
import json
import numpy as np
import redis
from PIL import Image
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.path_utils import normalize_path
from app.models.tubi_analysis import TubiAnalysis
from app.models.tubi_job import TubiJob
from app.services.inscription_position_analyzer import analyze_inscription_position
from app.services.siliconflow_service import analyze_image_regions, calculate_area_stats, analyze_text_summary_only
from app.services.tubi_auto_params import compute_tubi_params
from app.services.auto_tags import compute_tags
from app.services.inscription_content_analyzer import extract_material_tags
from app.services.tubi_mask_refiner import detect_inscription_grid_density, mask_to_regions, regions_to_mask
from app.api.tubi import ANNOTATED_DIR, draw_annotated_image
from app.services.qwen_vl_ocr_router import OCRRouter
from app.tubi.integration import run_cv_first_analysis


def generate_heatmap_data(regions: Dict, width: int, height: int) -> list:
    """将区域数据转换为热力图数据格式"""
    heatmap = []
    region_map = {
        'painting': regions.get('painting_regions', []),
        'inscription': regions.get('inscription_regions', []),
    }
    for rtype, region_list in region_map.items():
        if not isinstance(region_list, list):
            continue
        for idx, region in enumerate(region_list):
            if not isinstance(region, dict):
                continue
            bbox = region.get('bbox', [])
            if len(bbox) == 4:
                heatmap.append({
                    'type': rtype,
                    'x': float(bbox[0]) / width,
                    'y': float(bbox[1]) / height,
                    'w': float(bbox[2] - bbox[0]) / width,
                    'h': float(bbox[3] - bbox[1]) / height,
                    'density': region.get('confidence', 0.5),
                })
    return heatmap


def _filter_ocr_by_mask(ocr_items, inscription_mask, width, height, min_overlap_pct=0.15):
    """
    用 inscription_mask 过滤 OCR 检测结果，只保留落在题跋区域内的文字框。
    min_overlap_pct: bbox 面积中有多少比例必须落在 mask 内才算通过（默认15%）
    """
    if inscription_mask is None or width == 0 or height == 0:
        return []
    filtered = []
    mask_h, mask_w = inscription_mask.shape[:2]
    scale_x = mask_w / width
    scale_y = mask_h / height
    for item in ocr_items:
        bbox = item["bbox"]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        # 映射到 mask 坐标
        mx1 = int(x1 * scale_x); my1 = int(y1 * scale_y)
        mx2 = int(x2 * scale_x); my2 = int(y2 * scale_y)
        mx1_c = max(0, mx1); my1_c = max(0, my1)
        mx2_c = min(mask_w, mx2); my2_c = min(mask_h, my2)
        if mx2_c <= mx1_c or my2_c <= my1_c:
            continue
        mask_roi = inscription_mask[my1_c:my2_c, mx1_c:mx2_c]
        mask_pixel_count = cv2.countNonZero(mask_roi)
        total_pixel_count = (mx2_c - mx1_c) * (my2_c - my1_c)
        if total_pixel_count <= 0:
            continue
        overlap_pct = mask_pixel_count / total_pixel_count
        if overlap_pct >= min_overlap_pct:
            filtered.append(item)
    return filtered


settings = get_settings()
QUEUE_KEY_PENDING = "tubi:queue:pending"
QUEUE_KEY_PROCESSING = "tubi:queue:processing"


def get_redis():
    conn = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1.0,
        socket_timeout=15.0,
        retry_on_timeout=True
    )
    conn.ping()
    return conn


def requeue_processing(conn):
    while True:
        item = conn.rpop(QUEUE_KEY_PROCESSING)
        if not item:
            break
        conn.lpush(QUEUE_KEY_PENDING, item)


def cleanup_stale_jobs():
    threshold = datetime.now() - timedelta(minutes=30)
    db = SessionLocal()
    try:
        inflight_jobs = db.query(TubiJob).filter(TubiJob.status == "processing").all()
        if inflight_jobs:
            inflight_ids = [j.image_id for j in inflight_jobs]
            for j in inflight_jobs:
                j.status = "queued"
                j.last_error = "任务重启已重排队"
            db.commit()

            inflight_analyses = (
                db.query(TubiAnalysis)
                .filter(TubiAnalysis.image_id.in_(inflight_ids))
                .filter(TubiAnalysis.status == "analyzing")
                .all()
            )
            if inflight_analyses:
                for a in inflight_analyses:
                    a.status = "queued"
                    a.analysis_note = "任务重启已重排队"
                db.commit()

        stale = (
            db.query(TubiAnalysis)
            .filter(TubiAnalysis.status == "analyzing")
            .filter(TubiAnalysis.updated_at.isnot(None))
            .filter(TubiAnalysis.updated_at < threshold)
            .all()
        )
        if stale:
            for a in stale:
                a.status = "error"
                a.analysis_note = "分析超时，请重试"
            db.commit()

        jobs = (
            db.query(TubiJob)
            .filter(TubiJob.status == "processing")
            .filter(TubiJob.updated_at.isnot(None))
            .filter(TubiJob.updated_at < threshold)
            .all()
        )
        if jobs:
            for j in jobs:
                j.status = "queued"
                j.last_error = "任务超时已重排队"
            db.commit()
    finally:
        db.close()


def analyze_with_timeout(filepath, width, height, timeout_seconds=900):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(analyze_image_regions, filepath, width, height)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError:
        try:
            future.cancel()
        except Exception:
            pass
        return {"success": False, "error": "分析超时，请重试"}
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass



def process_one(conn, image_id: str):
    db = SessionLocal()
    db_analysis = None
    db_job = None
    try:
        db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
        if not db_analysis:
            return

        db_job = db.query(TubiJob).filter(TubiJob.image_id == image_id).first()
        if db_job:
            db_job.status = "processing"
            db_job.last_error = None
        else:
            db_job = TubiJob(image_id=image_id, status="processing")
            db.add(db_job)
        db.commit()

        db_analysis.status = "analyzing"
        db.commit()

        # 读取分析模式
        mode = db_job.mode if db_job and db_job.mode else "analyze"
        is_text_only = (mode == "analyze_text_only")
        print(f"[tubi_worker] image={image_id} mode={mode} text_only={is_text_only}")

        filepath = db_analysis.filepath
        width = db_analysis.image_width or 0
        height = db_analysis.image_height or 0

        if not filepath:
            db_analysis.status = "error"
            db_analysis.analysis_note = "图像文件不存在"
            db.commit()
            return

        if width == 0 or height == 0:
            with Image.open(filepath) as img:
                width, height = img.size
                db_analysis.image_width = width
                db_analysis.image_height = height
            db.commit()

        # ===== 根据 mode 分支处理 =====
        if mode == "analyze_text_only":
            # ── 轻量化模式：只调用AI快速点评 ──
            print(f"[tubi_worker] 轻量化AI文本分析模式: {image_id}")
            
            text_result = analyze_text_summary_only(filepath)
            if not text_result or not text_result.get("success", False):
                error_msg = text_result.get("error", "轻量化分析失败") if text_result else "轻量化分析失败"
                db_analysis.status = "error"
                db_analysis.analysis_note = error_msg
                db.commit()
                return
            
            db_analysis.analysis_note = text_result.get("analysis_note", "")
            # 提取并保存画材标签
            try:
                material_tags_list = extract_material_tags(
                    db_analysis.title or "",
                    db_analysis.analysis_note or ""
                )
                if material_tags_list:
                    db_analysis.material_tags = ",".join(material_tags_list)
                else:
                    db_analysis.material_tags = None
            except Exception as e:
                print(f"[tubi_worker] 提取画材标签失败: {e}")
                db_analysis.material_tags = None
            db_analysis.status = "analyzed"
            if db_job:
                db_job.status = "done"
                db_job.last_error = None
            # 自动标签持久化
            try:
                record_for_tags = {
                    "title": db_analysis.title,
                    "period_phase": db_analysis.period_phase,
                    "artwork_height_cm": db_analysis.artwork_height_cm,
                    "artwork_width_cm": db_analysis.artwork_width_cm,
                    "content_analysis": db_analysis.content_analysis,
                    "material_tags": db_analysis.material_tags,
                }
                auto_tags = compute_tags(record_for_tags)
                if auto_tags:
                    existing_tags = []
                    if db_analysis.tags:
                        try:
                            existing_tags = json.loads(db_analysis.tags) if isinstance(db_analysis.tags, str) else db_analysis.tags
                        except Exception:
                            existing_tags = []
                    if not isinstance(existing_tags, list):
                        existing_tags = []
                    for tag in auto_tags:
                        if tag not in existing_tags:
                            existing_tags.append(tag)
                    db_analysis.tags = json.dumps(existing_tags, ensure_ascii=False)
            except Exception as e:
                print(f"[tubi_worker] 自动标签持久化失败: {e}")
            db.commit()
            
        else:
            # ── 完整模式：CV-First新流程（区域检测+OCR+标注图）──
            print(f"[tubi_worker] 完整分析模式: {image_id}")
            
            # 尝试CV-First新流程
            use_cv_first = getattr(settings, "USE_CV_FIRST_PIPELINE", True)
            result = None
            regions = {}
            
            if use_cv_first:
                print(f"[tubi_worker] Trying CV-First pipeline...")
                try:
                    cv_result = run_cv_first_analysis(filepath, width, height)
                    if cv_result.get("success"):
                        result = cv_result
                        regions = result.get("regions", {})
                        print(f"[tubi_worker] CV-First pipeline succeeded. Group: {result.get('group', 'unknown')}, Confidence: {result.get('confidence', 0):.2f}")
                    else:
                        print(f"[tubi_worker] CV-First failed: {cv_result.get('error', 'unknown')}, falling back to VL")
                except Exception as e:
                    print(f"[tubi_worker] CV-First exception: {e}, falling back to VL")
            
            # 如果CV-First失败或未启用，回退到原有VL流程
            if not result:
                result = analyze_with_timeout(filepath, width, height)
                if not result or not result.get("success", False):
                    error_msg = result.get("error", "分析失败") if result else "分析失败"
                    db_analysis.status = "error"
                    db_analysis.analysis_note = error_msg
                    db.commit()
                    return
                regions = result.get("regions", {})

            try:
                paint_seed = regions_to_mask(regions.get("painting_regions", []) or [], width, height)
                insc_seed = regions_to_mask(regions.get("inscription_regions", []) or [], width, height)
                if cv2.countNonZero(paint_seed) > 0 and cv2.countNonZero(insc_seed) > 0:
                    paint_norm = cv2.subtract(paint_seed, insc_seed)
                    norm_regions = mask_to_regions(paint_norm)
                    if norm_regions:
                        regions["painting_regions"] = norm_regions
            except Exception:
                pass

            auto = compute_tubi_params(filepath, width, height, regions)
            try:
                meta = regions.get("_meta") if isinstance(regions, dict) else None
                if not isinstance(meta, dict):
                    meta = {}
                meta["auto_params"] = {k: v for k, v in (auto or {}).items() if k in ("paint", "insc", "expand", "seal")}
                meta["auto_metrics"] = (auto or {}).get("metrics") or {}
                meta["provider"] = result.get("provider")
                meta["normalized_regions"] = True
                regions["_meta"] = meta
            except Exception:
                pass

            try:
                area_stats = calculate_area_stats(regions, width, height)
            except Exception:
                area_stats = {
                    "inscription_percent": 0.0,
                    "painting_percent": 0.0,
                    "blank_percent": 0.0
                }

            dbg = None
            if getattr(settings, "TUBI_DEBUG_SAVE_IMAGES", False):
                dbg = os.path.join(getattr(settings, "TUBI_DEBUG_DIR", ""), image_id)

            # ===== 只检测题跋占比（网格密度法 v4），不再区分绘画/留白 =====
            inscription_mask = None
            insc_auto = (auto or {}).get("insc") or {}
            try:
                refined_insc = detect_inscription_grid_density(
                    image_path=filepath,
                    inscription_regions=regions.get("inscription_regions", []) or [],
                    image_width=width,
                    image_height=height,
                    expand_x_ratio=float(insc_auto.get("expand_x_ratio", 0.22)),
                    expand_x_min=int(insc_auto.get("expand_x_min", 48)),
                    expand_y_ratio=float(insc_auto.get("expand_y_ratio", 0.10)),
                    density_thresh_core=float(insc_auto.get("density_thresh_core", 0.055)),
                    density_thresh_expand=float(insc_auto.get("density_thresh_expand", 0.120)),
                    return_mask=True,
                    debug_dir=dbg,
                )
                if refined_insc.get("ok"):
                    inscription_mask = refined_insc.get("mask")
            except Exception:
                inscription_mask = None

            # 如果网格密度法失败，回退到种子 mask
            if inscription_mask is None:
                try:
                    inscription_seed_mask = regions_to_mask(regions.get("inscription_regions", []) or [], width, height)
                    if cv2.countNonZero(inscription_seed_mask) > 0:
                        inscription_mask = inscription_seed_mask
                except Exception:
                    inscription_mask = None

            # 用 inscription_mask 重新计算题跋占比，保留 painting/blank 的原始值
            if inscription_mask is not None:
                total_pixels = float(width * height) if width > 0 and height > 0 else 0.0
                if total_pixels > 0:
                    insc_px = float(cv2.countNonZero(inscription_mask))
                    area_stats["inscription_percent"] = float(round(insc_px / total_pixels * 100.0, 2))
                    # painting_percent 和 blank_percent 保持 calculate_area_stats 的计算值，不覆盖

            try:
                position_analysis = analyze_inscription_position(regions, width, height, image_path=filepath)
            except Exception:
                position_analysis = {}

            # ── V9 OCR（用 inscription_mask 过滤，只保留题跋区域内的文字）─────────────
            inscription_content = None
            ocr_items_for_draw = []
            try:
                if filepath and os.path.exists(filepath):
                    ocr_router = OCRRouter()
                    ocr_result = ocr_router.process(filepath, width, height)
                    if ocr_result.get("success"):
                        all_items = ocr_result.get("ocr_items", [])
                        filtered_items = _filter_ocr_by_mask(all_items, inscription_mask, width, height)
                        ocr_items_for_draw = filtered_items
                        # 构文字内容字符串
                        content_parts = []
                        for item in filtered_items:
                            tag = f"[{item.get('crop_name', '')}]" if item.get("from_crop") else ""
                            content_parts.append(f"{tag}{item['text']}")
                        inscription_content = " | ".join(content_parts) if content_parts else None
                        print(f"[V9 OCR] {len(all_items)} 条检测 -> 题跋区域内 {len(filtered_items)} 条")
            except Exception as e:
                print(f"[V9 OCR] failed: {e}")

            annotated_filename = f"annotated_{image_id}.jpg"
            annotated_path = f"{ANNOTATED_DIR}/{annotated_filename}"
            annotated_image_path = None
            if not is_text_only:
                try:
                    # 只画题跋（红色叠加），不画绘画和留白（仅非仅文字模式）
                    if inscription_mask is not None:
                        img_bgr = cv2.imread(filepath, cv2.IMREAD_COLOR)
                        if img_bgr is None:
                            raise RuntimeError("annotated_image_read_failed")

                        # 绘画区域 - 蓝色叠加（BGR: B高R低 = 蓝色）
                        painting_regions = regions.get("painting_regions", []) or []
                        if painting_regions:
                            painting_mask = regions_to_mask(painting_regions, img_bgr.shape[1], img_bgr.shape[0])
                            if cv2.countNonZero(painting_mask) > 0:
                                blue = np.zeros_like(img_bgr)
                                blue[:, :, 0] = 220    # B
                                blue[:, :, 1] = 100    # G
                                blue[:, :, 2] = 50     # R
                                paint_blend = cv2.addWeighted(img_bgr, 0.50, blue, 0.50, 0.0)
                                cv2.copyTo(paint_blend, painting_mask, img_bgr)

                        # 题跋区域 - 红色叠加（BGR: R高B低 = 红色）
                        if cv2.countNonZero(inscription_mask) > 0:
                            red = np.zeros_like(img_bgr)
                            red[:, :, 0] = 60     # B
                            red[:, :, 1] = 60     # G
                            red[:, :, 2] = 220    # R
                            ins_blend = cv2.addWeighted(img_bgr, 0.50, red, 0.50, 0.0)
                            cv2.copyTo(ins_blend, inscription_mask, img_bgr)

                        # ── 在标注图上绘制 OCR 检测框（亮红色边框）─────────────────────
                        if ocr_items_for_draw:
                            PAD_BASE = 0.12
                            for item in ocr_items_for_draw:
                                bbox = item["bbox"]
                                bw = bbox[2] - bbox[0]
                                bh = bbox[3] - bbox[1]
                                pad_x = max(2, int(bw * PAD_BASE))
                                pad_y = max(2, int(bh * PAD_BASE))
                                rx1 = max(0, bbox[0] - pad_x); ry1 = max(0, bbox[1] - pad_y)
                                rx2 = min(width, bbox[2] + pad_x); ry2 = min(height, bbox[3] + pad_y)
                                # 亮红色边框（主路=绿色系，补路=不同颜色）
                                if item.get("from_crop"):
                                    crop_name = item.get("crop_name", "")
                                    ocr_color = {"右半": (50, 130, 255), "右三": (200, 0, 255), "左三": (0, 200, 255)}.get(crop_name, (255, 100, 100))
                                else:
                                    ocr_color = (0, 255, 0)   # 亮绿（主路）
                                cv2.rectangle(img_bgr, (rx1, ry1), (rx2, ry2), ocr_color, 2)

                        cv2.imwrite(annotated_path, img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                        annotated_image_path = normalize_path(annotated_path)
                    else:
                        annotated_result = draw_annotated_image(filepath, regions, annotated_path)
                        if annotated_result:
                            annotated_image_path = normalize_path(annotated_result)
                except Exception:
                    annotated_image_path = None

            # 保护手动编辑的 regions 不被覆盖
            try:
                existing_raw = db_analysis.regions
                if existing_raw and isinstance(regions, dict):
                    existing_dict = json.loads(existing_raw) if isinstance(existing_raw, str) else existing_raw
                    if isinstance(existing_dict, dict):
                        meta = existing_dict.get("_meta")
                        if isinstance(meta, dict) and meta.get("user_edited"):
                            print(f"[tubi_worker] 检测到手动编辑标记，保留用户区域数据")
                            user_insc = existing_dict.get("inscription_regions", [])
                            user_paint = existing_dict.get("painting_regions", [])
                            if user_insc or user_paint:
                                regions["inscription_regions"] = user_insc
                                regions["painting_regions"] = user_paint
                                new_meta = regions.get("_meta", {})
                                if isinstance(new_meta, dict):
                                    new_meta["user_edited"] = True
                                    new_meta["preserved_from_manual"] = True
                                else:
                                    new_meta = {"user_edited": True, "preserved_from_manual": True}
                                regions["_meta"] = new_meta
            except Exception as e:
                print(f"[tubi_worker] 保护手动编辑数据时出错: {e}")

            db_analysis.regions = regions
            if not is_text_only:
                # 仅非仅文字模式时保存面积统计和标注图
                db_analysis.inscription_percent = area_stats.get("inscription_percent", 0.0)
                db_analysis.painting_percent = area_stats.get("painting_percent", 0.0)
                db_analysis.blank_percent = area_stats.get("blank_percent", 0.0)
                if annotated_image_path:
                    db_analysis.annotated_image_path = annotated_image_path
            db_analysis.position_analysis = position_analysis
            db_analysis.analysis_note = result.get("analysis_note", "")
            # 只有未校对时才覆盖 inscription_content，已校对的保留用户手动录入的文本
            if inscription_content is not None and not db_analysis.inscription_verified:
                db_analysis.inscription_content = inscription_content
            # 提取并保存画材标签
            try:
                material_tags_list = extract_material_tags(
                    db_analysis.title or "",
                    db_analysis.analysis_note or ""
                )
                if material_tags_list:
                    db_analysis.material_tags = ",".join(material_tags_list)
                else:
                    db_analysis.material_tags = None
            except Exception as e:
                print(f"[tubi_worker] 提取画材标签失败: {e}")
                db_analysis.material_tags = None
            db_analysis.status = "analyzed"
            if db_job:
                db_job.status = "done"
                db_job.last_error = None
            # 自动标签持久化
            try:
                record_for_tags = {
                    "title": db_analysis.title,
                    "period_phase": db_analysis.period_phase,
                    "artwork_height_cm": db_analysis.artwork_height_cm,
                    "artwork_width_cm": db_analysis.artwork_width_cm,
                    "content_analysis": db_analysis.content_analysis,
                    "material_tags": db_analysis.material_tags,
                }
                auto_tags = compute_tags(record_for_tags)
                if auto_tags:
                    existing_tags = []
                    if db_analysis.tags:
                        try:
                            existing_tags = json.loads(db_analysis.tags) if isinstance(db_analysis.tags, str) else db_analysis.tags
                        except Exception:
                            existing_tags = []
                    if not isinstance(existing_tags, list):
                        existing_tags = []
                    for tag in auto_tags:
                        if tag not in existing_tags:
                            existing_tags.append(tag)
                    db_analysis.tags = json.dumps(existing_tags, ensure_ascii=False)
            except Exception as e:
                print(f"[tubi_worker] 自动标签持久化失败: {e}")
            db.commit()
    except Exception as e:
        if db_analysis:
            try:
                db_analysis.status = "error"
                db_analysis.analysis_note = f"分析失败: {str(e)}"
                if db_job:
                    db_job.status = "error"
                    db_job.last_error = (db_analysis.analysis_note or "")[:500]
                db.commit()
            except Exception:
                pass
    finally:
        db.close()


def run():
    conn = None
    cleanup_stale_jobs()
    try:
        conn = get_redis()
        requeue_processing(conn)
    except Exception:
        conn = None

    if conn:
        lock = conn.lock("tubi:analysis:lock", timeout=1800)
        while True:
            try:
                image_id = conn.brpoplpush(QUEUE_KEY_PENDING, QUEUE_KEY_PROCESSING, timeout=5)
            except redis.exceptions.TimeoutError:
                continue
            except redis.exceptions.ConnectionError:
                try:
                    conn = get_redis()
                    lock = conn.lock("tubi:analysis:lock", timeout=1800)
                except Exception:
                    time.sleep(1)
                continue
            if not image_id:
                continue

            acquired = lock.acquire(blocking=True, blocking_timeout=5)
            if not acquired:
                conn.lrem(QUEUE_KEY_PROCESSING, 1, image_id)
                conn.lpush(QUEUE_KEY_PENDING, image_id)
                continue

            try:
                process_one(conn, image_id)
            finally:
                try:
                    lock.release()
                except Exception:
                    pass
                conn.lrem(QUEUE_KEY_PROCESSING, 0, image_id)
    else:
        while True:
            db = SessionLocal()
            job = None
            try:
                job = db.query(TubiJob).filter(TubiJob.status == "queued").order_by(TubiJob.created_at.asc()).first()
                if not job:
                    time.sleep(1)
                    continue
                job.status = "processing"
                db.commit()
                image_id = job.image_id
            finally:
                db.close()

            process_one(conn, image_id)

            db = SessionLocal()
            try:
                job = db.query(TubiJob).filter(TubiJob.image_id == image_id).first()
                analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
                if job:
                    if analysis and analysis.status == "analyzed":
                        job.status = "done"
                        job.last_error = None
                    elif analysis and analysis.status == "error":
                        job.status = "error"
                        job.last_error = (analysis.analysis_note or "")[:500]
                    else:
                        job.status = "error"
                        job.last_error = "任务结束但未生成结果"
                    db.commit()
            finally:
                db.close()

            time.sleep(1)


if __name__ == "__main__":
    run()
