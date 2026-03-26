from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from threading import Thread
from typing import Generator

import redis
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.modules.pantianshou_composition.analyzer import decode_image_bytes
from app.modules.pantianshou_composition.eta import DEFAULT_EXPECTED_SECONDS, megapixels_bucket
from app.modules.pantianshou_composition.models import CompositionFeedback, CompositionJob
from app.modules.pantianshou_composition.progress import get_redis, job_to_status_dict, update_job
from app.modules.pantianshou_composition.schemas import (
    FeedbackRequest,
    IngestRulesRequest,
    IngestStartResponse,
    IngestTaskStatusResponse,
    KnowledgeUploadResponse,
    SimpleSuccessResponse,
    TaskHistoryResponse,
    TaskStatusResponse,
    UploadResponse,
)
from app.modules.pantianshou_composition.knowledge_storage import ensure_knowledge_dirs, extract_zip_if_needed, save_book_upload, save_ingest_files
from app.modules.pantianshou_composition.storage import read_upload_meta, save_upload_bytes, write_upload_meta
from app.modules.pantianshou_composition.tasks import analyze_composition, extract_pdf_illustrations, ingest_illustrations, ingest_pan_rules

settings = get_settings()

router = APIRouter(prefix="/composition", tags=["潘天寿教你构图"])


def _is_safe_path(path: str, base_dir: str) -> bool:
    try:
        base = os.path.realpath(base_dir)
        target = os.path.realpath(path)
        return os.path.commonpath([base, target]) == base
    except Exception:
        return False


def _require_api_key(request: Request) -> str | None:
    require = bool(getattr(settings, "COMPOSITION_REQUIRE_API_KEY", False)) or bool(getattr(settings, "COMPOSITION_API_KEY", ""))
    key = request.headers.get("X-API-Key")
    if require:
        if not key:
            raise HTTPException(status_code=401, detail="missing_api_key")
        if key != getattr(settings, "COMPOSITION_API_KEY", ""):
            raise HTTPException(status_code=403, detail="invalid_api_key")
    return key


def _client_id(request: Request, api_key: str | None) -> str:
    if api_key:
        return f"key:{api_key}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def _rate_limit(r: redis.Redis, scope: str, client: str, window_seconds: int, limit: int) -> None:
    now = int(time.time())
    window = (now // window_seconds) * window_seconds
    key = f"composition:rl:{scope}:{client}:{window}"
    try:
        n = r.incr(key)
        if n == 1:
            r.expire(key, window_seconds + 1)
        if n > limit:
            raise HTTPException(status_code=429, detail="rate_limited")
    except HTTPException:
        raise
    except Exception:
        return


def _estimate_queue_eta_seconds(db: Session, total_expected_seconds: float) -> int:
    queued = db.query(CompositionJob).filter(CompositionJob.status.in_(["queued", "started"])).count()
    return int(max(queued * total_expected_seconds, 0.0))


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


@router.post("/upload", response_model=UploadResponse)
async def upload(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    api_key = _require_api_key(request)
    r = get_redis()
    _rate_limit(r, "upload", _client_id(request, api_key), window_seconds=60, limit=10)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file_too_large")

    try:
        img = decode_image_bytes(content)
        h, w = img.shape[:2]
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_image")

    task_id = uuid.uuid4().hex
    upload_path, original_url = save_upload_bytes(task_id, file.filename or "upload.png", content)
    write_upload_meta(task_id, file.filename or "upload.png")

    bucket = megapixels_bucket(w, h)
    expected_total = float(sum(DEFAULT_EXPECTED_SECONDS.values()))
    queue_eta = _estimate_queue_eta_seconds(db, expected_total)

    job = CompositionJob(
        id=task_id,
        status="queued",
        progress=0,
        stage="queued",
        stage_text="等待处理",
        message="",
        upload_path=upload_path,
        original_url=original_url,
        queue_eta_seconds=queue_eta,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()

    def enqueue() -> None:
        try:
            r0 = get_redis()
            r0.ping()
            task = analyze_composition.delay(task_id)
            update_job(task_id, celery_task_id=task.id)
        except Exception:
            Thread(target=lambda: analyze_composition.apply(args=[task_id]), daemon=True).start()

    Thread(target=enqueue, daemon=True).start()

    return UploadResponse(
        task_id=task_id,
        status="queued",
        status_url=f"/api/v1/composition/task/{task_id}",
        file_name=file.filename or "upload.png",
    )


@router.get("/history", response_model=TaskHistoryResponse)
def history(request: Request, limit: int = 30, db: Session = Depends(get_db)):
    _require_api_key(request)
    limit = max(1, min(int(limit or 30), 100))
    items = db.query(CompositionJob).order_by(CompositionJob.created_at.desc()).limit(limit).all()
    out = []
    for it in items:
        report_url = f"/api/v1/composition/report/{it.id}" if it.report_json_path else None
        pdf_url = f"/api/v1/composition/report/{it.id}/pdf" if it.pdf_path else None
        file_name = read_upload_meta(it.id)
        out.append(
            {
                "task_id": it.id,
                "status": it.status,
                "created_at": it.created_at.isoformat(),
                "original_url": it.original_url,
                "status_url": f"/api/v1/composition/task/{it.id}",
                "report_url": report_url,
                "pdf_url": pdf_url,
                "file_name": file_name,
            }
        )
    return {"items": out}


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
def get_task(task_id: str, request: Request, db: Session = Depends(get_db)):
    api_key = _require_api_key(request)
    r = get_redis()
    _rate_limit(r, "query", _client_id(request, api_key), window_seconds=10, limit=30)

    job = db.query(CompositionJob).filter(CompositionJob.id == task_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="task_not_found")
    return TaskStatusResponse(**job_to_status_dict(job))


@router.get("/task/{task_id}/events")
def task_events(task_id: str, request: Request):
    api_key = _require_api_key(request)
    r = get_redis()
    _rate_limit(r, "query", _client_id(request, api_key), window_seconds=10, limit=30)

    def gen() -> Generator[bytes, None, None]:
        last_updated = None

        r_sub = None
        pubsub = None
        try:
            r_sub = get_redis()
            r_sub.ping()
            pubsub = r_sub.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(f"composition:job:{task_id}".encode("utf-8"))
        except Exception:
            pubsub = None

        while True:
            db = SessionLocal()
            try:
                job = db.query(CompositionJob).filter(CompositionJob.id == task_id).first()
            finally:
                db.close()
            if not job:
                yield b"event: progress\ndata: {\"status\":\"failed\",\"error_message\":\"task_not_found\"}\n\n"
                return

            updated = job.updated_at.timestamp() if job.updated_at else 0
            if last_updated is None or updated != last_updated:
                payload = json.dumps(job_to_status_dict(job), ensure_ascii=False)
                yield f"event: progress\ndata: {payload}\n\n".encode("utf-8")
                last_updated = updated

            if job.status in {"done", "failed", "canceled", "deleted"}:
                return

            if pubsub is not None:
                try:
                    pubsub.get_message(timeout=0.8)
                except Exception:
                    time.sleep(0.8)
            else:
                time.sleep(0.8)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/report/{task_id}")
def get_report(task_id: str, request: Request, db: Session = Depends(get_db)):
    api_key = _require_api_key(request)
    r = get_redis()
    _rate_limit(r, "query", _client_id(request, api_key), window_seconds=10, limit=30)

    job = db.query(CompositionJob).filter(CompositionJob.id == task_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="task_not_found")
    if job.status != "done" or not job.report_json_path:
        raise HTTPException(status_code=409, detail="report_not_ready")
    if not _is_safe_path(job.report_json_path, os.path.dirname(settings.UPLOAD_DIR)):
        raise HTTPException(status_code=400, detail="invalid_report_path")
    if not os.path.exists(job.report_json_path):
        raise HTTPException(status_code=404, detail="report_missing")
    with open(job.report_json_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/report/{task_id}/pdf")
def download_pdf(task_id: str, request: Request, db: Session = Depends(get_db)):
    api_key = _require_api_key(request)
    r = get_redis()
    _rate_limit(r, "query", _client_id(request, api_key), window_seconds=10, limit=30)
    job = db.query(CompositionJob).filter(CompositionJob.id == task_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="task_not_found")
    if job.status != "done" or not job.pdf_path:
        raise HTTPException(status_code=409, detail="pdf_not_ready")
    if not _is_safe_path(job.pdf_path, os.path.dirname(settings.UPLOAD_DIR)):
        raise HTTPException(status_code=400, detail="invalid_pdf_path")
    if not os.path.exists(job.pdf_path):
        raise HTTPException(status_code=409, detail="pdf_not_ready")
    return FileResponse(job.pdf_path, media_type="application/pdf", filename=f"composition_{task_id}.pdf")


@router.post("/task/{task_id}/cancel", response_model=SimpleSuccessResponse)
def cancel_task(task_id: str, request: Request, db: Session = Depends(get_db)):
    _require_api_key(request)
    job = db.query(CompositionJob).filter(CompositionJob.id == task_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="task_not_found")
    if job.status in {"done", "failed", "canceled", "deleted"}:
        return SimpleSuccessResponse(success=True)
    if job.celery_task_id:
        try:
            celery_app.control.revoke(job.celery_task_id, terminate=False)
        except Exception:
            pass
    job.status = "canceled"
    job.stage = "canceled"
    job.stage_text = "已取消"
    job.message = ""
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()
    return SimpleSuccessResponse(success=True)


@router.delete("/task/{task_id}", response_model=SimpleSuccessResponse)
def delete_task(task_id: str, request: Request, db: Session = Depends(get_db)):
    _require_api_key(request)
    job = db.query(CompositionJob).filter(CompositionJob.id == task_id).first()
    if not job:
        return SimpleSuccessResponse(success=True)
    paths = [job.upload_path, job.report_json_path, job.pdf_path]
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    db.delete(job)
    db.commit()
    return SimpleSuccessResponse(success=True)


@router.post("/feedback", response_model=SimpleSuccessResponse)
def feedback(payload: FeedbackRequest, request: Request, db: Session = Depends(get_db)):
    api_key = _require_api_key(request)
    r = get_redis()
    _rate_limit(r, "feedback", _client_id(request, api_key), window_seconds=60, limit=30)

    fb = CompositionFeedback(
        task_id=payload.task_id,
        rating=payload.rating,
        comments=payload.comments or "",
        client_id=_client_id(request, api_key),
        created_at=datetime.utcnow(),
    )
    db.add(fb)
    db.commit()
    return SimpleSuccessResponse(success=True)


@router.post("/knowledge/ingest/rules", response_model=IngestStartResponse)
def ingest_rules(payload: IngestRulesRequest, request: Request):
    _require_api_key(request)
    pan_md_path = (payload.pan_md_path or "pan.md").strip()
    if not os.path.isabs(pan_md_path):
        pan_md_path = os.path.join(_repo_root(), pan_md_path)
    pan_md_path = os.path.abspath(pan_md_path)
    ruleset_version = (payload.ruleset_version or "").strip() or None
    task = ingest_pan_rules.delay(pan_md_path, bool(payload.recreate), ruleset_version)
    return IngestStartResponse(task_id=task.id, status="queued", status_url=f"/api/v1/composition/knowledge/task/{task.id}")


@router.post("/knowledge/upload/book", response_model=KnowledgeUploadResponse)
async def upload_book(request: Request, file: UploadFile = File(...)):
    _require_api_key(request)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file_too_large")
    stored_path, stored_url = save_book_upload(file.filename or "book.pdf", content)
    return KnowledgeUploadResponse(file_name=file.filename or "book.pdf", stored_url=stored_url, stored_path=stored_path)


@router.post("/knowledge/ingest/images", response_model=IngestStartResponse)
async def ingest_images(
    request: Request,
    files: list[UploadFile] = File(...),
    mapping: UploadFile | None = File(None),
    ruleset_version: str = Form(""),
):
    _require_api_key(request)
    if not files:
        raise HTTPException(status_code=400, detail="empty_file")
    pairs = []
    for f in files:
        content = await f.read()
        if not content:
            continue
        pairs.append((f.filename or uuid.uuid4().hex, content))
    mapping_path = None
    if mapping is not None:
        mapping_bytes = await mapping.read()
        if mapping_bytes:
            pairs.append((mapping.filename or "mapping.json", mapping_bytes))
    _, batch_dir = save_ingest_files(pairs)
    if mapping is not None and mapping.filename:
        mapping_guess = os.path.join(batch_dir, os.path.basename(mapping.filename))
        if os.path.exists(mapping_guess):
            mapping_path = mapping_guess
    images_dir = extract_zip_if_needed(batch_dir)
    rv = (ruleset_version or "").strip() or None
    task = ingest_illustrations.delay(images_dir, mapping_path, rv)
    return IngestStartResponse(task_id=task.id, status="queued", status_url=f"/api/v1/composition/knowledge/task/{task.id}")


@router.post("/knowledge/ingest/book/pdf", response_model=IngestStartResponse)
async def ingest_book_pdf(
    request: Request,
    pdf_path: str = Form(""),
    mapping: UploadFile | None = File(None),
    ruleset_version: str = Form(""),
):
    _require_api_key(request)
    pdf_path = (pdf_path or "").strip()
    if not pdf_path:
        raise HTTPException(status_code=400, detail="missing_pdf_path")
    pdf_path = os.path.abspath(pdf_path)
    dirs = ensure_knowledge_dirs()
    allowed = os.path.abspath(dirs["books_dir"])
    if not pdf_path.startswith(allowed + os.sep) and pdf_path != allowed:
        raise HTTPException(status_code=400, detail="invalid_pdf_path")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="pdf_not_found")

    mapping_path = None
    if mapping is not None:
        mapping_bytes = await mapping.read()
        if mapping_bytes:
            _, batch_dir = save_ingest_files([(mapping.filename or "mapping.json", mapping_bytes)])
            mapping_guess = os.path.join(batch_dir, os.path.basename(mapping.filename or "mapping.json"))
            if os.path.exists(mapping_guess):
                mapping_path = mapping_guess

    rv = (ruleset_version or "").strip() or None
    task = extract_pdf_illustrations.delay(pdf_path, mapping_path, rv)
    return IngestStartResponse(task_id=task.id, status="queued", status_url=f"/api/v1/composition/knowledge/task/{task.id}")


@router.get("/knowledge/task/{task_id}", response_model=IngestTaskStatusResponse)
def ingest_task_status(task_id: str, request: Request):
    _require_api_key(request)
    try:
        res = celery_app.AsyncResult(task_id)
        state = res.state or ""
        if state == "PENDING":
            return IngestTaskStatusResponse(task_id=task_id, status="queued", progress=0, stage="queued", message="等待处理")
        if state == "PROGRESS":
            info = res.info if isinstance(res.info, dict) else {}
            return IngestTaskStatusResponse(
                task_id=task_id,
                status="running",
                progress=int(info.get("progress") or 0),
                stage=str(info.get("stage") or "running"),
                message=str(info.get("message") or ""),
            )
        if state == "SUCCESS":
            result = None
            try:
                result = res.result
            except Exception:
                result = None
            return IngestTaskStatusResponse(task_id=task_id, status="done", progress=100, stage="done", message="完成", result=result)
        err = ""
        try:
            err = str(res.info) if res.info else ""
        except Exception:
            err = ""
        return IngestTaskStatusResponse(task_id=task_id, status="failed", progress=100, stage="failed", message="", error_message=err or "failed")
    except Exception as e:
        return IngestTaskStatusResponse(task_id=task_id, status="failed", progress=100, stage="failed", message="", error_message=str(e) or "failed")
