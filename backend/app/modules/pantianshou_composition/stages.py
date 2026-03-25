from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Tuple

import cv2

from app.core.config import get_settings
from app.modules.pantianshou_composition.analyzer import (
    compute_metrics,
    decode_image_bytes,
    make_basic_annotations,
    make_heatmap_png,
    to_feature_vector_512,
)
from app.modules.pantianshou_composition.composition_llm import generate_composition_narrative
from app.modules.pantianshou_composition.figure_assets import figure_image_path, figure_image_url
from app.modules.pantianshou_composition.pdf_generator import generate_simple_pdf
from app.modules.pantianshou_composition.qdrant_client import search_cases
from app.modules.pantianshou_composition.report_builder import build_report
from app.modules.pantianshou_composition.rule_matcher import select_rules
from app.modules.pantianshou_composition.storage import build_static_url, get_heatmap_path, get_pdf_path, get_report_json_path

settings = get_settings()


@dataclass
class CompositionContext:
    task_id: str
    job: Any
    bucket: str
    img_bgr: Any
    metrics: Any | None = None
    edges: Any | None = None
    work_gray: Any | None = None
    vector: List[float] | None = None
    issues: List[Dict[str, Any]] | None = None
    matched_rules: List[Dict[str, Any]] | None = None
    theory_basis: List[Dict[str, Any]] | None = None
    references: List[Dict[str, Any]] | None = None
    comparisons: List[Dict[str, Any]] | None = None
    checks: List[Dict[str, Any]] | None = None
    llm: Any | None = None
    heatmap_url: str | None = None
    report_json_path: str | None = None
    pdf_path: str | None = None


def load_job_image(job: Any) -> Any:
    with open(job.upload_path, "rb") as f:
        content = f.read()
    return decode_image_bytes(content)


def preprocess_image(ctx: CompositionContext) -> None:
    metrics, edges, work_gray = compute_metrics(ctx.img_bgr, bucket=ctx.bucket)
    ctx.metrics = metrics
    ctx.edges = edges
    ctx.work_gray = work_gray


def detect_placeholder() -> None:
    time.sleep(0.4)


def extract_feature_vector(ctx: CompositionContext) -> None:
    ctx.vector = to_feature_vector_512(ctx.img_bgr)


def _build_rules_payload(sel: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    issues = sel.get("issues") or []
    matched_rules: List[Dict[str, Any]] = []
    theory_basis: List[Dict[str, Any]] = []
    for rr in sel.get("rules") or []:
        ref_figs = rr.get("reference_figures") or []
        ref_images = []
        for fid in ref_figs[:6]:
            url = figure_image_url(str(fid))
            if url:
                ref_images.append({"figure_id": str(fid), "image_url": url})
        rel = float(rr.get("relevance") or 0.0)
        basis = {
            "rule_id": rr.get("rule_id") or "",
            "rule_name": rr.get("rule_name") or "",
            "category": rr.get("category") or "",
            "subcategory": rr.get("subcategory") or "",
            "condition": rr.get("condition") or "",
            "quantitative_standard": rr.get("quantitative_standard") or "",
            "weight": rr.get("weight"),
            "reference_figures": ref_figs,
            "source": "pan.md",
        }
        theory_basis.append(basis)
        matched_rules.append(
            {
                "rule_id": rr.get("rule_id") or "",
                "rule_name": rr.get("rule_name") or "",
                "category": rr.get("category") or "",
                "subcategory": rr.get("subcategory") or "",
                "condition": rr.get("condition") or "",
                "quantitative_standard": rr.get("quantitative_standard") or "",
                "weight": rr.get("weight"),
                "reference_figures": ref_figs,
                "reference_images": ref_images,
                "relevance": rel,
                "similarity": min(1.0, rel / 100.0) if rel > 0 else 0.0,
            }
        )
    return issues, matched_rules, theory_basis


def _build_references(case_hits: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    references: List[Dict[str, Any]] = []
    if case_hits:
        for hit in case_hits:
            payload = hit.get("payload") or {}
            figure_id = payload.get("figure_id") or payload.get("id") or ""
            figure_id = str(figure_id) if figure_id else ""
            image_url = payload.get("image_url") or (figure_image_url(figure_id) if figure_id else None)
            figure_type = payload.get("figure_type") or ""
            desc = str(payload.get("description") or "").strip()
            if not desc:
                if figure_type == "positive":
                    desc = "正例插图"
                elif figure_type == "negative":
                    desc = "反例插图"
                else:
                    desc = "（暂无图例描述）"
            references.append(
                {
                    "figure_id": figure_id,
                    "artist": payload.get("artist") or "潘天寿",
                    "work": payload.get("work") or (figure_id or "（相似案例）"),
                    "similarity": float(hit.get("score") or 0.0),
                    "description": desc,
                    "image_url": image_url,
                }
            )
    else:
        references.append(
            {
                "artist": "潘天寿",
                "work": "（参考案例）",
                "similarity": 0.0,
                "description": "第一版默认提供参考案例占位；接入案例库后将返回最相似的经典画作。",
            }
        )
    return references


def _build_comparisons(
    references: List[Dict[str, Any]],
    metrics: Any,
    bucket: str,
) -> List[Dict[str, Any]]:
    comparisons: List[Dict[str, Any]] = []
    for ref in references[:3]:
        fid = str(ref.get("figure_id") or "")
        if not fid:
            continue
        ref_path = figure_image_path(fid)
        if not ref_path or not os.path.exists(ref_path):
            continue
        try:
            ref_img = cv2.imread(ref_path)
            if ref_img is None:
                continue
            ref_metrics, _, _ = compute_metrics(ref_img, bucket=bucket)
        except Exception:
            continue
        blank_cur = int(round(metrics.blank_ratio * 100))
        blank_ref = int(round(ref_metrics.blank_ratio * 100))
        dom_cur = float(metrics.dominant_orientation_ratio)
        dom_ref = float(ref_metrics.dominant_orientation_ratio)
        dense_cur = float(metrics.edge_density_std)
        dense_ref = float(ref_metrics.edge_density_std)
        advice = []
        if blank_cur >= blank_ref + 10:
            advice.append("留白比参考案例更大，可用题款/印章或小物补实，让留白成形并形成呼应。")
        elif blank_cur <= blank_ref - 10:
            advice.append("留白比参考案例更少，可减少重复笔触与次要信息，留出透气空隙以强化主次。")
        if dom_cur >= dom_ref + 0.08:
            advice.append("主方向更集中，建议用横向支撑或斜向穿插打破单向直贯，形成承转。")
        if dense_cur <= dense_ref - 0.03:
            advice.append("疏密对比偏弱，建议密处更聚、疏处更透，让节奏对比更鲜明。")
        comparisons.append(
            {
                "figure_id": fid,
                "image_url": ref.get("image_url"),
                "similarity": ref.get("similarity"),
                "advice": advice,
                "differences": [
                    {"name": "留白比例", "current": blank_cur, "reference": blank_ref},
                    {"name": "主方向集中度", "current": dom_cur, "reference": dom_ref},
                    {"name": "疏密对比强度", "current": dense_cur, "reference": dense_ref},
                ],
            }
        )
    return comparisons


def _build_checks(metrics: Any) -> List[Dict[str, Any]]:
    blank_pct = int(round(metrics.blank_ratio * 100))
    x, y, w, h = metrics.inscription_box
    checks: List[Dict[str, Any]] = []
    checks.append({"name": "留白控制", "score": max(0, 10 - int(abs(blank_pct - 38) / 6)), "max": 10, "comment": f"留白约 {blank_pct}%"})
    checks.append(
        {
            "name": "破平行风险",
            "score": 10 if not metrics.parallel_warning else 6,
            "max": 10,
            "comment": "未见明显长线平行" if not metrics.parallel_warning else "存在平行趋势，需要破势",
        }
    )
    checks.append({"name": "疏密节奏", "score": max(0, min(10, int(metrics.edge_density_std / 0.012))), "max": 10, "comment": f"疏密对比强度 {metrics.edge_density_std:.3f}"})
    checks.append(
        {"name": "题款经营", "score": 10 if w > 0 and h > 0 else 7, "max": 10, "comment": "已检测到题款落点" if w > 0 and h > 0 else "建议结合留白重新寻找落点"}
    )
    return checks


def search_and_match(ctx: CompositionContext) -> None:
    case_hits = search_cases(ctx.vector or [], limit=5)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    pan_md_path = os.path.join(repo_root, "pan.md")
    sel = select_rules(pan_md_path, ctx.metrics, limit=12)

    issues, matched_rules, theory_basis = _build_rules_payload(sel)
    references = _build_references(case_hits)
    comparisons = _build_comparisons(references, ctx.metrics, bucket=ctx.bucket)
    checks = _build_checks(ctx.metrics)

    ctx.issues = issues
    ctx.matched_rules = matched_rules
    ctx.theory_basis = theory_basis
    ctx.references = references
    ctx.comparisons = comparisons
    ctx.checks = checks


def write_llm_narrative(ctx: CompositionContext) -> None:
    issues = ctx.issues or []
    references = ctx.references or []
    comparisons = ctx.comparisons or []
    theory_basis = ctx.theory_basis or []
    matched_rules = ctx.matched_rules or []
    metrics = ctx.metrics
    ctx.llm = generate_composition_narrative(
        image_path=ctx.job.upload_path,
        original_url=ctx.job.original_url,
        metrics={
            "留白感觉": "很大" if metrics.blank_ratio >= 0.25 else ("偏少" if metrics.blank_ratio <= 0.06 else "适中"),
            "疏密节奏": "偏平" if metrics.edge_density_std < 0.05 else "有对比",
            "主方向": "偏单一" if metrics.dominant_orientation_ratio >= 0.55 else "较丰富",
            "平行线风险": "存在" if metrics.parallel_warning else "不明显",
            "题跋落点": "需要重新经营" if metrics.inscription_box[2] <= 0 or metrics.inscription_box[3] <= 0 else "可进一步精调",
        },
        checks=[],
        issues=[{"提示": (it.get("hint") or it.get("title") or "").strip()} for it in issues if (it.get("hint") or it.get("title") or "").strip()],
        references=references[:3],
        comparisons=[
            {
                "image_url": c.get("image_url"),
                "差异提示": "对照参考图，留白/主方向/疏密三处差异见下图说明。",
                "建议摘要": ((c.get("advice") or [])[:2] if isinstance(c.get("advice"), list) else []),
            }
            for c in (comparisons[:2] if isinstance(comparisons, list) else [])
            if c.get("image_url")
        ],
        theory_basis=[
            {
                "rule_name": r.get("rule_name") or "",
                "category": r.get("category") or "",
                "subcategory": r.get("subcategory") or "",
                "condition": r.get("condition") or "",
                "quantitative_standard": r.get("quantitative_standard") or "",
            }
            for r in (theory_basis[:10] if isinstance(theory_basis, list) else [])
        ],
        example_images=(
            [
                {
                    "title": "对比参考示例",
                    "image_url": c.get("image_url"),
                    "note": ((c.get("advice") or [])[:1] or [""])[0],
                }
                for c in (comparisons[:2] if isinstance(comparisons, list) else [])
                if c.get("image_url")
            ]
            + [
                {
                    "title": "规则示例图",
                    "image_url": (r.get("reference_images") or [{}])[0].get("image_url"),
                    "note": (r.get("rule_name") or "").strip(),
                }
                for r in (matched_rules[:3] if isinstance(matched_rules, list) else [])
                if (r.get("reference_images") or [{}])[0].get("image_url")
            ]
        )[:8],
    )


def write_heatmap_and_get_url(task_id: str, edges: Any) -> Tuple[str, str]:
    heatmap_img = make_heatmap_png(edges)
    heatmap_path = get_heatmap_path(task_id)
    cv2.imwrite(heatmap_path, heatmap_img)
    base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
    rel_heat = os.path.relpath(heatmap_path, base_data_dir)
    heatmap_url = build_static_url(rel_heat)
    return heatmap_path, heatmap_url


def build_annotations(metrics: Any, edges: Any) -> Dict[str, Any]:
    annotations = make_basic_annotations(metrics)
    try:
        import numpy as np

        ys, xs = np.where(edges > 0)
        if xs.size > 0 and ys.size > 0:
            x0 = int(xs.min())
            x1 = int(xs.max())
            y0 = int(ys.min())
            y1 = int(ys.max())
            pad_x = int((x1 - x0) * 0.06) + 10
            pad_y = int((y1 - y0) * 0.06) + 10
            x0 = max(0, x0 - pad_x)
            y0 = max(0, y0 - pad_y)
            x1 = min(edges.shape[1] - 1, x1 + pad_x)
            y1 = min(edges.shape[0] - 1, y1 + pad_y)
            sx = float(metrics.width) / float(edges.shape[1])
            sy = float(metrics.height) / float(edges.shape[0])
            rx = int(round(x0 * sx))
            ry = int(round(y0 * sy))
            rw = int(round((x1 - x0) * sx))
            rh = int(round((y1 - y0) * sy))
            annotations["sketch_rects"] = [[rx, ry, max(1, rw), max(1, rh)]]
            cx = rx + rw // 2
            cy = ry + rh // 2
            annotations["sketch_lines"] = [[rx, cy, rx + rw, cy], [cx, ry, cx, ry + rh]]
        else:
            annotations["sketch_rects"] = []
            annotations["sketch_lines"] = []
    except Exception:
        annotations["sketch_rects"] = []
        annotations["sketch_lines"] = []
    return annotations


def write_report_and_pdf(ctx: CompositionContext) -> None:
    annotations = build_annotations(ctx.metrics, ctx.edges)
    _, heatmap_url = write_heatmap_and_get_url(ctx.task_id, ctx.edges)
    ctx.heatmap_url = heatmap_url

    report = build_report(
        task_id=ctx.task_id,
        metrics=ctx.metrics,
        annotations=annotations,
        original_url=ctx.job.original_url,
        heatmap_url=heatmap_url,
        references=ctx.references or [],
        matched_rules=ctx.matched_rules or [],
        issues=ctx.issues or [],
        comparisons=ctx.comparisons or [],
        checks=ctx.checks or [],
        theory_basis=ctx.theory_basis or [],
        llm=ctx.llm,
        ruleset_version=date.today().isoformat(),
        model_version="v1",
    )

    report_json_path = get_report_json_path(ctx.task_id)
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)

    pdf_path = get_pdf_path(ctx.task_id)
    pdf_bytes = generate_simple_pdf(
        title="Composition Report",
        lines=[
            f"Task: {ctx.task_id}",
            f"Score: {report['summary']['total_score']}/100",
            f"Grade: {report['summary']['grade']}",
        ],
    )
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    ctx.report_json_path = report_json_path
    ctx.pdf_path = pdf_path
