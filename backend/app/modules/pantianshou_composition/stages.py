from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from app.core.config import get_settings
from app.modules.pantianshou_composition.analyzer import (
    compute_metrics,
    decode_image_bytes,
    make_basic_annotations,
    make_heatmap_png,
    to_feature_vector_1024,
)
from app.modules.pantianshou_composition.composition_cv import compute_advanced_metrics
from app.modules.pantianshou_composition.composition_llm import generate_composition_narrative, extract_qczh_coords
from app.modules.pantianshou_composition.figure_assets import figure_image_path, figure_image_url, figure_image_url_from_qdrant
from app.modules.pantianshou_composition.pdf_generator import generate_rich_pdf
from app.modules.pantianshou_composition.qdrant_client import search_cases
from app.modules.pantianshou_composition.report_builder import build_report, build_dimension_scores
from app.modules.pantianshou_composition.rule_matcher import select_rules
from app.modules.pantianshou_composition.storage import build_static_url, get_heatmap_path, get_pdf_path, get_report_json_path, read_upload_meta, to_abs_path

logger = logging.getLogger(__name__)
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
    bw_mask: Any | None = None
    advanced_metrics: Any | None = None
    vector: List[float] | None = None
    issues: List[Dict[str, Any]] | None = None
    matched_rules: List[Dict[str, Any]] | None = None
    theory_basis: List[Dict[str, Any]] | None = None
    references: List[Dict[str, Any]] | None = None
    comparisons: List[Dict[str, Any]] | None = None
    checks: List[Dict[str, Any]] | None = None
    llm: Any | None = None
    arrow_analysis: Dict[str, Any] | None = None
    arrow_overlay_url: str | None = None
    heatmap_url: str | None = None
    report_json_path: str | None = None
    pdf_path: str | None = None


def load_job_image(job: Any) -> Any:
    abs_path = to_abs_path(job.upload_path)
    with open(abs_path, "rb") as f:
        content = f.read()
    return decode_image_bytes(content)


def preprocess_image(ctx: CompositionContext) -> None:
    metrics, edges, work_gray = compute_metrics(ctx.img_bgr, bucket=ctx.bucket)
    ctx.metrics = metrics
    ctx.edges = edges
    ctx.work_gray = work_gray
    # Compute binary mask for advanced CV analysis
    gray = cv2.cvtColor(ctx.img_bgr, cv2.COLOR_BGR2GRAY)
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ctx.bw_mask = bw
    ctx.advanced_metrics = compute_advanced_metrics(bw, edges)


def detect_placeholder() -> None:
    time.sleep(0.4)


def extract_feature_vector(ctx: CompositionContext) -> None:
    ctx.vector = to_feature_vector_1024(to_abs_path(ctx.job.upload_path))


def _build_rules_payload(sel: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    issues = sel.get("issues") or []
    matched_rules: List[Dict[str, Any]] = []
    theory_basis: List[Dict[str, Any]] = []
    for rr in sel.get("rules") or []:
        ref_figs = rr.get("reference_figures") or []
        ref_images = []
        # Determine source based on rule_id prefix
        rule_id = rr.get("rule_id") or ""
        rule_source = "panplus.md" if any(rule_id.startswith(p) for p in ("JH-", "CC-", "BJ-")) else "pan.md"
        # For panplus rules, use bird_flower=True to search bird_flower_tutorial images
        # For pan.md rules, use the default pan.md image cache
        is_bird_flower = (rule_source == "panplus.md")
        for fid in ref_figs[:6]:
            url = figure_image_url(str(fid), bird_flower=is_bird_flower)
            if not url:
                url = figure_image_url_from_qdrant(str(fid))
            if url:
                ref_images.append({"figure_id": str(fid), "image_url": url})
        rel = float(rr.get("relevance") or 0.0)
        basis = {
            "rule_id": rule_id,
            "rule_name": rr.get("rule_name") or "",
            "category": rr.get("category") or "",
            "subcategory": rr.get("subcategory") or "",
            "condition": rr.get("condition") or "",
            "quantitative_standard": rr.get("quantitative_standard") or "",
            "weight": rr.get("weight"),
            "reference_figures": ref_figs,
            "source": rule_source,
        }
        theory_basis.append(basis)
        matched_rules.append(
            {
                "rule_id": rule_id,
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
                "source": rule_source,
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
            artist = payload.get("artist") or payload.get("artwork_artist")
            artwork_title = payload.get("artwork_title") or payload.get("work")
            desc = str(payload.get("description") or "").strip()

            # 构建显示文本
            if not desc:
                if figure_type == "positive":
                    desc = "正例插图"
                elif figure_type == "negative":
                    desc = "反例插图"
                elif figure_type == "technique":
                    desc = "技法示意图"
                elif figure_type == "artwork" and artist and artwork_title:
                    desc = f"{artist}《{artwork_title}》"
                else:
                    desc = figure_id or "（相似案例）"

            # 如果没有 artist，使用描述作为 work
            if not artist:
                work = desc
                artist = ""
            else:
                work = artwork_title or figure_id or "（相似案例）"

            references.append(
                {
                    "figure_id": figure_id,
                    "artist": artist,
                    "work": work,
                    "similarity": float(hit.get("score") or 0.0),
                    "description": desc,
                    "image_url": image_url,
                    "figure_type": figure_type,
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
    # 留白控制：中国画留白 30-70% 都是合理的，给更宽的范围
    if 30 <= blank_pct <= 70:
        blank_score = 9
    elif 20 <= blank_pct < 30 or 70 < blank_pct <= 80:
        blank_score = 7
    elif blank_pct < 20:
        blank_score = 5
    else:
        blank_score = 5
    checks.append({"name": "留白控制", "score": blank_score, "max": 10, "comment": f"留白约 {blank_pct}%"})
    checks.append(
        {
            "name": "破平行风险",
            "score": 9 if not metrics.parallel_warning else 7,
            "max": 10,
            "comment": "线条方向丰富，无明显平行" if not metrics.parallel_warning else "局部线条有趋同趋势，可穿插变化",
        }
    )
    checks.append({"name": "疏密节奏", "score": max(4, min(10, int(metrics.edge_density_std / 0.010) + 4)), "max": 10, "comment": f"疏密对比强度 {metrics.edge_density_std:.3f}"})
    checks.append(
        {"name": "题款经营", "score": 9 if w > 0 and h > 0 else 7, "max": 10, "comment": "已检测到题款落点" if w > 0 and h > 0 else "题款布局可在留白处经营"}
    )
    return checks


def search_and_match(ctx: CompositionContext) -> None:
    case_hits = search_cases(ctx.vector or [], limit=5)

    # 优先从数据库加载规则（pan.md/panplus.md 已迁移到 CompositionRule 表）
    sel = select_rules(metrics=ctx.metrics, adv=ctx.advanced_metrics, limit=12)

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


def analyze_arrow_flow(ctx: CompositionContext) -> None:
    pass


def draw_qczh_from_llm(ctx: CompositionContext) -> None:
    llm_result = ctx.llm or {}
    llm_text = llm_result.get("text") or ""
    if not llm_text:
        return
    coords = extract_qczh_coords(llm_text)
    if not coords:
        logger.warning("Arrow draw: no qczh coords found in LLM output for %s", ctx.task_id)
        return
    try:
        qi = coords.get("qi") or {}
        cheng = coords.get("cheng") or {}
        zhuan = coords.get("zhuan") or {}
        he = coords.get("he") or {}
        img_h, img_w = ctx.img_bgr.shape[:2]
        qi_pt = (int(qi["x"] * img_w / 100), int(qi["y"] * img_h / 100))
        cheng_pt = (int(cheng["x"] * img_w / 100), int(cheng["y"] * img_h / 100))
        zhuan_pt = (int(zhuan["x"] * img_w / 100), int(zhuan["y"] * img_h / 100))
        he_pt = (int(he["x"] * img_w / 100), int(he["y"] * img_h / 100))
        labels = [
            qi.get("label") or "起",
            cheng.get("label") or "承",
            zhuan.get("label") or "转",
            he.get("label") or "合",
        ]
        arrows = [
            (qi_pt[0], qi_pt[1], cheng_pt[0], cheng_pt[1]),
            (cheng_pt[0], cheng_pt[1], zhuan_pt[0], zhuan_pt[1]),
            (zhuan_pt[0], zhuan_pt[1], he_pt[0], he_pt[1]),
        ]
        from app.modules.pantianshou_composition.qichengzhuanhe import draw_arrows_on_lineart
        from app.modules.pantianshou_composition.storage import get_arrow_overlay_path, ensure_composition_dirs, build_static_url, THUMBNAIL_SIZE
        arrow_canvas = draw_arrows_on_lineart(ctx.img_bgr, arrows, labels)
        arrow_path = get_arrow_overlay_path(ctx.task_id)
        cv2.imwrite(arrow_path, arrow_canvas)
        dirs = ensure_composition_dirs()
        arrow_thumb_path = os.path.join(dirs["thumbs_dir"], f"{ctx.task_id}_arrow.jpg")
        h, w = arrow_canvas.shape[:2]
        if w > h:
            new_w, new_h = THUMBNAIL_SIZE, int(h * THUMBNAIL_SIZE / w)
        else:
            new_h, new_w = THUMBNAIL_SIZE, int(w * THUMBNAIL_SIZE / h)
        cv2.imwrite(arrow_thumb_path, cv2.resize(arrow_canvas, (new_w, new_h), interpolation=cv2.INTER_AREA),
                     [cv2.IMWRITE_JPEG_QUALITY, 80])
        base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
        rel_arrow = os.path.relpath(arrow_path, base_data_dir)
        rel_thumb = os.path.relpath(arrow_thumb_path, base_data_dir)
        ctx.arrow_overlay_url = build_static_url(rel_arrow)
        ctx.arrow_analysis = {
            "arrows": arrows,
            "arrow_labels": labels,
            "path_type": coords.get("path_shape", "之字形"),
            "llm_analysis": "",
            "thumb_url": build_static_url(rel_thumb),
        }
        logger.info("Arrow draw from LLM: %s path=%s", ctx.task_id, coords.get("path_shape"))
    except Exception as e:
        logger.warning("Arrow draw failed for %s: %s", ctx.task_id, e, exc_info=True)


def _fetch_knowledge_context(matched_rules: List[Dict[str, Any]]) -> List[str]:
    try:
        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        from app.modules.pantianshou_composition import qdrant_client as qc

        terms = set()
        for r in (matched_rules or [])[:8]:
            for k in ("rule_name", "category", "subcategory"):
                v = (r.get(k) or "").strip()
                if v:
                    terms.add(v)
        if not terms:
            return []
        search_query = "。".join(sorted(terms))
        service = EmbeddingService()
        emb_result = service.embed_text_sync(search_query)
        if not emb_result or not emb_result.embedding:
            return []
        hits = qc.search_collection(
            qc.KNOWLEDGE_TEXTS_COLLECTION,
            emb_result.embedding,
            limit=5,
        )
        chunks = [h.get("payload", {}).get("content", "") for h in (hits or [])]
        logger = __import__("logging").getLogger(__name__)
        logger.info("知识库原文搜索: query_terms=%d, hits=%d", len(terms), len(chunks))
        return [c for c in chunks if c]
    except Exception:
        return []


def write_llm_narrative(ctx: CompositionContext) -> None:
    """调用 LLM 生成构图分析讲评，结果存入 ctx.llm。"""
    issues = ctx.issues or []
    references = ctx.references or []
    comparisons = ctx.comparisons or []
    theory_basis = ctx.theory_basis or []
    matched_rules = ctx.matched_rules or []
    metrics = ctx.metrics

    # ---- 搜索知识库原文（潘天寿+花鸟教程），注入 LLM prompt 增强讲评权威性 ----
    context_knowledge = _fetch_knowledge_context(matched_rules)

    # Pre-compute dimension scores so LLM uses real scores in its table
    _total, _dims = build_dimension_scores(metrics, adv=ctx.advanced_metrics)
    dim_scores_payload = {"total_score": _total, "dimensions": _dims}

    ctx.llm = generate_composition_narrative(
        image_path=to_abs_path(ctx.job.upload_path),
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
        example_images=[
            {
                "title": (r.get("rule_name") or "规则示例").strip(),
                "image_url": (r.get("reference_images") or [{}])[0].get("image_url"),
                "caption": (r.get("condition") or "").strip(),
                "note": f"{r.get('category', '')} · {r.get('rule_name', '')}".strip(" ·"),
            }
            for r in (matched_rules[:8] if isinstance(matched_rules, list) else [])
            if (r.get("reference_images") or [{}])[0].get("image_url")
        ][:5],
        dimension_scores=dim_scores_payload,
        context_knowledge=context_knowledge,
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
    annotations = make_basic_annotations(metrics, edges=edges)
    # sketch_rects and sketch_lines are no longer rendered on the frontend
    # (they interfered with the 起承转合 arrows). Keep the data empty.
    annotations["sketch_rects"] = []
    annotations["sketch_lines"] = []
    return annotations


def write_report_and_pdf(ctx: CompositionContext) -> None:
    annotations = build_annotations(ctx.metrics, ctx.edges)
    _, heatmap_url = write_heatmap_and_get_url(ctx.task_id, ctx.edges)
    ctx.heatmap_url = heatmap_url

    # Ensure original_url is populated
    original_url = ctx.job.original_url or ""
    if not original_url and ctx.job.upload_path:
        # upload_path 已经是相对路径（相对于 data 目录），直接使用
        if os.path.isabs(ctx.job.upload_path):
            base_data = os.path.dirname(settings.UPLOAD_DIR)
            rel = os.path.relpath(ctx.job.upload_path, base_data)
        else:
            rel = ctx.job.upload_path
        original_url = build_static_url(rel)
    
    # 读取缩略图URL
    _, thumb_url = read_upload_meta(ctx.task_id)

    report = build_report(
        task_id=ctx.task_id,
        metrics=ctx.metrics,
        annotations=annotations,
        original_url=original_url,
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
        adv=ctx.advanced_metrics,
        arrow_analysis=ctx.arrow_analysis,
        arrow_overlay_url=ctx.arrow_overlay_url,
        thumb_url=thumb_url,
    )

    report_json_path = get_report_json_path(ctx.task_id)
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)

    pdf_path = get_pdf_path(ctx.task_id)
    try:
        pdf_bytes = generate_rich_pdf(
            task_id=ctx.task_id,
            report=report,
            original_image_path=to_abs_path(ctx.job.upload_path),
        )
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Rich PDF generation failed, falling back to simple PDF: %s", e)
        from app.modules.pantianshou_composition.pdf_generator import generate_simple_pdf
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
