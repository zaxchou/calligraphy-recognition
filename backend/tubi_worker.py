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
from app.services.siliconflow_service import analyze_image_regions
from app.services.tubi_auto_params import compute_tubi_params
from app.services.auto_tags import compute_tags
from app.services.inscription_content_analyzer import extract_material_tags
from app.services.tubi_mask_refiner import detect_inscription_grid_density, mask_to_regions, regions_to_mask
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
        print(f"[tubi_worker] image={image_id} mode={mode}")

        filepath = db_analysis.filepath
        width = db_analysis.image_width or 0
        height = db_analysis.image_height or 0

        if not filepath:
            db_analysis.status = "error"
            db.commit()
            return

        if width == 0 or height == 0:
            with Image.open(filepath) as img:
                width, height = img.size
                db_analysis.image_width = width
                db_analysis.image_height = height
            db.commit()

        # ===== 统一识图流程：区域检测（内部用于OCR过滤）+ OCR + 画材标签 =====
        # 区域检测（仅供内部 OCR 过滤用，不落库）
        print(f"[tubi_worker] 开始区域检测: {image_id}")
        use_cv_first = getattr(settings, "USE_CV_FIRST_PIPELINE", True)
        result = None
        regions = {}

        if use_cv_first:
            try:
                cv_result = run_cv_first_analysis(filepath, width, height)
                if cv_result.get("success"):
                    result = cv_result
                    regions = result.get("regions", {})
                    print(f"[tubi_worker] CV-First succeeded. Group: {result.get('group', 'unknown')}")
                else:
                    print(f"[tubi_worker] CV-First failed: {cv_result.get('error', 'unknown')}, falling back to VL")
            except Exception as e:
                print(f"[tubi_worker] CV-First exception: {e}, falling back to VL")

        if not result:
            result = analyze_with_timeout(filepath, width, height)
            if not result or not result.get("success", False):
                error_msg = result.get("error", "分析失败") if result else "分析失败"
                db_analysis.status = "error"
                db.commit()
                return
            regions = result.get("regions", {})

        # 遮罩生成（用于 OCR 题跋区域过滤）
        inscription_mask = None
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
            )
            if refined_insc.get("ok"):
                inscription_mask = refined_insc.get("mask")
        except Exception:
            pass

        if inscription_mask is None:
            try:
                inscription_seed_mask = regions_to_mask(regions.get("inscription_regions", []) or [], width, height)
                if cv2.countNonZero(inscription_seed_mask) > 0:
                    inscription_mask = inscription_seed_mask
            except Exception:
                pass

        # ── OCR 文字识别（用 inscription_mask 过滤）──
        inscription_content = None
        try:
            if filepath and os.path.exists(filepath):
                ocr_router = OCRRouter()
                ocr_result = ocr_router.process(filepath, width, height)
                if ocr_result.get("success"):
                    all_items = ocr_result.get("ocr_items", [])
                    filtered_items = _filter_ocr_by_mask(all_items, inscription_mask, width, height)
                    content_parts = []
                    for item in filtered_items:
                        tag = f"[{item.get('crop_name', '')}]" if item.get("from_crop") else ""
                        content_parts.append(f"{tag}{item['text']}")
                    inscription_content = " | ".join(content_parts) if content_parts else None
                    print(f"[tubi_worker] OCR: {len(all_items)} 条 -> 题跋区域 {len(filtered_items)} 条")
        except Exception as e:
            print(f"[tubi_worker] OCR failed: {e}")

        # ── 落库：只持久化需要的数据 ──
        # 只有未校对时才覆盖 inscription_content
        if inscription_content is not None and not db_analysis.inscription_verified:
            db_analysis.inscription_content = inscription_content

        # 画材标签（从 title 提取，不再依赖 AI 点评）
        try:
            material_tags_list = extract_material_tags(db_analysis.title or "", "")
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
