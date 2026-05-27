"""
墨林情绪引擎 v2.0
────────────────────────────────────────
七维度融合情感评分系统

维度:
1. 文字词典 (通用)
2. 空间布局 (通用)
3. 画材情感 (通用)
4. 尺寸元数据 (通用)
5. 时期基线 (特化)
6. 印章情感 (特化)
7. 主题覆盖 (特化)
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
    combined_raw: float = 0.0
    combined_normalized: float = 0.0
    polarity: str = "neutral"
    reasoning: str = ""
    weights_used: Dict[str, float] = field(default_factory=dict)


# ── 默认权重（校准后）──────────────────────────────────────
DEFAULT_WEIGHTS = {
    "text": 0.40,
    "spatial": 0.20,
    "painting": 0.10,
    "size": 0.05,
    "period": 0.10,
    "seal": 0.10,
    "theme": 0.05,
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
    """判断极性"""
    if normalized >= pos_threshold:
        return "positive"
    elif normalized <= neg_threshold:
        return "negative"
    return "neutral"


def analyze_text(text: str) -> DimensionResult:
    """维度1: 文字词典分析"""
    lexicon = get_lexicon()
    result = DimensionResult(name="文字")

    if not text:
        return result

    score = 0.0
    matched = []
    positions = set()

    # 最长匹配优先
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
    result.normalized = vader_normalize(score)
    result.has_data = len(matched) > 0
    result.confidence = 1.0 if result.has_data else 0.3
    result.signals = matched
    return result


def analyze_spatial(spatial_emotion: Dict) -> DimensionResult:
    """维度2: 空间布局分析"""
    result = DimensionResult(name="空间")

    if not spatial_emotion or not spatial_emotion.get("signals"):
        return result

    score = spatial_emotion.get("combined_spatial_score", 0) or 0
    result.raw = score
    result.normalized = vader_normalize(score)
    result.has_data = True
    result.confidence = 0.8
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

    primary_theme = themes[0] if themes else None
    if not primary_theme:
        return result

    theme_code = primary_theme.get("code")
    theme_name = primary_theme.get("name", "")

    # 查找主题覆盖规则
    override = THEME_SENTIMENT_OVERRIDE.get(theme_code)
    if not override:
        return result

    # 检查是否有例外关键词（暂不实现，需要原文）
    polarity = override.get("polarity", "neutral")
    bonus = override.get("override_bonus", 0)

    result.raw = bonus
    result.normalized = vader_normalize(bonus)
    result.has_data = True
    result.confidence = 0.9
    result.signals = [{"theme": theme_name, "polarity": polarity, "bonus": bonus}]
    return result


def combine_dimensions(text: DimensionResult,
                       spatial: DimensionResult,
                       painting: DimensionResult,
                       size: DimensionResult,
                       period: DimensionResult,
                       seal: DimensionResult,
                       theme: DimensionResult,
                       weights: Dict[str, float] = None) -> tuple:
    """七维度加权融合"""
    if weights is None:
        weights = DEFAULT_WEIGHTS

    dimensions = [
        ("text", text, weights.get("text", 0.40)),
        ("spatial", spatial, weights.get("spatial", 0.20)),
        ("painting", painting, weights.get("painting", 0.10)),
        ("size", size, weights.get("size", 0.05)),
        ("period", period, weights.get("period", 0.10)),
        ("seal", seal, weights.get("seal", 0.10)),
        ("theme", theme, weights.get("theme", 0.05)),
    ]

    weighted_sum = 0.0
    weight_total = 0.0

    for name, dim, w in dimensions:
        effective_weight = w * dim.confidence
        weighted_sum += effective_weight * dim.raw
        weight_total += effective_weight

    if weight_total == 0:
        return 0.0, 0.0, "neutral"

    combined_raw = weighted_sum / weight_total
    combined_normalized = vader_normalize(combined_raw)
    polarity = classify_polarity(combined_normalized)

    return combined_raw, combined_normalized, polarity


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
    主入口：七维度情感分析

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

    # 融合
    combined_raw, combined_normalized, polarity = combine_dimensions(
        text_dim, spatial_dim, painting_dim, size_dim,
        period_dim, seal_dim, theme_dim, weights
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
        combined_raw=combined_raw,
        combined_normalized=combined_normalized,
        polarity=polarity,
        reasoning=reasoning,
        weights_used=weights or DEFAULT_WEIGHTS,
    )
