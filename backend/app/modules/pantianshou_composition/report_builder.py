from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.modules.pantianshou_composition.analyzer import ImageMetrics


def _grade(score: int) -> str:
    if score >= 92:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 80:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def build_dimension_scores(metrics: ImageMetrics) -> Tuple[int, List[Dict[str, Any]]]:
    blank_pct = int(round(metrics.blank_ratio * 100))
    open_score = int(round(30 * (1.0 - max(metrics.dominant_orientation_ratio - 0.25, 0.0))))
    open_score = max(10, min(open_score, 30))

    void_score = int(round(25 * (1.0 - abs(blank_pct - 38) / 50.0)))
    void_score = max(8, min(void_score, 25))

    dense_score = int(round(25 * min(metrics.edge_density_std / 0.12, 1.0)))
    dense_score = max(8, min(dense_score, 25))

    aux_score = 20
    if metrics.parallel_warning:
        aux_score -= 4
    aux_score = max(8, min(aux_score, 20))

    dims = [
        {
            "name": "开合之势",
            "score": open_score,
            "max": 30,
            "analysis": _analysis_open(open_score, metrics),
            "suggestion": _suggest_open(metrics),
        },
        {
            "name": "虚实相生",
            "score": void_score,
            "max": 25,
            "analysis": _analysis_void(blank_pct),
            "suggestion": _suggest_void(blank_pct),
        },
        {
            "name": "疏密有致",
            "score": dense_score,
            "max": 25,
            "analysis": _analysis_dense(metrics),
            "suggestion": _suggest_dense(metrics),
        },
        {
            "name": "辅助元素",
            "score": aux_score,
            "max": 20,
            "analysis": _analysis_aux(metrics),
            "suggestion": _suggest_aux(metrics),
        },
    ]
    total = open_score + void_score + dense_score + aux_score
    return total, dims


def _analysis_open(score: int, metrics: ImageMetrics) -> str:
    if metrics.dominant_orientation_ratio >= 0.55:
        return "线条与物象的主方向较单一，整体气势容易趋于直白，开合的层次感偏弱。"
    if score >= 24:
        return "起结趋势较明确，画面整体方向统一，开合关系基本顺畅。"
    return "起结趋势存在，但承转不够明显，开合的节奏需要更丰富的对比。"


def _suggest_open(metrics: ImageMetrics) -> str:
    x, y, w, h = metrics.inscription_box
    if w > 0 and h > 0:
        return "可在中部或留白处增加一处“小起结”，形成承转；同时用题款/印章做呼应。"
    return "可通过穿插枝条/苔点或小石块增加承转，避免一气直贯导致的单调。"


def _analysis_void(blank_pct: int) -> str:
    if blank_pct >= 55:
        return f"留白约 {blank_pct}% ，空白偏多，若边界过于规整，容易显得空洞。"
    if blank_pct <= 20:
        return f"留白约 {blank_pct}% ，画面偏满，容易压迫，虚实对比不足。"
    return f"留白约 {blank_pct}% ，虚实比例基本可用，重点在留白形状与呼应关系。"


def _suggest_void(blank_pct: int) -> str:
    if blank_pct >= 55:
        return "建议用题款或轻点苔、飞鸟等小物补实，以虚中求实，避免空白过大。"
    if blank_pct <= 20:
        return "建议减少局部重复笔触，留出透气空隙，让主次关系更分明。"
    return "可微调留白边界的曲直与开合，使留白形成“有意味的形”，并与主体形成对话。"


def _analysis_dense(metrics: ImageMetrics) -> str:
    if metrics.parallel_warning:
        return "局部出现较明显的长线条平行趋势，容易带来呆板感，需要用穿插与角度变化打破。"
    if metrics.edge_density_std < 0.05:
        return "疏密分布偏平均，节奏对比不够强烈，画面容易显得平。"
    return "疏密区有一定对比，若再强化密处的聚与疏处的透，节奏会更鲜明。"


def _suggest_dense(metrics: ImageMetrics) -> str:
    if metrics.parallel_warning:
        return "调整副枝/山脊线角度，避免与主线长时间平行；用苔点或短线穿插制造破势。"
    if metrics.edge_density_std < 0.05:
        return "密处宜更聚，疏处宜更透；可把次要元素收拢成簇，留出更明确的呼吸间隙。"
    return "建议在密处强化穿插、叠压与遮挡关系，同时让疏处保持大块留白与走势延伸。"


def _analysis_aux(metrics: ImageMetrics) -> str:
    x, y, w, h = metrics.inscription_box
    if w <= 0 or h <= 0:
        return "题款与印章位置需要结合留白重新寻找落点，使辅助元素与主体形成对角或呼应。"
    return "辅助元素可用题款/印章在留白处建立平衡与呼应，避免主体孤立。"


def _suggest_aux(metrics: ImageMetrics) -> str:
    if metrics.parallel_warning:
        return "可在留白处用题款形成另一条走势，与主体方向形成对照，减弱平行线的呆板。"
    return "建议按“虚处落款、实处留白”的原则，把题款放在建议框附近，再用印章压角呼应。"


def build_report(
    task_id: str,
    metrics: ImageMetrics,
    annotations: Dict[str, Any],
    original_url: str,
    heatmap_url: str | None,
    references: List[Dict[str, Any]],
    matched_rules: List[Dict[str, Any]] | None,
    issues: List[Dict[str, Any]] | None,
    comparisons: List[Dict[str, Any]] | None,
    checks: List[Dict[str, Any]] | None,
    theory_basis: List[Dict[str, Any]] | None,
    llm: Dict[str, Any] | None,
    ruleset_version: str,
    model_version: str,
) -> Dict[str, Any]:
    total_score, dimensions = build_dimension_scores(metrics)
    grade = _grade(total_score)
    comment = _build_comment(total_score, metrics)

    if heatmap_url:
        annotations = dict(annotations)
        annotations["heatmap"] = heatmap_url

    return {
        "report_version": "1.0",
        "ruleset_version": ruleset_version,
        "model_version": model_version,
        "summary": {
            "total_score": total_score,
            "grade": grade,
            "comment": comment,
        },
        "issues": issues or [],
        "dimensions": dimensions,
        "checks": checks or [],
        "theory_basis": theory_basis or [],
        "llm": llm or {"ok": False},
        "references": references,
        "comparisons": comparisons or [],
        "matched_rules": matched_rules or [],
        "annotations": annotations,
        "assets": {
            "original_url": original_url,
            "heatmap_url": heatmap_url,
        },
    }


def _build_comment(total_score: int, metrics: ImageMetrics) -> str:
    if total_score >= 85:
        return "整体势能较强，疏密与虚实关系较有章法；建议在局部承转处再做精细推敲。"
    if total_score >= 75:
        return "作品气势尚可，结构关系基本成立；可进一步强化疏密对比与起结承转，让节奏更鲜明。"
    if metrics.parallel_warning:
        return "画面主线条关系偏平行，容易显得呆板；建议用穿插与角度变化打破，并调整留白形状。"
    return "构图关系仍需加强，建议从开合、虚实、疏密三条线同时推敲，先立势再求精。"
