from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.pantianshou_composition.models import CompositionJob

settings = get_settings()


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=False, socket_connect_timeout=0.2, socket_timeout=0.5)


def get_job(db: Session, task_id: str) -> CompositionJob | None:
    return db.query(CompositionJob).filter(CompositionJob.id == task_id).first()


def update_job(task_id: str, **fields: Any) -> None:
    db = SessionLocal()
    try:
        job = get_job(db, task_id)
        if not job:
            return
        for k, v in fields.items():
            if hasattr(job, k):
                setattr(job, k, v)
        job.updated_at = datetime.utcnow()
        db.add(job)
        db.commit()
    finally:
        db.close()

    try:
        r = get_redis()
        r.publish(f"composition:job:{task_id}".encode("utf-8"), b"1")
    except Exception:
        pass


def job_to_status_dict(job: CompositionJob) -> Dict[str, Any]:
    return {
        "task_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "stage_text": job.stage_text,
        "message": job.message or "",
        "eta_seconds": job.eta_seconds,
        "eta_confidence": job.eta_confidence,
        "queue_eta_seconds": job.queue_eta_seconds,
        "error_code": job.error_code,
        "error_message": job.error_message,
    }
