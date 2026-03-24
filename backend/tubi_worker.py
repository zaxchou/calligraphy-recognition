import time
import concurrent.futures
import redis
from PIL import Image
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.path_utils import normalize_path
from app.models.tubi_analysis import TubiAnalysis
from app.models.tubi_job import TubiJob
from app.services.inscription_position_analyzer import analyze_inscription_position
from app.services.siliconflow_service import analyze_image_regions, calculate_area_stats, generate_heatmap_data
from app.api.tubi import ANNOTATED_DIR, draw_annotated_image


settings = get_settings()
QUEUE_KEY_PENDING = "tubi:queue:pending"
QUEUE_KEY_PROCESSING = "tubi:queue:processing"


def get_redis():
    conn = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.5,
        retry_on_timeout=False
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
    try:
        db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
        if not db_analysis:
            return

        db_analysis.status = "analyzing"
        db.commit()

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

        result = analyze_with_timeout(filepath, width, height)
        if not result or not result.get("success", False):
            error_msg = result.get("error", "分析失败") if result else "分析失败"
            db_analysis.status = "error"
            db_analysis.analysis_note = error_msg
            db.commit()
            return

        regions = result.get("regions", {})

        try:
            area_stats = calculate_area_stats(regions, width, height)
        except Exception:
            area_stats = {
                "inscription_percent": 0.0,
                "painting_percent": 0.0,
                "blank_percent": 0.0
            }

        try:
            heatmap = generate_heatmap_data(regions, width, height)
        except Exception:
            heatmap = []

        try:
            position_analysis = analyze_inscription_position(regions, width, height)
        except Exception:
            position_analysis = {}

        annotated_filename = f"annotated_{image_id}.jpg"
        annotated_path = f"{ANNOTATED_DIR}/{annotated_filename}"
        annotated_image_path = None
        try:
            annotated_result = draw_annotated_image(filepath, regions, annotated_path)
            if annotated_result:
                annotated_image_path = normalize_path(annotated_result)
        except Exception:
            annotated_image_path = None

        db_analysis.regions = regions
        db_analysis.inscription_percent = area_stats.get("inscription_percent", 0.0)
        db_analysis.painting_percent = area_stats.get("painting_percent", 0.0)
        db_analysis.blank_percent = area_stats.get("blank_percent", 0.0)
        db_analysis.heatmap_data = heatmap
        db_analysis.position_analysis = position_analysis
        db_analysis.analysis_note = result.get("analysis_note", "")
        if annotated_image_path:
            db_analysis.annotated_image_path = annotated_image_path
        db_analysis.status = "analyzed"
        db.commit()
    except Exception as e:
        if db_analysis:
            try:
                db_analysis.status = "error"
                db_analysis.analysis_note = f"分析失败: {str(e)}"
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
            image_id = conn.brpoplpush(QUEUE_KEY_PENDING, QUEUE_KEY_PROCESSING, timeout=5)
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

