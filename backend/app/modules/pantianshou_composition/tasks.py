from __future__ import annotations

import json
import time

import os

from typing import Any, Dict

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.pantianshou_composition import eta
from app.modules.pantianshou_composition.models import CompositionJob
from app.modules.pantianshou_composition.pipeline import StageMaps, try_get_redis, run_stage
from app.modules.pantianshou_composition.progress import update_job
from app.modules.pantianshou_composition.stages import (
    CompositionContext,
    detect_placeholder,
    extract_feature_vector,
    load_job_image,
    preprocess_image,
    search_and_match,
    write_report_and_pdf,
    write_llm_narrative,
)
from app.modules.pantianshou_composition.knowledge_ingest import ingest_pan_md
from app.modules.pantianshou_composition.knowledge_ingest import ingest_illustration_images
from app.modules.pantianshou_composition.pdf_illustration_extractor import extract_pdf_images_to_data
from app.modules.pantianshou_composition.storage import build_static_url

settings = get_settings()


STAGE_TEXT = {
    "preprocess": "图像预处理",
    "detect": "目标检测与分割",
    "feature_extract": "线条提取与特征计算",
    "vector_search": "向量检索与规则匹配",
    "llm_narrative": "生成专业讲评",
    "report": "生成报告与标注",
}

STAGE_PROGRESS = {
    "queued": 0,
    "preprocess": 10,
    "detect": 30,
    "feature_extract": 50,
    "vector_search": 70,
    "llm_narrative": 82,
    "report": 90,
    "done": 100,
}


def _job(task_id: str) -> CompositionJob | None:
    db = SessionLocal()
    try:
        return db.query(CompositionJob).filter(CompositionJob.id == task_id).first()
    finally:
        db.close()


@celery_app.task(bind=True, name="composition.analyze")
def analyze_composition(self, task_id: str) -> None:
    job = _job(task_id)
    if not job:
        return
    if job.status in {"canceled", "deleted"}:
        return

    r = try_get_redis()
    started_at = time.time()
    width: int | None = None
    height: int | None = None
    bucket = "unknown"
    maps = StageMaps(text=STAGE_TEXT, progress=STAGE_PROGRESS)

    def _safe_error_message(e: Exception) -> str:
        msg = str(e or "")
        msg = msg.replace("\n", " ").strip()
        if not msg:
            return type(e).__name__
        if "Traceback" in msg or "/" in msg or "\\" in msg:
            return type(e).__name__
        return msg[:200]

    try:
        update_job(task_id, status="started", progress=0, stage="queued", stage_text="等待处理", message="")

        img = load_job_image(job)
        height, width = img.shape[:2]
        bucket = eta.megapixels_bucket(width, height)
        ctx = CompositionContext(task_id=task_id, job=job, bucket=bucket, img_bgr=img)

        def _preprocess() -> None:
            time.sleep(0.2)
            preprocess_image(ctx)

        run_stage(
            task_id=task_id,
            r=r,
            bucket=bucket,
            stage="preprocess",
            maps=maps,
            message="正在归一化与提取元数据",
            fn=_preprocess,
        )
        run_stage(
            task_id=task_id,
            r=r,
            bucket=bucket,
            stage="detect",
            maps=maps,
            message="正在分析物象与结构区",
            fn=detect_placeholder,
        )
        run_stage(
            task_id=task_id,
            r=r,
            bucket=bucket,
            stage="feature_extract",
            maps=maps,
            message="正在生成构图特征向量",
            fn=lambda: extract_feature_vector(ctx),
        )
        run_stage(
            task_id=task_id,
            r=r,
            bucket=bucket,
            stage="vector_search",
            maps=maps,
            message="正在检索匹配规则与案例",
            fn=lambda: search_and_match(ctx),
        )
        run_stage(
            task_id=task_id,
            r=r,
            bucket=bucket,
            stage="llm_narrative",
            maps=maps,
            message="正在生成更丰富的文字讲评",
            fn=lambda: write_llm_narrative(ctx),
        )
        run_stage(
            task_id=task_id,
            r=r,
            bucket=bucket,
            stage="report",
            maps=maps,
            message="正在生成报告、标注与 PDF",
            fn=lambda: write_report_and_pdf(ctx),
        )
        update_job(task_id, report_json_path=ctx.report_json_path, pdf_path=ctx.pdf_path, overlay_heatmap_url=ctx.heatmap_url)

        update_job(task_id, status="done", progress=100, stage="done", stage_text="完成", message="", eta_seconds=0, eta_confidence=0.85)
    except Exception as e:
        update_job(task_id, status="failed", stage="failed", stage_text="失败", message="", error_code="analysis_failed", error_message=_safe_error_message(e))
    finally:
        total = time.time() - started_at
        if width and height:
            bucket = eta.megapixels_bucket(width, height)
        if r:
            try:
                eta.update_expected_seconds(r, bucket, "total", total)
            except Exception:
                pass


@celery_app.task(bind=True, name="composition.ingest_pan_rules")
def ingest_pan_rules(self, pan_md_path: str, recreate: bool = False, ruleset_version: str | None = None) -> Dict[str, Any]:
    self.update_state(state="PROGRESS", meta={"progress": 10, "stage": "load", "message": "正在读取规则文件"})
    result = ingest_pan_md(pan_md_path, recreate=recreate, ruleset_version=ruleset_version)
    if not result.get("ok"):
        self.update_state(state="PROGRESS", meta={"progress": 100, "stage": "failed", "message": result.get("error") or "failed"})
        raise RuntimeError(result.get("error") or "failed")
    self.update_state(state="PROGRESS", meta={"progress": 100, "stage": "done", "message": "完成"})
    return result


@celery_app.task(bind=True, name="composition.ingest_illustrations")
def ingest_illustrations(self, images_dir: str, mapping_json: str | None = None, ruleset_version: str | None = None) -> Dict[str, Any]:
    self.update_state(state="PROGRESS", meta={"progress": 10, "stage": "load", "message": "正在读取图片"})
    result = ingest_illustration_images(images_dir, mapping_json=mapping_json, ruleset_version=ruleset_version, skip_unmapped=bool(mapping_json))
    if not result.get("ok"):
        self.update_state(state="PROGRESS", meta={"progress": 100, "stage": "failed", "message": result.get("error") or "failed"})
        raise RuntimeError(result.get("error") or "failed")
    self.update_state(state="PROGRESS", meta={"progress": 100, "stage": "done", "message": "完成"})
    return result


@celery_app.task(bind=True, name="composition.extract_pdf_illustrations")
def extract_pdf_illustrations(self, pdf_path: str, mapping_json: str | None = None, ruleset_version: str | None = None) -> Dict[str, Any]:
    self.update_state(state="PROGRESS", meta={"progress": 5, "stage": "extract", "message": "正在从 PDF 提取附图"})
    try:
        out_dir, imgs = extract_pdf_images_to_data(pdf_path)
    except Exception as e:
        self.update_state(state="PROGRESS", meta={"progress": 100, "stage": "failed", "message": str(e)})
        raise
    auto_mapping_path = None
    if not mapping_json:
        mapping = {}
        for it in imgs:
            if it.figure_id:
                mapping[it.file_name] = it.figure_id
        if mapping:
            auto_mapping_path = os.path.join(out_dir, "mapping.json")
            with open(auto_mapping_path, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
            mapping_json = auto_mapping_path
    mapping_json_url = None
    if mapping_json and os.path.exists(mapping_json):
        base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
        rel = os.path.relpath(mapping_json, base_data_dir)
        mapping_json_url = build_static_url(rel)
    self.update_state(state="PROGRESS", meta={"progress": 65, "stage": "ingest", "message": "正在将附图向量入库"})
    result = ingest_illustration_images(out_dir, mapping_json=mapping_json, ruleset_version=ruleset_version, skip_unmapped=True)
    if not result.get("ok"):
        self.update_state(state="PROGRESS", meta={"progress": 100, "stage": "failed", "message": result.get("error") or "failed"})
        raise RuntimeError(result.get("error") or "failed")
    self.update_state(state="PROGRESS", meta={"progress": 100, "stage": "done", "message": "完成"})
    return {
        "ok": True,
        "pdf_path": pdf_path,
        "extracted_dir": out_dir,
        "extracted_count": len(imgs),
        "sample_urls": [x.stored_url for x in imgs[:10]],
        "mapping_json_path": mapping_json,
        "mapping_json_url": mapping_json_url,
        "ingest": result,
    }
