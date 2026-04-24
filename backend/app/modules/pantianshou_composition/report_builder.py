from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

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


def build_dimension_scores(
    metrics: ImageMetrics,
    adv: Optional[Any] = None,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Build 7-dimension scores with optional advanced CV metrics.
    
    评分哲学：中国画构图分析的目的不是挑毛病，而是帮助理解作品的结构关系。
    经典作品之所以成为经典，必然有其道理。评分应反映"结构完整性"而非"完美度"。
    
    7维度100分方案（v2.0 — 融合潘天寿+写意花鸟画教程）：
      开合之势: 20  (20%) — 原30降权
      虚实相生: 18  (18%) — 原25降权
      疏密有致: 18  (18%) — 原25降权
      辅助元素: 14  (14%) — 原20降权
      均衡节奏: 12  (12%) — NEW from panplus
      穿插结构: 10  (10%) — NEW from panplus
      边角空间:  8   (8%) — NEW from panplus
    """
    blank_pct = int(round(metrics.blank_ratio * 100))

    # ------------------------------------------------------------------
    # 1. Open & Close (开合之势) — max 20
    # ------------------------------------------------------------------
    open_score = 15  # base (大多数作品的开合关系是成立的)
    # Direction diversity (from basic metric)
    if metrics.dominant_orientation_ratio < 0.35:
        open_score += 3  # 多方向，开合丰富
    elif metrics.dominant_orientation_ratio < 0.55:
        open_score += 1
    # Advanced: trend conflict penalty (but mild)
    if adv and hasattr(adv, "trends"):
        tr = adv.trends
        if tr.has_major_conflict:
            open_score -= 2
        elif tr.opposing_trends >= 1:
            open_score -= 1
        # Good: dominant direction exists but not too strong
        if 0.25 <= tr.dominant_strength <= 0.5:
            open_score += 1
        elif tr.dominant_strength > 0.6:
            open_score -= 1  # 太强=单调
    # Parallel warning (mild)
    if metrics.parallel_warning:
        open_score -= 1
    open_score = max(8, min(open_score, 20))

    # ------------------------------------------------------------------
    # 2. Void & Solid (虚实相生) — max 18
    # ------------------------------------------------------------------
    void_score = 14  # base
    # 宽松的留白区间
    if 25 <= blank_pct <= 75:
        void_score += 3  # 大多数作品的留白在这个范围
    elif 15 <= blank_pct < 25 or 75 < blank_pct <= 85:
        void_score += 1  # 稍偏但合理
    elif blank_pct > 85:
        void_score -= 2  # 留白偏多
    elif blank_pct < 10:
        void_score -= 4  # 过于满
    # Advanced: dense area breathing
    if adv and hasattr(adv, "gaps"):
        g = adv.gaps
        if g.dense_internal_blank_ratio >= 0.12:
            void_score += 1  # good: dense areas breathe
    void_score = max(8, min(void_score, 18))

    # ------------------------------------------------------------------
    # 3. Sparse & Dense (疏密有致) — max 18
    # ------------------------------------------------------------------
    dense_score = 13  # base
    # Rhythm from edge density std
    if metrics.edge_density_std >= 0.10:
        dense_score += 3
    elif metrics.edge_density_std >= 0.06:
        dense_score += 1
    elif metrics.edge_density_std < 0.02:
        dense_score -= 2
    # Advanced: rhythm score
    if adv and hasattr(adv, "gaps"):
        g = adv.gaps
        if g.rhythm_score >= 0.15:
            dense_score += 1
        elif g.rhythm_score < 0.05:
            dense_score -= 1
    # Advanced: element count
    if adv and hasattr(adv, "elements"):
        el = adv.elements
        if el.element_count >= 3:
            dense_score += 1  # good: 3+ elements
    # Parallel (mild penalty)
    if metrics.parallel_warning:
        dense_score -= 1
    dense_score = max(8, min(dense_score, 18))

    # ------------------------------------------------------------------
    # 4. Auxiliary Elements (辅助元素) — max 14
    # ------------------------------------------------------------------
    aux_score = 11  # base
    # Inscription box
    x, y, w, h = metrics.inscription_box
    if w > 0 and h > 0:
        aux_score += 2
    else:
        aux_score -= 1  # 没有题款很正常
    # Advanced: triangle structure bonus
    if adv and hasattr(adv, "triangle"):
        tri = adv.triangle
        if tri.has_triangle and not tri.is_equilateral:
            aux_score += 1
        if tri.is_equilateral:
            aux_score -= 1  # mild penalty
    aux_score = max(6, min(aux_score, 14))

    # ------------------------------------------------------------------
    # 5. Balance & Rhythm (均衡节奏) — max 12 [NEW from panplus]
    #    来源：杆秤式均衡、蓄势借力、大小相间、合掌顺掌交掌
    # ------------------------------------------------------------------
    balance_score = 9  # base
    if adv and hasattr(adv, "region"):
        r = adv.region
        # L/R non-symmetry is good for 杆秤式均衡
        lr = r.left_right_ratio
        if 0.6 <= lr <= 1.67:
            balance_score += 1  # reasonable asymmetry
        elif 0.4 <= lr < 0.6 or 1.67 < lr <= 2.5:
            pass  # neutral — some asymmetry exists
        # Top/bottom balance
        if 0.67 <= r.top_bot_ratio <= 1.5:
            balance_score += 1
    if adv and hasattr(adv, "elements"):
        el = adv.elements
        # Size variety (大小三级变化)
        if el.area_ratio_max_min >= 3.0 and el.element_count >= 4:
            balance_score += 1
        # Spacing variety (避免等间距)
        if el.spacing_uniformity >= 0.2:
            balance_score += 1
    balance_score = max(4, min(balance_score, 12))

    # ------------------------------------------------------------------
    # 6. Interweaving Structure (穿插结构) — max 10 [NEW from panplus]
    #    来源："女"字交叉、直起横破、合掌顺掌交掌
    # ------------------------------------------------------------------
    weave_score = 7  # base
    if adv and hasattr(adv, "crossings"):
        c = adv.crossings
        # Good: acute crosses (女字形)
        if c.acute_crosses >= 2:
            weave_score += 1
        # Bad: too many HV crosses (十字形)
        if c.horizontal_vertical_crosses >= 2:
            weave_score -= 1
        # Good: line angle diversity
        if 0.3 <= c.angle_concentration <= 0.7:
            weave_score += 1
        # Bad: too many single-point crossings
        if c.single_point_crossings > 0:
            weave_score -= 1
    if adv and hasattr(adv, "trends"):
        tr = adv.trends
        # Good: diagonal ratio (斜势)
        if tr.diagonal_ratio >= 0.3:
            weave_score += 1
        # Bad: too flat (平板)
        if tr.horizontal_vertical_ratio > 0.6 and tr.diagonal_ratio < 0.2:
            weave_score -= 1
    weave_score = max(3, min(weave_score, 10))

    # ------------------------------------------------------------------
    # 7. Edge & Corner Space (边角空间) — max 8 [NEW from panplus]
    #    来源：占边占角、实空白与虚空白、款印分割空间
    # ------------------------------------------------------------------
    edge_score = 6  # base
    if adv and hasattr(adv, "region"):
        r = adv.region
        # Corner variety (四角不等量) — good
        corners = [r.top_left, r.top_right, r.bot_left, r.bot_right]
        corner_std = float(np.std(corners))
        if corner_std >= 0.03:
            edge_score += 1  # corners have variety
        # Large blank areas (大实空白)
        if adv and hasattr(adv, "gaps"):
            g = adv.gaps
            # Breathing room in dense areas (小空白透气)
            if g.dense_internal_blank_ratio >= 0.08:
                edge_score += 1
    # Inscription contributes to edge balance
    x, y, w, h = metrics.inscription_box
    if w > 0 and h > 0:
        edge_score += 1  # inscription helps edge composition
    edge_score = max(3, min(edge_score, 8))

    dims = [
        {
            "name": "开合之势",
            "score": open_score,
            "max": 20,
            "analysis": _analysis_open(open_score, metrics, adv),
            "suggestion": _suggest_open(metrics, adv),
        },
        {
            "name": "虚实相生",
            "score": void_score,
            "max": 18,
            "analysis": _analysis_void(blank_pct, adv),
            "suggestion": _suggest_void(blank_pct, adv),
        },
        {
            "name": "疏密有致",
            "score": dense_score,
            "max": 18,
            "analysis": _analysis_dense(metrics, adv),
            "suggestion": _suggest_dense(metrics, adv),
        },
        {
            "name": "辅助元素",
            "score": aux_score,
            "max": 14,
            "analysis": _analysis_aux(metrics, adv),
            "suggestion": _suggest_aux(metrics, adv),
        },
        {
            "name": "均衡节奏",
            "score": balance_score,
            "max": 12,
            "analysis": _analysis_balance(metrics, adv),
            "suggestion": _suggest_balance(metrics, adv),
        },
        {
            "name": "穿插结构",
            "score": weave_score,
            "max": 10,
            "analysis": _analysis_weave(metrics, adv),
            "suggestion": _suggest_weave(metrics, adv),
        },
        {
            "name": "边角空间",
            "score": edge_score,
            "max": 8,
            "analysis": _analysis_edge(metrics, adv),
            "suggestion": _suggest_edge(metrics, adv),
        },
    ]
    total = open_score + void_score + dense_score + aux_score + balance_score + weave_score + edge_score
    return total, dims


def _analysis_open(score: int, metrics: ImageMetrics, adv: Any = None) -> str:
    parts = []
    if score >= 26:
        parts.append("起结趋势明确，画面方向统一。")
    else:
        parts.append("起结趋势基本存在。")
    if adv and hasattr(adv, "trends"):
        tr = adv.trends
        if tr.has_major_conflict:
            parts.append("画面中存在方向对立的趋势，可进一步梳理主次关系。")
        elif 0.25 <= tr.dominant_strength <= 0.5:
            parts.append("主导方向力度适中，开合有度。")
    if metrics.parallel_warning:
        parts.append("部分线条方向趋同，可用斜向穿插丰富变化。")
    if not parts:
        return "起结趋势基本成立。"
    return " ".join(parts)


def _suggest_open(metrics: ImageMetrics, adv: Any = None) -> str:
    if adv and hasattr(adv, "trends") and adv.trends.has_major_conflict:
        return "建议统一主导方向，将次要趋势弱化为小起结服从大势。"
    x, y, w, h = metrics.inscription_box
    if w > 0 and h > 0:
        return '可在中部或留白处增加一处"小起结"，形成承转；同时用题款/印章做呼应。'
    return "可通过穿插枝条/苔点或小石块增加承转，避免一气直贯导致的单调。"


def _analysis_void(blank_pct: int, adv: Any = None) -> str:
    if blank_pct < 10:
        return f"留白约 {blank_pct}%，画面几乎布满，虚实对比不足。"
    if 30 <= blank_pct <= 70:
        # 这个范围内的留白是合理的
        if blank_pct >= 55:
            return f"留白约 {blank_pct}%，虚实关系成立，留白与主体形成呼吸节奏。"
        return f"留白约 {blank_pct}%，虚实比例得当，画面有呼吸感。"
    if blank_pct > 80:
        return f"留白约 {blank_pct}%，留白面积较大，需注意让留白成形并虚中有物。"
    if blank_pct < 20:
        return f"留白约 {blank_pct}%，画面偏实，可适当留出透气空间。"
    if adv and hasattr(adv, "gaps"):
        g = adv.gaps
        if g.dense_area_ratio > 0.3 and g.dense_internal_blank_ratio < 0.05:
            return f"留白约 {blank_pct}%，密处较为紧实，可在密组内留出气口。"
    if blank_pct > 70:
        return f"留白约 {blank_pct}%，留白充裕，注意让留白成形。"
    return f"留白约 {blank_pct}%，虚实比例基本可用。"


def _suggest_void(blank_pct: int, adv: Any = None) -> str:
    if blank_pct > 80:
        return "留白较大，可考虑用题款或轻点苔、飞鸟等小物补实，以虚中求实。"
    if blank_pct < 10:
        return "画面偏满，可减少次要笔触，留出透气空隙，让主次分明。"
    if adv and hasattr(adv, "gaps"):
        g = adv.gaps
        if g.dense_internal_blank_ratio < 0.05 and g.dense_area_ratio > 0.3:
            return "密处可透出小空白使画面灵动，在密组内减少叠压留出气口。"
    if 30 <= blank_pct <= 70:
        return "留白比例合理，可进一步推敲留白边界的曲直与开合，使留白与主体形成更好的对话。"
    if blank_pct < 25:
        return "可适当减少次要信息，留出更多透气空隙，强化主次关系。"
    return '可微调留白边界的曲直与开合，使留白形成"有意味的形"。'


def _analysis_dense(metrics: ImageMetrics, adv: Any = None) -> str:
    parts = []
    if metrics.parallel_warning:
        parts.append("局部线条方向趋同，可用斜向穿插丰富变化。")
    if adv and hasattr(adv, "elements"):
        el = adv.elements
        if el.spacing_uniformity < 0.10 and el.element_count >= 4:
            parts.append("元素间距过于均匀，缺乏远近变化。")
    if adv and hasattr(adv, "region"):
        r = adv.region
        if r.center_vs_avg < 0.3:  # 更严格的蜂腰阈值
            parts.append("画面中间区域墨色偏少，呈蜂腰状。")
    if not parts:
        return "疏密有一定对比，画面节奏基本成立。"
    return " ".join(parts)


def _suggest_dense(metrics: ImageMetrics, adv: Any = None) -> str:
    if metrics.parallel_warning:
        return "调整副枝/山脊线角度，避免与主线长时间平行；用苔点或短线穿插制造破势。"
    if adv and hasattr(adv, "region") and adv.region.center_vs_avg < 0.3:
        return "中间区域可添加过渡元素（如小石、苔点），让上下连贯。"
    if adv and hasattr(adv, "elements"):
        el = adv.elements
        if el.spacing_uniformity < 0.10 and el.element_count >= 4:
            return "建议调整部分元素位置打破等距排列，让间距有远近变化。"
    if metrics.edge_density_std < 0.04:
        return "密处宜更聚，疏处宜更透；可把次要元素收拢成簇，留出更明确的呼吸间隙。"
    return "可在密处进一步强化穿插与遮挡关系，疏处保持大块留白与走势延伸。"


def _analysis_aux(metrics: ImageMetrics, adv: Any = None) -> str:
    x, y, w, h = metrics.inscription_box
    if w > 0 and h > 0:
        return "已检测到题款/印章，可在留白处进一步经营位置与大小。"
    if adv and hasattr(adv, "elements"):
        el = adv.elements
        if el.isolated_elements >= 1 and el.element_count >= 4:
            return "存在与其他元素距离较远的孤立元素，可调整位置使其呼应。"
    return "题款与印章可在留白处经营，建立与主体的平衡与呼应。"


def _suggest_aux(metrics: ImageMetrics, adv: Any = None) -> str:
    if metrics.parallel_warning:
        return "可在留白处用题款形成另一条走势，与主体方向形成对照，减弱平行线的呆板。"
    if adv and hasattr(adv, "elements") and adv.elements.isolated_elements >= 1:
        return "孤立元素建议调整位置使其与主组呼应，或用款印补充建立联系。"
    return '建议按"虚处落款、实处留白"的原则，把题款放在建议框附近，再用印章压角呼应。'


def _analysis_balance(metrics: ImageMetrics, adv: Any = None) -> str:
    """均衡节奏维度分析 — 杆秤式均衡、大小相间、蓄势借力"""
    parts = []
    if adv and hasattr(adv, "elements"):
        el = adv.elements
        if el.area_ratio_max_min >= 3.0 and el.element_count >= 4:
            parts.append("元素大小对比鲜明，大小相间的节奏感较好。")
        elif el.area_ratio_max_min < 2.0 and el.element_count >= 4:
            parts.append("元素大小对比不够明显，可拉开大小差异以增强节奏。")
        if el.spacing_uniformity >= 0.2:
            parts.append("元素间距有远近变化，避免了等距排列的呆板。")
    if adv and hasattr(adv, "region"):
        r = adv.region
        lr = r.left_right_ratio
        if 0.5 <= lr <= 2.0:
            parts.append("左右非对称均衡关系成立，杆秤式平衡感较好。")
    if not parts:
        return "画面的均衡节奏基本成立。"
    return " ".join(parts)


def _suggest_balance(metrics: ImageMetrics, adv: Any = None) -> str:
    if adv and hasattr(adv, "elements"):
        el = adv.elements
        if el.area_ratio_max_min < 2.0 and el.element_count >= 4:
            return "可拉开元素大小差异，形成大间小、小间大的攒三聚五节奏。"
        if el.spacing_uniformity < 0.15:
            return "元素间距过于均匀，建议调整部分元素位置打破等距排列。"
    return "可在某一侧增加款印或小物作为\"压阵\"，使杆秤式平衡更加鲜明。"


def _analysis_weave(metrics: ImageMetrics, adv: Any = None) -> str:
    """穿插结构维度分析 — "女"字交叉、直起横破、线条交织"""
    parts = []
    if adv and hasattr(adv, "crossings"):
        c = adv.crossings
        if c.acute_crosses >= 2:
            parts.append("线条交叉角度富于变化，穿插关系丰富。")
        if c.horizontal_vertical_crosses >= 2:
            parts.append("存在较多十字形交叉，穿插角度可进一步调整。")
    if adv and hasattr(adv, "trends"):
        tr = adv.trends
        if tr.diagonal_ratio >= 0.3:
            parts.append("画面有斜势走向，纵横交错使气势更生动。")
        elif tr.horizontal_vertical_ratio > 0.6:
            parts.append("线条以水平/垂直为主，缺少斜向穿插的变化。")
    if not parts:
        return "穿插结构基本成立，线条关系有一定变化。"
    return " ".join(parts)


def _suggest_weave(metrics: ImageMetrics, adv: Any = None) -> str:
    if adv and hasattr(adv, "trends") and adv.trends.diagonal_ratio < 0.2:
        return "可增加斜向元素打破横竖为主的平板感，形成纵横互破的生动穿插。"
    if adv and hasattr(adv, "crossings") and adv.crossings.horizontal_vertical_crosses >= 2:
        return "建议调整部分线条角度避免正交十字交叉，形成更有变化的女字交叉结构。"
    return "可用\"直起横破、横起竖破\"的方法，在主势方向的垂直方向加入穿插元素。"


def _analysis_edge(metrics: ImageMetrics, adv: Any = None) -> str:
    """边角空间维度分析 — 占边占角、实空白与虚空白"""
    parts = []
    if adv and hasattr(adv, "region"):
        r = adv.region
        corners = [r.top_left, r.top_right, r.bot_left, r.bot_right]
        corner_std = float(np.std(corners))
        if corner_std >= 0.03:
            parts.append("四角留白有大小变化，金边银角的处理较为讲究。")
        else:
            parts.append("四角留白偏均匀，可拉开四角差异。")
    if adv and hasattr(adv, "gaps"):
        g = adv.gaps
        if g.dense_internal_blank_ratio >= 0.08:
            parts.append("密处有透气的小空白，如围棋活眼使画面不闷。")
    if not parts:
        return "边角空间处理基本合理。"
    return " ".join(parts)


def _suggest_edge(metrics: ImageMetrics, adv: Any = None) -> str:
    x, y, w, h = metrics.inscription_box
    if w <= 0 or h <= 0:
        return "可利用题款印章调节四角留白，使大空白分割为大小不同的子空间。"
    return "可进一步推敲款印位置与画框边角的关系，使\"金边银角\"更加讲究。"


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
    adv: Any = None,
    arrow_analysis: Dict[str, Any] | None = None,
    arrow_overlay_url: str | None = None,
    thumb_url: str | None = None,
) -> Dict[str, Any]:
    total_score, dimensions = build_dimension_scores(metrics, adv=adv)
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
        "arrow_analysis": arrow_analysis,
        "assets": {
            "original_url": original_url,
            "thumb_url": thumb_url,
            "heatmap_url": heatmap_url,
            "arrow_overlay_url": arrow_overlay_url,
        },
    }


def _build_comment(total_score: int, metrics: ImageMetrics) -> str:
    if total_score >= 85:
        return "构图功力深厚，开合、虚实、疏密三条线配合默契，画面气韵生动，是一幅结构成熟的佳作。"
    if total_score >= 78:
        return "构图整体结构成立，主次分明、虚实得当；局部可进一步推敲承转与疏密节奏。"
    if total_score >= 70:
        return "作品具有一定的构图意识，基本关系能够成立；可在开合承转和疏密对比上继续精进。"
    if metrics.parallel_warning:
        return "画面整体有一定气势，但局部线条关系偏平行；可用穿插与角度变化丰富空间层次。"
    return "构图处于探索阶段，建议先从一幅画只做一件事（比如只练习开合）开始，逐步叠加。"
