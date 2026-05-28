"""
墨林情绪引擎 v2.0
────────────────────────────────────────
八维度融合情感评分系统

维度:
1. 文字词典 (通用)
2. 空间布局 (通用)
3. 画材情感 (通用)
4. 尺寸元数据 (通用)
5. 时期基线 (特化)
6. 印章情感 (特化)
7. 主题覆盖 (特化)
8. 笔墨质感 (预留 — 待图形识别)
"""

import math
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from app.services.emotion_lexicon_loader import get_lexicon


@dataclass
class DimensionResult:
    """单维度评分结果"""
    name: str
    raw: float = 0.0
    normalized: float = 0.0
    confidence: float = 1.0
    has_data: bool = False
    signals: List[Dict] = field(default_factory=list)


@dataclass
class EngineResult:
    """引擎综合结果"""
    text: DimensionResult = field(default_factory=lambda: DimensionResult("文字"))
    spatial: DimensionResult = field(default_factory=lambda: DimensionResult("空间"))
    painting: DimensionResult = field(default_factory=lambda: DimensionResult("画材"))
    size: DimensionResult = field(default_factory=lambda: DimensionResult("尺寸"))
    period: DimensionResult = field(default_factory=lambda: DimensionResult("时期"))
    seal: DimensionResult = field(default_factory=lambda: DimensionResult("印章"))
    theme: DimensionResult = field(default_factory=lambda: DimensionResult("主题"))
    brush_ink: DimensionResult = field(default_factory=lambda: DimensionResult("笔墨"))
    combined_raw: float = 0.0
    combined_normalized: float = 0.0
    polarity: str = "neutral"
    reasoning: str = ""
    weights_used: Dict[str, float] = field(default_factory=dict)
    # v3.1 新增
    dimension_polarities: Dict[str, str] = field(default_factory=dict)  # {"text": "positive", ...}
    conflict_score: float = 0.0  # 0~1，情感矛盾程度


# ── 默认权重（校准后）──────────────────────────────────────
DEFAULT_WEIGHTS = {
    "text": 0.40,
    "spatial": 0.20,
    "painting": 0.10,
    "size": 0.05,
    "period": 0.10,
    "seal": 0.10,
    "theme": 0.05,
    "brush_ink": 0.00,  # 预留维度，当前权重为 0
}

VADER_ALPHA = 8.0


def vader_normalize(raw: float, alpha: float = VADER_ALPHA) -> float:
    """VADER 归一化: raw → [-1, +1]"""
    if raw == 0:
        return 0.0
    return raw / math.sqrt(raw ** 2 + alpha)


def classify_polarity(normalized: float,
                      pos_threshold: float = 0.10,
                      neg_threshold: float = -0.10) -> str:
    """判断极性（简单三分类）"""
    if normalized >= pos_threshold:
        return "positive"
    elif normalized <= neg_threshold:
        return "negative"
    return "neutral"


def classify_complex_polarity(normalized: float,
                               dimension_polarities: Dict[str, str]) -> str:
    """六分类极性判断：考虑维度间的矛盾

    返回:
    - positive / negative / neutral          → 单一倾向，无矛盾
    - complex_positive / complex_negative    → 矛盾但有主导方向
    - complex_balanced                       → 矛盾且势均力敌
    """
    pos_count = sum(1 for p in dimension_polarities.values() if p == "positive")
    neg_count = sum(1 for p in dimension_polarities.values() if p == "negative")

    # 矛盾检测：至少有 2 个正面和 2 个负面维度
    is_conflicted = pos_count >= 2 and neg_count >= 2

    if is_conflicted:
        if normalized > 0.05:
            return "complex_positive"
        elif normalized < -0.05:
            return "complex_negative"
        return "complex_balanced"

    # 单一倾向
    if normalized >= 0.10:
        return "positive"
    elif normalized <= -0.10:
        return "negative"
    return "neutral"


def compute_conflict_score(dimensions: List[DimensionResult]) -> float:
    """计算情感冲突度 0~1

    考虑两个因素：
    1. 正负维度的平衡度（越接近 50/50 越高）
    2. 参与冲突的维度占比（越多维度参与冲突越高）

    全部同号 → 0，多个维度正负对峙 → 趋近 1
    """
    pos = sum(1 for d in dimensions if d.normalized > 0.05)
    neg = sum(1 for d in dimensions if d.normalized < -0.05)
    total_dim = len(dimensions)

    if pos == 0 or neg == 0:
        return 0.0

    # 平衡度：正负越接近，ratio 越高
    balance = min(pos, neg) / max(pos, neg)  # (0, 1]

    # 参与度：参与冲突的维度占比（至少 2 正 2 负才算有意义的冲突）
    engagement = (pos + neg) / total_dim  # (0, 1]

    # 组合分数：平衡度 × 参与度
    return round(balance * engagement, 3)


def analyze_text(text: str, use_rules: bool = True) -> DimensionResult:
    """维度1: 文字词典分析（v3：集成规则引擎）

    流程：
    1. 规则引擎预处理（多字词组优先匹配 → 否定词检测 → 程度副词 → 前后缀）
    2. 词库匹配（跳过已被多字词组占用的位置）
    3. 后处理：否定反转 × 副词加权
    """
    from app.services.emotion_text_preprocessor import get_preprocessor

    lexicon = get_lexicon()
    result = DimensionResult(name="文字")

    if not text:
        return result

    score = 0.0
    matched = []
    positions = set()

    if use_rules:
        # ── v3 规则引擎 ──────────────────────────────────
        preprocessor = get_preprocessor(lexicon.get_multi_char_words())
        annotated = preprocessor.preprocess(text)

        # 标记被多字词组占用的位置（含否定特例边界）
        for b in annotated.word_boundaries:
            for p in range(b.start, b.end):
                positions.add(p)
            w_score = lexicon.get_score(b.word)
            if w_score is not None:
                # v3.2 fix: 多字词也要检查否定范围
                is_negated, neg_word = annotated.is_in_negation_scope(b.start)
                if is_negated:
                    w_score = -w_score
                score += w_score
                matched.append({"word": b.word, "score": w_score, "method": "multi_word", "negated": is_negated})

        for b in annotated.exception_boundaries:
            for p in range(b.start, b.end):
                positions.add(p)

        # 对剩余位置进行单字/双字匹配
        words = sorted(lexicon.get_all_words(), key=len, reverse=True)
        for word in words:
            if len(word) < 2:
                continue  # 单字后面处理
            if word in [b.word for b in annotated.word_boundaries]:
                continue  # 已被多字词组匹配

            pos = text.find(word)
            if pos >= 0:
                word_pos = set(range(pos, pos + len(word)))
                if not word_pos & positions:
                    positions.update(word_pos)
                    w_score = lexicon.get_score(word)
                    if w_score is not None:
                        # 判断是否在否定作用范围内
                        is_negated, neg_word = annotated.is_in_negation_scope(pos)
                        if is_negated:
                            w_score = -w_score  # 极性反转
                        # 程度副词加权
                        adv_mult = annotated.get_adverb_multiplier(pos)
                        w_score = round(w_score * adv_mult)
                        score += w_score
                        matched.append({
                            "word": word,
                            "score": w_score,
                            "method": "matched",
                            "negated": is_negated,
                            "adverb_mult": adv_mult if adv_mult != 1.0 else None,
                        })

        # 单字匹配（跳过已占用的位置）
        single_words = [w for w in lexicon.get_all_words() if len(w) == 1]
        for word in single_words:
            pos = text.find(word)
            if pos >= 0 and pos not in positions:
                positions.add(pos)
                w_score = lexicon.get_score(word)
                if w_score is not None:
                    # 否定 + 副词加权
                    is_negated, neg_word = annotated.is_in_negation_scope(pos)
                    if is_negated:
                        w_score = -w_score
                    adv_mult = annotated.get_adverb_multiplier(pos)
                    w_score = round(w_score * adv_mult)
                    score += w_score
                    matched.append({
                        "word": word,
                        "score": w_score,
                        "method": "single_char",
                        "negated": is_negated,
                        "adverb_mult": adv_mult if adv_mult != 1.0 else None,
                    })

    else:
        # ── 旧版（纯词库匹配，无规则）────────────────────
        words = sorted(lexicon.get_all_words(), key=len, reverse=True)
        for word in words:
            pos = text.find(word)
            if pos >= 0:
                word_pos = set(range(pos, pos + len(word)))
                if not word_pos & positions:
                    positions.update(word_pos)
                    w_score = lexicon.get_score(word)
                    if w_score is not None:
                        score += w_score
                        matched.append({"word": word, "score": w_score})

    result.raw = score
    # v3.2 fix: 单字匹配分数上限（±8），防止长文本中大量单字堆叠
    single_total = sum(s.get("score", 0) or 0 for s in matched if s.get("method") == "single_char")
    if abs(single_total) > 8:
        ratio = 8.0 / abs(single_total)
        for s in matched:
            if s.get("method") == "single_char":
                original = s["score"]
                s["score"] = round(original * ratio)
        result.raw = sum(s.get("score", 0) or 0 for s in matched)

    # 后处理：语境规则调整（修正反讽、条件句式的误判）
    result.raw = _apply_context_rules(text, result.raw, matched)
    result.normalized = vader_normalize(result.raw)
    result.has_data = len(matched) > 0
    result.confidence = 1.0 if result.has_data else 0.3
    result.signals = matched
    return result


def _apply_context_rules(text: str, score: float, signals: List[Dict] = None) -> float:
    """后处理规则：修正词库对反讽、条件句式的误判

    两阶段：
    1. 精准扣分 — 识别反衬/条件句式中的特定词，选择性降分
    2. 整体缩放 — 对无法定位到具体词的反讽模式，整体降低
    """
    import re
    penalty = 0.0
    signals = signals or []

    # ═══ 精准扣分：针对特定词的语境修正 ═══

    # 规则1: 反讽对比 — "X无限，Y嫌/弃/恶" → X中的正面词是反衬
    #   找到"甘芳"等在被"嫌/弃"前的正面词，降低其贡献
    foil_match = re.search(r'(\S{1,4}(?:物|者|处)?)\s*无[限数量](?:\S{0,6})[，,\s]*\S*?(嫌|弃|恶|厌|憎)', text)
    if foil_match:
        foil_section = text[:foil_match.start()]
        for sig in signals:
            word = sig.get("word", "")
            w_score = sig.get("score", 0) or 0
            # 在 foil 区域中的正面多字词 → 减半
            if len(word) >= 2 and w_score > 0 and word in foil_section:
                penalty += w_score * 0.5

    # 规则2: 条件让步 — "任使/纵使...乃/方得志"
    #   "得志/成名/出头"等词出现在条件结构中 → 减半
    cond_match = re.search(r'(?:任使|纵使|即便|需使)\S{0,20}(?:乃|方|始|才)(\S{1,3}(?:志|名|头|功))', text)
    if cond_match:
        cond_word = cond_match.group(1)
        for sig in signals:
            if sig.get("word") == cond_word and sig.get("score", 0) > 0:
                penalty += sig["score"] * 0.6

    # 规则3: 转折连词 — "而/却/但/唯/独"前后情感相反
    #   例: "甘芳物无限，其中涵辣嫌人餐" → "其中"暗示转折
    pivot_match = re.search(r'(?:其中|唯有|独有|却是|而)(\S{0,10}(?:嫌|弃|恶|厌|憎)\S{0,6})', text)
    if pivot_match:
        # 转折后的负面词前面的正面词 → 反衬
        pivot_pos = pivot_match.start()
        before = text[:pivot_pos]
        for sig in signals:
            word = sig.get("word", "")
            w_score = sig.get("score", 0) or 0
            if len(word) >= 2 and w_score > 0 and word in before:
                penalty += w_score * 0.4

    if penalty > 0:
        score -= penalty

    # ═══ 整体缩放：对无法定位到具体词的模式 ═══

    # 自嘲式否定 — "莫嫌X少" → 苦涩底色
    if re.search(r'莫嫌.{1,6}(?:少|不\S|无\S)', text) and score > 2:
        score = score * 0.7

    # 笑杀/笑倒/笑破 — 苦涩/讽刺的笑，不是愉快的笑
    if re.search(r'笑[杀倒破讽]', text):
        for sig in signals:
            if sig.get("word") in ("笑", "一笑", "可笑") and sig.get("score", 0) > 0:
                score -= sig["score"] * 0.6  # 笑的分值减少 60%

    return max(score, -10.0)  # 不低于 -10


def analyze_spatial(spatial_emotion: Dict) -> DimensionResult:
    """维度2: 空间布局分析"""
    result = DimensionResult(name="空间")

    if not spatial_emotion or not spatial_emotion.get("signals"):
        return result

    raw_score = spatial_emotion.get("combined_spatial_score")
    # 旧数据可能没有 combined_spatial_score，从 signals 中提取
    if raw_score is None:
        signals = spatial_emotion.get("signals", [])
        scores = [s.get("score") for s in signals if s.get("score") is not None]
        raw_score = max(scores, key=abs) if scores else 0.0

    result.raw = raw_score or 0.0
    result.normalized = vader_normalize(result.raw)
    result.has_data = bool(spatial_emotion.get("signals"))
    result.confidence = 0.8 if result.has_data else 0.3
    result.signals = spatial_emotion.get("signals", [])
    return result


def analyze_painting(painting_matches: List[Dict]) -> DimensionResult:
    """维度3: 画材情感分析"""
    result = DimensionResult(name="画材")

    if not painting_matches:
        return result

    score = 0.0
    for match in painting_matches:
        rule = match.get("rule", {})
        score += rule.get("emotion_offset", 0) * match.get("weight_multiplier", 1.0)

    result.raw = score
    result.normalized = vader_normalize(score)
    result.has_data = True
    result.confidence = 0.7
    result.signals = painting_matches
    return result


def analyze_size(width_cm: float, height_cm: float, period: str = None) -> DimensionResult:
    """维度4: 尺寸元数据分析"""
    result = DimensionResult(name="尺寸")

    if not width_cm and not height_cm:
        return result

    from app.services.inscription_content_analyzer import get_size_category
    size_cat = get_size_category(width_cm, height_cm)

    # 大幅偏正式（轻微积极），小幅偏随性（中性）
    size_scores = {"小幅": 0.0, "中幅": 0.1, "大幅": 0.2}
    score = size_scores.get(size_cat, 0.0)

    result.raw = score
    result.normalized = vader_normalize(score)
    result.has_data = True
    result.confidence = 0.5
    return result


def analyze_period(year: int, artist: str) -> DimensionResult:
    """维度5: 时期基线分析"""
    result = DimensionResult(name="时期")

    if not year:
        return result

    from app.services.inscription_content_analyzer import get_life_stage
    life_stage = get_life_stage(year, artist)

    score = life_stage.get("emotion_offset", 0)
    result.raw = score
    result.normalized = vader_normalize(score)
    result.has_data = score != 0
    result.confidence = 0.8 if result.has_data else 0.3
    return result


def analyze_seal(seal_content: str) -> DimensionResult:
    """维度6: 印章情感分析"""
    result = DimensionResult(name="印章")

    if not seal_content:
        return result

    from app.services.inscription_content_analyzer import analyze_seal_emotion
    seal_emotion = analyze_seal_emotion(seal_content)

    score = seal_emotion.get("composite_score", 0) or 0
    result.raw = score
    result.normalized = vader_normalize(score)
    result.has_data = seal_emotion.get("total_seals", 0) > 0
    result.confidence = 0.6 if result.has_data else 0.2
    result.signals = seal_emotion.get("signals", [])
    return result


def analyze_theme(themes: List[Dict], artist: str = None) -> DimensionResult:
    """维度7: 主题情感覆盖"""
    result = DimensionResult(name="主题")

    if not themes:
        return result

    from app.services.tibi_analysis_rules import THEME_SENTIMENT_OVERRIDE

    # 始终标记有数据（主题存在）
    result.has_data = True
    result.signals = []

    for theme in themes[:2]:  # 只看前两个主题
        theme_code = theme.get("code")
        theme_name = theme.get("name", "")
        confidence = theme.get("confidence", 0)

        override = THEME_SENTIMENT_OVERRIDE.get(theme_code)
        if override:
            polarity = override.get("polarity", "neutral")
            bonus = override.get("override_bonus", 0)
            result.signals.append({
                "theme": theme_name,
                "code": theme_code,
                "confidence": confidence,
                "polarity": polarity,
                "bonus": bonus,
                "has_override": True,
                "note": override.get("note", ""),
            })
            # 只有主主题的覆盖才生效
            if theme == themes[0]:
                result.raw = bonus
        else:
            result.signals.append({
                "theme": theme_name,
                "code": theme_code,
                "confidence": confidence,
                "polarity": "neutral",
                "bonus": 0,
                "has_override": False,
                "note": "无覆盖规则",
            })

    result.normalized = vader_normalize(result.raw)
    result.confidence = 0.9
    return result


def analyze_brush_ink() -> DimensionResult:
    """维度8: 笔墨质感（预留 — 待图形识别能力接入）"""
    return DimensionResult(name="笔墨", confidence=0.0)


def combine_dimensions(text: DimensionResult,
                       spatial: DimensionResult,
                       painting: DimensionResult,
                       size: DimensionResult,
                       period: DimensionResult,
                       seal: DimensionResult,
                       theme: DimensionResult,
                       brush_ink: DimensionResult = None,
                       weights: Dict[str, float] = None) -> tuple:
    """八维度加权融合

    Returns:
        (combined_raw, combined_normalized, polarity, dimension_polarities, conflict_score)
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    dims = [
        ("text", text, weights.get("text", 0.40)),
        ("spatial", spatial, weights.get("spatial", 0.20)),
        ("painting", painting, weights.get("painting", 0.10)),
        ("size", size, weights.get("size", 0.05)),
        ("period", period, weights.get("period", 0.10)),
        ("seal", seal, weights.get("seal", 0.10)),
        ("theme", theme, weights.get("theme", 0.05)),
        ("brush_ink", brush_ink or DimensionResult(name="笔墨"), weights.get("brush_ink", 0.00)),
    ]

    weighted_sum = 0.0
    weight_total = 0.0
    dimension_polarities = {}

    for name, dim, w in dims:
        effective_weight = w * dim.confidence
        weighted_sum += effective_weight * dim.raw
        weight_total += effective_weight
        # 记录每个维度的独立极性
        dimension_polarities[name] = classify_polarity(dim.normalized)

    if weight_total == 0:
        return 0.0, 0.0, "neutral", dimension_polarities, 0.0

    combined_raw = weighted_sum / weight_total
    combined_normalized = vader_normalize(combined_raw)
    conflict_score = compute_conflict_score([d[1] for d in dims])
    polarity = classify_complex_polarity(combined_normalized, dimension_polarities)

    return combined_raw, combined_normalized, polarity, dimension_polarities, conflict_score


def build_reasoning(text: DimensionResult,
                    spatial: DimensionResult,
                    seal: DimensionResult,
                    theme: DimensionResult,
                    polarity: str) -> str:
    """生成推理说明（返回 i18n key，前端用 $t() 翻译）"""
    parts = []

    def _label(dim: DimensionResult, name_key: str) -> str:
        if not dim.has_data:
            return f"{name_key}.no_data"
        p = classify_polarity(dim.normalized)
        return f"{name_key}.{p}"

    parts.append(_label(text, "reasoning.text"))
    parts.append(_label(spatial, "reasoning.spatial"))
    parts.append(_label(seal, "reasoning.seal"))

    if theme.has_data:
        theme_name = theme.signals[0].get("theme", "") if theme.signals else ""
        parts.append(f"reasoning.theme.{theme_name}")

    # 组合推理：用 | 分隔维度，最后加极性
    dimension_part = "|".join(parts)
    return f"{dimension_part}|reasoning.conclusion.{polarity}"


def analyze(text: str,
            spatial_emotion: Dict = None,
            painting_matches: List = None,
            width_cm: float = None,
            height_cm: float = None,
            year: int = None,
            artist: str = None,
            seal_content: str = None,
            themes: List = None,
            weights: Dict[str, float] = None) -> EngineResult:
    """
    主入口：八维度情感分析

    Returns:
        EngineResult: 包含各维度分数、综合分数、极性、推理
    """
    # 1. 文字
    text_dim = analyze_text(text)

    # 2. 空间
    spatial_dim = analyze_spatial(spatial_emotion)

    # 3. 画材
    painting_dim = analyze_painting(painting_matches)

    # 4. 尺寸
    size_dim = analyze_size(width_cm, height_cm)

    # 5. 时期
    period_dim = analyze_period(year, artist)

    # 6. 印章
    seal_dim = analyze_seal(seal_content)

    # 7. 主题
    theme_dim = analyze_theme(themes, artist)

    # 8. 笔墨（预留）
    brush_ink_dim = analyze_brush_ink()

    # 融合
    combined_raw, combined_normalized, polarity, dimension_polarities, conflict_score = combine_dimensions(
        text_dim, spatial_dim, painting_dim, size_dim,
        period_dim, seal_dim, theme_dim, brush_ink_dim, weights
    )

    # 推理
    reasoning = build_reasoning(text_dim, spatial_dim, seal_dim, theme_dim, polarity)

    return EngineResult(
        text=text_dim,
        spatial=spatial_dim,
        painting=painting_dim,
        size=size_dim,
        period=period_dim,
        seal=seal_dim,
        theme=theme_dim,
        brush_ink=brush_ink_dim,
        combined_raw=combined_raw,
        combined_normalized=combined_normalized,
        polarity=polarity,
        reasoning=reasoning,
        weights_used=weights or DEFAULT_WEIGHTS,
        dimension_polarities=dimension_polarities,
        conflict_score=conflict_score,
    )
