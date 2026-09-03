"""
独立题跋分析 Worker 进程（v2.0 §2.3）。

背景：此前 Worker 线程嵌入在 uvicorn 进程内（main.py），CV/LLM 重任务与 API
争抢资源，worker 崩溃会带崩 web。本入口将其拆为独立进程：
    python -m app.worker_main        # 或 compose 独立 service

开关约定：
- 服务器：.env 设 TIBA_EMBEDDED_WORKER=false，由本进程消费 tubi_jobs 队列
- 本地开发：默认 TIBA_EMBEDDED_WORKER 未设置 = true，main.py 内嵌线程照常工作
"""
import logging
import os
import signal
import sys
import threading
import time

from contextlib import asynccontextmanager

# 与 web 进程相同：导入 app.main 以复用建表/迁移/模型注册
# （幂等：CREATE TABLE IF NOT EXISTS / 幂等迁移）
from app.core.database import engine, Base, run_migrations  # noqa: E402
from sqlalchemy import text  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tiba-worker-standalone")

_stop_event = threading.Event()


def _handle_signal(signum, frame):
    logger.info(f"收到信号 {signum}，正在停止…")
    _stop_event.set()


def _recover_stale_jobs():
    from app.core.database import SessionLocal
    from datetime import datetime, timedelta
    db = SessionLocal()
    try:
        cutoff = (datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(text(
            "UPDATE tubi_jobs SET status='queued', last_error='recovered' "
            "WHERE status='processing' AND updated_at < :cutoff"), {"cutoff": cutoff})
        db.execute(text(
            "UPDATE tubi_analyses SET status='uploaded' "
            "WHERE status='analyzing' AND updated_at < :cutoff"), {"cutoff": cutoff})
        db.commit()
        logger.info("已恢复卡住任务（如有）")
    except Exception as e:
        logger.warning(f"恢复任务失败: {e}")
    finally:
        db.close()


def _loop():
    from app.core.database import SessionLocal
    from app.models.tiba_job import TibaJob

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _recover_stale_jobs()

    while not _stop_event.is_set():
        db = SessionLocal()
        image_id = None
        try:
            job = db.query(TibaJob).filter(TibaJob.status == "queued").order_by(
                TibaJob.created_at.asc()).first()
            if not job:
                _stop_event.wait(2)
                continue
            image_id = job.image_id
            job.status = "processing"
            db.commit()
        except Exception as e:
            logger.error(f"取任务失败: {e}")
            _stop_event.wait(3)
            continue
        finally:
            db.close()

        if not image_id:
            continue

        try:
            from tiba_worker import process_one
            process_one(None, image_id)
        except Exception as e:
            logger.error(f"处理失败 {image_id}: {e}")

    logger.info("独立 Worker 已停止")


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # 必须先导入 models 注册表再 create_all（否则 metadata 为空，全新库缺表）
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    run_migrations()
    _loop()


if __name__ == "__main__":
    main()
