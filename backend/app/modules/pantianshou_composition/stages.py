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


def _pipeline_log(msg: str) -> None:
    import datetime
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "pipeline.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except Exception:
        pass

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
    n_with_images = sum(1 for r in (matched_rules or []) if r.get("reference_images"))
    _pipeline_log(f"[search] rules={len(matched_rules or [])}, with_ref_figs={sum(1 for r in (matched_rules or []) if r.get('reference_figures'))}, with_images={n_with_images}")
    if matched_rules:
        for r in matched_rules[:3]:
            refs = r.get("reference_figures", [])
            imgs = r.get("reference_images", [])
            _pipeline_log(f"  rule={r.get('rule_id')} refs={refs[:2]} imgs={[i.get('image_url','')[:50] for i in imgs]}")
    references = _build_references(case_hits)
    _pipeline_log(f"[search] case_hits={len(case_hits or [])}")
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


def _extract_qczh_from_glm(img_bgr) -> dict | None:
    """使用 GLM-5V-Turbo 独立提取起承转合四点坐标（视觉定位更准）。"""
    import base64, time, httpx
    import cv2
    try:
        if not (settings.ZHIPU_ENABLED and settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL):
            return None
    except Exception:
        return None
    # resize to reasonable size for API
    h, w = img_bgr.shape[:2]
    max_dim = 1280
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img_small = cv2.resize(img_bgr, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
    else:
        img_small = img_bgr
    _, buf = cv2.imencode('.jpg', img_small, [cv2.IMWRITE_JPEG_QUALITY, 75])
    b64 = base64.b64encode(buf).decode()
    kb = len(b64) / 1024
    _pipeline_log(f"GLM image encoded: {kb:.0f} KB base64")
    model = (settings.ZHIPU_MODEL or "").strip() or "glm-5v-turbo"
    base = (settings.ZHIPU_BASE_URL or "").rstrip("/")
    if base.endswith("/chat/completions"):
        url = base
    else:
        url = f"{base}/chat/completions"
    prompt = (
        "你是中国画构图专家。请在画面上标注起承转合四个关键位置（百分比坐标，x∈[0,100], y∈[0,100]，原点左上角）。\n"
        "注意：你的左手边是「左」，右手边是「右」。请仔细确认画材实际位置再给出坐标。\n"
        "- 起(qi)：画面主要势能起点，在画面边缘附近\n"
        "- 承(cheng)：势能承接发展的中间节点\n"
        "- 转(zhuan)：势能转折变化处\n"
        "- 合(he)：势能收束终点，通常靠近题款或视觉终点\n"
        "path_shape 从「之字形/对角线/三角形/回环/上升」中选择。\n"
        "只返回 JSON，不要任何解释：\n"
        '{"qi":{"x":数字,"y":数字},"cheng":{"x":数字,"y":数字},"zhuan":{"x":数字,"y":数字},"he":{"x":数字,"y":数字},"path_shape":"之字形"}'
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        "stream": False, "max_tokens": 4096, "temperature": 0.1,
        "thinking": {"type": "disabled"},
    }
    headers = {"Authorization": f"Bearer {settings.ZHIPU_API_KEY}", "Content-Type": "application/json"}
    for attempt in range(3):
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                r = client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                choice = data.get("choices", [{}])[0]
                content = (choice.get("message", {}).get("content") or "").strip()
                if not content:
                    content = choice.get("reasoning_content") or ""
                if not content:
                    _pipeline_log(f"GLM empty content, finish_reason={choice.get('finish_reason')}")
                    continue
                import re as _re
                m = _re.search(r'\{[^{}]*"qi"\s*:.*?"path_shape"[^}]*\}', content, _re.DOTALL)
                if m:
                    import json as _json
                    coords = _json.loads(m.group(0))
                    if all(k in coords for k in ("qi", "cheng", "zhuan", "he")):
                        _pipeline_log(f"[arrow] GLM coords: qi=({coords['qi'].get('x')},{coords['qi'].get('y')}) he=({coords['he'].get('x')},{coords['he'].get('y')}) path={coords.get('path_shape')}")
                        return coords
                _pipeline_log(f"GLM no valid JSON in: {content[:150]}")
        except Exception as e2:
            _pipeline_log(f"GLM attempt {attempt+1} error: {e2}")
            if attempt < 2:
                time.sleep(1 + attempt)
    _pipeline_log("GLM all 3 attempts failed")
    return None


def draw_qczh_from_llm(ctx: CompositionContext) -> None:
    llm_result = ctx.llm or {}
    llm_text = llm_result.get("_raw_text") or llm_result.get("text") or ""
    if not llm_text and not ctx.img_bgr:
        return
    # try GLM first for better left/right accuracy
    coords = None
    if ctx.img_bgr is not None:
        coords = _extract_qczh_from_glm(ctx.img_bgr)
    if not coords and llm_text:
        coords = extract_qczh_coords(llm_text)
    if not coords:
        if not llm_text:
            _pipeline_log("[arrow] no GLM and no LLM text")
        else:
            tail = llm_text[-300:] if len(llm_text) > 300 else llm_text
            _pipeline_log(f"[arrow] no qczh coords. LLM tail: {tail[:200]}")
        return
    try:
        qi = coords.get("qi") or {}
        cheng = coords.get("cheng") or {}
        zhuan = coords.get("zhuan") or {}
        he = coords.get("he") or {}
        # LLM sometimes reverses qi and he; ensure qi is closer to an edge
        def _edge_dist(pt):
            x = float(pt.get("x", 50))
            y = float(pt.get("y", 50))
            return min(x, y, 100 - x, 100 - y)
        qi_he_swapped = False
        if _edge_dist(qi) > _edge_dist(he):
            qi_he_swapped = True
            qi, he = he, qi
        img_h, img_w = ctx.img_bgr.shape[:2]
        qi_pt = (int(qi["x"] * img_w / 100), int(qi["y"] * img_h / 100))
        cheng_pt = (int(cheng["x"] * img_w / 100), int(cheng["y"] * img_h / 100))
        zhuan_pt = (int(zhuan["x"] * img_w / 100), int(zhuan["y"] * img_h / 100))
        he_pt = (int(he["x"] * img_w / 100), int(he["y"] * img_h / 100))
        labels = ["起", "承", "转", "合"]
        if qi_he_swapped:
            labels[0], labels[3] = labels[3], labels[0]
        arrows = [
            (qi_pt[0], qi_pt[1], cheng_pt[0], cheng_pt[1]),
            (cheng_pt[0], cheng_pt[1], zhuan_pt[0], zhuan_pt[1]),
            (zhuan_pt[0], zhuan_pt[1], he_pt[0], he_pt[1]),
        ]
        from app.modules.pantianshou_composition.qichengzhuanhe import draw_arrows_on_lineart, generate_lineart
        from app.modules.pantianshou_composition.storage import get_arrow_overlay_path, ensure_composition_dirs, build_static_url, THUMBNAIL_SIZE
        lineart = generate_lineart(ctx.img_bgr)
        arrow_canvas = draw_arrows_on_lineart(lineart, arrows, labels)
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
        _pipeline_log(f"[arrow] ok qi=({qi_pt[0]},{qi_pt[1]})->he=({he_pt[0]},{he_pt[1]}) path={coords.get('path_shape')} swapped={qi_he_swapped}")
    except Exception as e:
        _pipeline_log(f"[arrow] FAIL: {e}")


def _fetch_knowledge_context(matched_rules: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    try:
        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        from app.modules.pantianshou_composition import qdrant_client as qc
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.modules.pantianshou_composition.models import TextChunk, ExtractedImage
        from app.modules.pantianshou_composition.storage import build_static_url
        import os as _os

        terms = set()
        for r in (matched_rules or [])[:8]:
            for k in ("rule_name", "category", "subcategory"):
                v = (r.get(k) or "").strip()
                if v:
                    terms.add(v)
        if not terms:
            _pipeline_log("knowledge_context: no terms from matched_rules")
            return [], []
        search_query = "。".join(sorted(terms))
        service = EmbeddingService()
        emb_result = service.embed_text_sync(search_query)
        if not emb_result or not emb_result.embedding:
            _pipeline_log(f"knowledge_context: embedding failed (result={bool(emb_result)}, has_embedding={bool(emb_result and emb_result.embedding)})")
            return [], []
        hits = qc.search_collection(
            qc.KNOWLEDGE_TEXTS_COLLECTION,
            emb_result.embedding,
            limit=5,
        )
        chunks = [h.get("payload", {}).get("content", "") for h in (hits or [])]
        images: List[Dict[str, Any]] = []
        seen_urls = set()
        term_words = set()
        for t in terms:
            for w in t:
                term_words.add(w)
        def _relevance(fig_id: str, cap: str) -> int:
            s = 0
            for tw in term_words:
                if tw in fig_id:
                    s += 3
                if tw in cap:
                    s += 1
            return s

        data_dir = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
        base_data_dir = _os.path.join(data_dir, "data")
        knowledge_db = _os.path.join(data_dir, "data", "knowledge.db")
        kb_engine = create_engine(f"sqlite:///{knowledge_db}", connect_args={"timeout": 30})
        KbSession = sessionmaker(bind=kb_engine)
        db = KbSession()
        try:
            for h in (hits or []):
                vector_id = h.get("id", "")
                if not vector_id:
                    continue
                chunk = db.query(TextChunk).filter(TextChunk.vector_id == vector_id).first()
                if not chunk or not chunk.associated_images:
                    continue
                for img_id in chunk.associated_images[:4]:
                    img = db.query(ExtractedImage).filter(ExtractedImage.id == img_id).first()
                    if not img or not img.stored_path:
                        continue
                    try:
                        rel = _os.path.relpath(img.stored_path, base_data_dir)
                        url = build_static_url(rel)
                    except (ValueError, OSError):
                        url = img.stored_url or ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    fig_id = (img.figure_id or "").strip()
                    caption = (img.caption or "").strip()
                    title = fig_id if fig_id else "插图"
                    note = caption[:120] if caption else ""
                    rel_score = _relevance(fig_id, caption)
                    images.append({"title": title, "image_url": url, "caption": note, "note": note, "_rel": rel_score})
        finally:
            db.close()
            kb_engine.dispose()
        images.sort(key=lambda x: -x.get("_rel", 0))
        # strip internal _rel key
        for img in images:
            img.pop("_rel", None)
        _pipeline_log(f"knowledge_context: text_chunks={len(chunks)}, images={len(images)}, query_terms={len(terms)}")
        return [c for c in chunks if c], images[:6]
    except Exception as e:
        _pipeline_log(f"knowledge_context FAIL: {e}")
        return [], []


def write_llm_narrative(ctx: CompositionContext) -> None:
    """调用 LLM 生成构图分析讲评，结果存入 ctx.llm。"""
    issues = ctx.issues or []
    references = ctx.references or []
    comparisons = ctx.comparisons or []
    theory_basis = ctx.theory_basis or []
    matched_rules = ctx.matched_rules or []
    metrics = ctx.metrics

    # ---- 搜索知识库原文 + 关联插图（潘天寿+花鸟教程），注入 LLM prompt ----
    context_knowledge, example_images = _fetch_knowledge_context(matched_rules)
    if not example_images:
        # fallback: use Qdrant-cached images from rule matching
        seen = set()
        for r in (matched_rules or []):
            for ri in (r.get("reference_images") or []):
                url = ri.get("image_url", "")
                if url and url not in seen:
                    seen.add(url)
                    example_images.append({
                        "title": (r.get("rule_name") or "规则示例").strip(),
                        "image_url": url,
                        "caption": (r.get("condition") or "").strip(),
                        "note": f"{r.get('category','')} · {r.get('rule_name','')}".strip(" ·"),
                    })
            if len(example_images) >= 5:
                break
    _pipeline_log(f"[llm] example_images={len(example_images)}, context_chunks={len(context_knowledge)}")
    if example_images:
        for ei in example_images[:2]:
            _pipeline_log(f"  img: title={ei.get('title')} url={ei.get('image_url','')[:60]}")

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
        example_images=example_images,
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
