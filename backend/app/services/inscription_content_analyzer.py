"""
题跋内容分析服务
- LLM主题分类（五大类）
- 情感分析（双通道：规则词表 + Qwen Turbo LLM）
- jieba分词统计
- 特征词提取

⚠️ 所有算法规则常量已迁移至 tibi_analysis_rules.py（唯一规则数据源）。
   升级算法版本时只修改该文件即可保证全局统一。
"""
import json
import re
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import httpx

from app.services.artist_context_registry import get_artist_birth_year, get_artist_display_name

# ── 从规则中心导入全部常量（唯一数据源） ──────────────────────────────────
from app.services.tibi_analysis_rules import (
    STOP_WORDS, FEATURE_WORDS, THEMES, THEME_NAME_MIGRATION,
    POSITIVE_WORDS, NEGATIVE_WORDS,
    LIFE_STAGE_TABLE, PAINTING_MATERIAL_RULES, TEXT_SCORING_RULES,
    EMOTION_SCORING, ARTIST_EMOTION_BASELINE, THEME_SENTIMENT_OVERRIDE,
    SIZE_CATEGORIES, SIZE_THEME_RULES, SIZE_PERIOD_MOOD_RULES, SIZE_INTERPRETATION,
    MATERIAL_KEYWORDS, GENERIC_SINGLE_CHARS,
    LLM_SENTIMENT_PROMPT, LLM_SENTIMENT_PROMPT_V3, LLM_THEME_PROMPT,
    LLM_COMBINED_PROMPT_V1, LLM_CONFLICT_RETRY_PROMPT, LLM_THEME_PROMPT_V3,
    ARTIST_SENTIMENT_NOTES, ARTIST_THEME_NOTES,
    RECIPIENT_MARKERS, SOCIAL_NO_RECIPIENT_DISCOUNT,
    DEFAULT_ARTIST_RULES, HARDCODED_ARTIST_RULES,
)


_cache_artist_rules: Dict[str, Dict] = {}
_cache_seal_emotion: Dict[str, Dict] = {}
_cache_seal_emotion_loaded: bool = False


def _load_artist_rules(artist_name: str) -> Dict:
    """加载画家规则：DB 优先 → 硬编码兜底 → 系统默认值"""
    if not artist_name:
        return dict(DEFAULT_ARTIST_RULES)
    if artist_name in _cache_artist_rules:
        return _cache_artist_rules[artist_name]

    try:
        from app.core.database import get_db_connection
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT * FROM artist_rules WHERE artist_name = ?", (artist_name,)
            ).fetchone()
            if row:
                rules = dict(row)
                for field in ["life_stages", "theme_exceptions", "seal_rules",
                               "expected_theme_distribution", "expected_sentiment_distribution"]:
                    if rules.get(field) and isinstance(rules[field], str):
                        try:
                            rules[field] = json.loads(rules[field])
                        except (json.JSONDecodeError, TypeError):
                            rules[field] = DEFAULT_ARTIST_RULES.get(field, {})
                _cache_artist_rules[artist_name] = rules
                return rules
        finally:
            conn.close()
    except Exception:
        pass

    rules = HARDCODED_ARTIST_RULES.get(artist_name, dict(DEFAULT_ARTIST_RULES))
    _cache_artist_rules[artist_name] = rules
    return rules


def _load_seal_emotion_cache() -> Dict[str, Dict]:
    """加载印章情感数据（带内存缓存，只查一次 DB）"""
    global _cache_seal_emotion_loaded
    if _cache_seal_emotion_loaded:
        return _cache_seal_emotion
    try:
        from app.core.database import get_db_connection
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT name, emotion_score, emotion_category, emotion_desc FROM seals "
                "WHERE emotion_score IS NOT NULL"
            ).fetchall()
            for r in rows:
                _cache_seal_emotion[r["name"]] = {
                    "score": r["emotion_score"],
                    "category": r["emotion_category"] or "unknown",
                    "desc": r["emotion_desc"] or "",
                    "emotion": _score_to_emotion_label(r["emotion_score"]),
                }
            _cache_seal_emotion_loaded = True
        finally:
            conn.close()
    except Exception:
        pass
    return _cache_seal_emotion


def _get_artist_sentiment_note(artist: str = None) -> str:
    """根据画家返回情感分析的特殊注意事项（DB优先 → 硬编码兜底）"""
    name = get_artist_display_name(artist) if artist else ""
    rules = _load_artist_rules(name)
    return rules.get("sentiment_note", "")


def _get_artist_theme_note(artist: str = None) -> Tuple[str, str]:
    """根据画家返回主题分析的特殊注意事项（DB优先 → 硬编码兜底）"""
    name = get_artist_display_name(artist) if artist else ""
    rules = _load_artist_rules(name)
    return (rules.get("theme_note", ""), "")

# jieba 中文分词
import jieba

# ── 所有规则常量已迁移至 tibi_analysis_rules.py ────────────────────────

def get_size_category(width_cm: float = None, height_cm: float = None) -> str:
    """根据高度判断尺寸分组"""
    if not height_cm:
        return "未知"
    if height_cm < 70:
        return "小幅"
    elif height_cm <= 150:
        return "中幅"
    else:
        return "大幅"


def get_size_interpretation(size_category: str, period: str = None) -> str:
    """获取尺寸解读语料"""
    if size_category == "未知":
        return ""
    interp = SIZE_INTERPRETATION.get(size_category, {})
    if period and period in interp:
        return interp[period]
    return interp.get("通用", "")


def _extract_material_category_from_title(title: str, analysis_note: str = None) -> List[str]:
    """从标题和AI画材分析中提取画材类别（匹配 SIZE_THEME_RULES 中的 materials）"""
    material_categories = []
    category_keywords = {
        "吉祥": ["牡丹", "松柏", "松藤", "松石", "长寿", "百子", "富贵", "荣华", "多寿", "长年"],
        "四君子": ["梅", "兰", "竹", "菊", "松", "岁寒三友"],
        "墨荷": ["荷", "莲", "残荷"],
        "山水": ["山水", "泉", "溪"],
        "鱼虾": ["鱼", "虾", "蟹"],
        "蔬果": ["蔬", "果", "葱", "蒜", "姜", "白菜", "萝卜"],
        "祝寿": ["寿", "松鹤", "仙鹤", "鹤"],
    }
    combined = f"{title or ''} {analysis_note or ''}"
    for category, keywords in category_keywords.items():
        if any(kw in combined for kw in keywords):
            material_categories.append(category)
    return list(set(material_categories))


# ══════════════════════════════════════════════════════════════════════
# v4 核心函数
# ══════════════════════════════════════════════════════════════════════

def get_life_stage(year: int, artist: str = None) -> Dict:
    """
    查表1：年份 → 人生阶段 + 基线情感 + 权重
    优先使用 DB 中画家的 life_stages 规则，兜底用 LIFE_STAGE_TABLE
    返回 {"stage": ..., "baseline_emotion": ..., "emotion_offset": ..., "weight": ..., "description": ...}
    """
    artist_name = get_artist_display_name(artist) if artist else ""
    rules = _load_artist_rules(artist_name)
    life_stages = rules.get("life_stages", [])

    if year is not None and life_stages:
        for stage in life_stages:
            start = stage.get("year_start", 0)
            end = stage.get("year_end", 0)
            if start <= year <= end:
                return {
                    "stage": stage.get("name", "未知"),
                    "baseline_emotion": "中立",
                    "emotion_offset": stage.get("mood_offset", 0.0),
                    "weight": stage.get("weight", 1.0),
                    "description": stage.get("description", ""),
                }

    if year is None:
        return {
            "stage": "未知",
            "baseline_emotion": "中立",
            "emotion_offset": 0.0,
            "weight": 1.0,
            "description": "无年份信息",
        }
    for (start, end), info in LIFE_STAGE_TABLE.items():
        if start <= year <= end:
            return info
    if year < 1714:
        return LIFE_STAGE_TABLE[(1714, 1722)]
    return LIFE_STAGE_TABLE[(1746, 1760)]


def match_painting_materials(
    title: str = None,
    analysis_note: str = None,
    inscription_content: str = None,
) -> List[Dict]:
    """
    查表2：画作标题 + AI画材分析 + 题跋文本 → 匹配题材规则
    三来源分别匹配，带权重：
      - 题跋 (inscription_content): 权重 1.0（作者自书，最可信）
      - 标题 (title):             权重 0.8（通常准确但简短）
      - 图像分析 (analysis_note): 权重 0.5（AI识别，可能误判）
    返回：
      [{
        "rule": {...},
        "matched_keywords": [...],
        "source": "inscription(×1.0)+title(×0.8)" 等,
        "weight_multiplier": 1.0,
      }, ...]
    """
    sources = [
        (inscription_content, "inscription", 1.0),
        (title,              "title",        0.8),
        (analysis_note,      "analysis_note", 0.5),
    ]
    # 去重：同一规则可能被多个来源匹配，合并为一条记录
    rule_best: Dict[int, Dict] = {}  # index in PAINTING_MATERIAL_RULES → merged match

    for text, source_name, weight_multiplier in sources:
        if not text:
            continue
        for idx, rule in enumerate(PAINTING_MATERIAL_RULES):
            matched_kw = [kw for kw in rule["keywords"] if kw in text]
            if not matched_kw:
                continue
            if idx not in rule_best:
                rule_best[idx] = {
                    "rule": rule,
                    "matched_keywords": list(matched_kw),
                    "sources": [(source_name, weight_multiplier)],
                    "max_multiplier": weight_multiplier,
                }
            else:
                existing = rule_best[idx]
                for kw in matched_kw:
                    if kw not in existing["matched_keywords"]:
                        existing["matched_keywords"].append(kw)
                existing["sources"].append((source_name, weight_multiplier))
                existing["max_multiplier"] = max(existing["max_multiplier"], weight_multiplier)

    # 转成最终格式
    matches = []
    for entry in rule_best.values():
        final_multiplier = entry["max_multiplier"]
        source_summary = "+".join(
            f"{s}(×{w})" for s, w in entry["sources"]
        )
        matches.append({
            "rule": entry["rule"],
            "matched_keywords": entry["matched_keywords"],
            "source": source_summary,
            "weight_multiplier": final_multiplier,
        })
    return matches


def score_text_keywords(text: str) -> Tuple[Dict[int, float], float, List[Dict]]:
    """
    查表3：文本关键词扫描 → 主题得分 + 情感分值 + 情感明细
    返回 (theme_scores, emotion_score, emotion_details)
    - theme_scores: {theme_code: score, ...}
    - emotion_score: 连续值（正=积极，负=消极）
    - emotion_details: [{"word": "...", "score": -1.8, "category": "negative_life"}, ...]

    评分优先级：emotion_lexicon > EMOTION_SCORING（向后兼容）
    """
    from app.services.emotion_lexicon_loader import get_lexicon
    lexicon = get_lexicon()

    theme_scores = {}
    # 各主题基础分
    for code, rule in TEXT_SCORING_RULES.items():
        base = rule.get("base_score", 0)
        if base > 0:
            theme_scores[code] = base

    # 关键词匹配累加
    for code, rule in TEXT_SCORING_RULES.items():
        kw_dict = rule.get("keywords", {})
        for kw, score in kw_dict.items():
            if kw in text:
                theme_scores[code] = theme_scores.get(code, 0) + score

    # 情感分值计算 + 明细记录（最长匹配优先，避免重复计数）
    emotion_score = 0.0
    emotion_details: List[Dict] = []
    matched_positions = set()  # 记录已匹配的字符位置

    # 收集所有候选词，按长度降序排列（最长匹配优先）
    all_candidates = []
    for word in lexicon.get_all_words():
        all_candidates.append(word)
    for category, config in EMOTION_SCORING.items():
        for word in config["words"]:
            if not lexicon.has_word(word):
                all_candidates.append(word)
    all_candidates.sort(key=len, reverse=True)

    for word in all_candidates:
        # 检查是否与已匹配位置重叠
        pos = text.find(word)
        if pos >= 0:
            word_positions = set(range(pos, pos + len(word)))
            if not word_positions & matched_positions:  # 无重叠
                matched_positions.update(word_positions)

                # 优先用词典分数
                lex_score = lexicon.get_score(word)
                if lex_score is not None:
                    emotion_score += lex_score
                    emotion_details.append({
                        "word": word,
                        "score": lex_score,
                        "category": lexicon.get_category(word) or "unknown",
                        "source": "lexicon",
                    })
                else:
                    # 回退到 EMOTION_SCORING
                    for category, config in EMOTION_SCORING.items():
                        if word in config["words"]:
                            emotion_score += config["score"]
                            emotion_details.append({
                                "word": word,
                                "score": config["score"],
                                "category": category,
                                "source": "legacy",
                            })
                            break

    # 自嘲检测：反转"笑"在自嘲语境下的正向贡献
    SELF_MOCK_PATTERNS = ["莫笑", "堪笑", "自笑", "一笑", "休笑", "人笑", "应笑", "可笑"]
    has_self_mock = any(p in text for p in SELF_MOCK_PATTERNS)
    if has_self_mock:
        for det in emotion_details:
            if det["word"] == "笑":
                emotion_score -= det["score"]
                emotion_score += -1.5
                det["score"] = -1.5
                det["word"] = "笑(自嘲)"
                det["category"] = "negative_self_mock"

    return theme_scores, emotion_score, emotion_details


def classify_inscription_v4(
    text: str,
    year: int = None,
    title: str = None,
    analysis_note: str = None,
    inscription_content: str = None,
    width_cm: float = None,
    height_cm: float = None,
    artist: str = None,
) -> Dict:
    """
    v4 多维信号融合分类器
    ─────────────────────────────────
    四个信号维度：
    1. 时间信号：year → 人生阶段 → 基线情感修正
    2. 画作内容信号：title + analysis_note → 题材匹配 → 主题/情感倾向
    3. 文本信号：关键词扫描 → 主题得分累加 + 情感分值
    4. 尺寸信号：width_cm + height_cm → 尺寸分组 → 主题/心境权重

    返回：
    {
        "themes": [{"code": 1, "name": "...", "confidence": 0.9, "score": 3.0}, ...],
        "sentiment": {
            "polarity": "positive"|"negative"|"neutral",
            "emotion_score": 1.5,  # 连续值，用于时间序列分析
            "reasoning": "..."
        },
        "signals": {
            "time": {...},        # 时间信号明细
            "painting": [...],    # 画作内容信号明细
            "text": {...},        # 文本信号明细
            "size": {...},        # 尺寸信号明细
        },
        "special_rules": [...],   # 触发的特殊规则
    }
    """
    signals = {"time": {}, "painting": [], "text": {}, "size": {}}
    special_rules = []
    emotion_rules = []  # 追踪影响情感分数的规则（text, offset）

    # inscription_content fallback：若未传入，使用 text（题跋正文）
    if inscription_content is None:
        inscription_content = text

    # ── 维度1：时间信号 ──────────────────────────────────────────
    life_stage = get_life_stage(year, artist)
    signals["time"] = {
        "year": year,
        "stage": life_stage["stage"],
        "baseline_emotion": life_stage["baseline_emotion"],
        "emotion_offset": life_stage["emotion_offset"],
        "weight": life_stage["weight"],
    }

    # ── 维度2：画作内容信号 ──────────────────────────────────────
    painting_matches = match_painting_materials(title, analysis_note, inscription_content)
    painting_theme_scores = {}
    painting_emotion_offset = 0.0
    for match in painting_matches:
        rule = match["rule"]
        code = rule["theme_tendency"]
        # 画作内容信号：0.7 * weight * weight_multiplier（题跋命中权重更高）
        multiplier = match.get("weight_multiplier", 1.0)
        painting_theme_scores[code] = painting_theme_scores.get(code, 0) + rule["weight"] * 0.7 * multiplier
        painting_emotion_offset += rule["emotion_offset"] * multiplier
        signals["painting"].append({
            "matched_keywords": match["matched_keywords"],
            "visual_emotion": rule["visual_emotion"],
            "theme_tendency": THEMES[code]["name"],
            "weight": rule["weight"],
            "source": match.get("source", "unknown"),
            "weight_multiplier": multiplier,
        })

    # ── 维度3：文本信号 ──────────────────────────────────────────
    text_theme_scores, text_emotion_score, text_emotion_details = score_text_keywords(text or "")
    signals["text"] = {
        "theme_scores": {str(k): v for k, v in text_theme_scores.items()},
        "emotion_score": text_emotion_score,
    }

    # ── 维度4：尺寸信号 ──────────────────────────────────────────
    size_theme_boost = {}  # 主题权重加成
    size_sentiment_modifier = 1.0  # 情感极性修正
    size_mood_tag = None
    size_category = "未知"
    period_phase = get_period_phase(year, artist)
    material_categories = []
    
    if width_cm or height_cm:
        size_category = get_size_category(width_cm, height_cm)
        material_categories = _extract_material_category_from_title(title or "", analysis_note)
        size_signals = []
        
        # 尺寸×题材→主题权重
        for rule in SIZE_THEME_RULES:
            cond = rule["condition"]
            if cond["size"] == size_category:
                # 检查题材关键词匹配（material_categories 与 rule 中 materials 的交集）
                matched_materials = [m for m in material_categories if m in cond.get("materials", [])]
                if matched_materials:
                    for theme_code, boost in rule["theme_boost"].items():
                        size_theme_boost[theme_code] = size_theme_boost.get(theme_code, 0) + boost
                    size_signals.append(f"{rule['description']}")
        
        # 尺寸×分期→心境权重
        for rule in SIZE_PERIOD_MOOD_RULES:
            cond = rule["condition"]
            if cond["size"] == size_category and cond["period"] == period_phase:
                if "theme_boost" in rule:
                    for theme_code, boost in rule["theme_boost"].items():
                        size_theme_boost[theme_code] = size_theme_boost.get(theme_code, 0) + boost
                if "sentiment_modifier" in rule:
                    size_sentiment_modifier = rule["sentiment_modifier"]
                if "mood_tag" in rule:
                    size_mood_tag = rule["mood_tag"]
                size_signals.append(f"{rule['description']}")
        
        signals["size"] = {
            "size_category": size_category,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "material_categories": material_categories,
            "period": period_phase,
            "theme_boost": size_theme_boost,
            "sentiment_modifier": size_sentiment_modifier,
            "mood_tag": size_mood_tag,
            "signals": size_signals,
            "interpretation": get_size_interpretation(size_category, period_phase),
        }

    # ── 信号融合 ─────────────────────────────────────────────────
    # 合并主题得分：文本分 + 画作内容分 + 尺寸分
    merged_scores = {}
    for code, score in text_theme_scores.items():
        merged_scores[code] = merged_scores.get(code, 0) + score
    for code, score in painting_theme_scores.items():
        merged_scores[code] = merged_scores.get(code, 0) + score
    # 新增：尺寸信号主题权重加成
    for code, boost in size_theme_boost.items():
        merged_scores[code] = merged_scores.get(code, 0) + boost

    # 合并情感分值：文本情感为基底，时间/画作/尺寸作为修正
    # 时间修正：当文本本身有消极信号时放大，无消极信号时微调
    emotion_score = text_emotion_score
    if text_emotion_score < 0:
        # 文本已有消极信号 → 时间偏移放大（乘法）
        emotion_score += life_stage["emotion_offset"] * 1.5
    else:
        # 文本无消极信号 → 时间偏移微调（不强制覆盖文本信号）
        emotion_score += life_stage["emotion_offset"] * 0.3
    emotion_score += painting_emotion_offset
    # 新增：尺寸情感修正（加法修正，小幅偏移方向）
    emotion_score += size_sentiment_modifier

    # ── 特殊规则 ─────────────────────────────────────────────────

    # 规则A：时事讽喻锁定 — 需要足够强的信号
    # v5: 主题编码4=时事讽喻
    satire_score = merged_scores.get(4, 0)
    # 检查是否有强讽喻词（2分及以上）
    strong_satire_keywords = ["催租", "舆隶", "官粮", "纨绔", "夺朱", "世味辣", "卖画难",
                              "官吏", "赋税", "纨绔子弟", "恶态", "苍生", "民生",
                              "世味", "豪家", "冷落", "簪缨", "挥毫卖", "寻纸",
                              "索画", "催诗", "催画", "艰难", "恼客魂", "俗尘",
                              "衣食", "画贱", "世间", "天下"]
    has_strong_satire = any(kw in (text or "") for kw in strong_satire_keywords)
    # 锁定条件：有强词且>=2，或无强词但>=3
    should_lock_satire = (has_strong_satire and satire_score >= 2) or (not has_strong_satire and satire_score >= 3)
    if should_lock_satire:
        special_rules.append(f"时事讽喻得分={satire_score}，直接锁定时事讽喻主题")
        # 移除咏物寄兴的分数（被覆盖）
        if 2 in merged_scores:
            del merged_scores[2]
        emotion_score -= 1.5  # 讽喻消极修正

    # 规则A2：身世自况锁定 — 李鱓标志性意象
    # v5: 主题编码1=身世自况
    self_ref_score = merged_scores.get(1, 0)
    # v5.3: 同步移除"懊道人"——落款署名不作为锁定依据
    strong_selfref_keywords = ["臣非老画师", "两革科名", "一贬官", "老夫卖画",
                                "落拓", "潦倒", "落魄", "穷愁", "罢官", "科名"]
    has_strong_selfref = any(kw in (text or "") for kw in strong_selfref_keywords)
    should_lock_selfref = (has_strong_selfref and self_ref_score >= 3) or (self_ref_score >= 5)
    if should_lock_selfref:
        special_rules.append(f"身世自况得分={self_ref_score}，锁定身世自况主题")
        # 身世自况优先级高于咏物寄兴
        if 2 in merged_scores and merged_scores.get(2, 0) < self_ref_score:
            del merged_scores[2]

    # 规则A3：老夫+困顿词组合 → 身世自况加分（李鱓经典自况模式）
    text_lower = text or ""
    has_laofu = "老夫" in text_lower
    hardship_words = ["寒", "难", "苦", "醉", "卖", "贫", "困", "泣", "湿"]
    has_hardship = any(w in text_lower for w in hardship_words)
    if has_laofu and has_hardship:
        merged_scores[1] = merged_scores.get(1, 0) + 2  # v5: 1=身世自况
        special_rules.append("老夫+困顿词组合 → 身世自况加分")

    # 规则A4：世味/豪家+冷落 → 时事讽喻加分（社会批判模式）
    social_critique_pairs = [
        (["世味"], ["辣", "苦", "寒", "知"]),
        (["豪家", "富贵"], ["冷落", "笑", "争"]),
        (["簪缨", "纨绔"], ["恶态", "问", "子弟"]),
    ]
    for triggers, modifiers in social_critique_pairs:
        has_trigger = any(t in text_lower for t in triggers)
        has_modifier = any(m in text_lower for m in modifiers)
        if has_trigger and has_modifier:
            merged_scores[4] = merged_scores.get(4, 0) + 2  # v5: 4=时事讽喻
            special_rules.append(f"社会批判模式({triggers[0]}+{modifiers[0]}) → 时事讽喻加分")
            break

    # 规则B：文本<10字且无强特征词 → 归为咏物寄兴（而非"记录创作信息"）
    # v5: 文人画无"纯记录"，短题跋默认借物寄兴
    char_count_val = count_chars(text or "")
    has_strong_signal = any(merged_scores.get(c, 0) >= 1.5 for c in [1, 2, 3, 4, 5, 6])
    if char_count_val < 10 and not has_strong_signal:
        special_rules.append("文本<10字且无强特征词，默认咏物寄兴")
        merged_scores = {2: 3}  # v5: 2=咏物寄兴
        emotion_score = 0  # 强制中立

    # 规则C：蔬果+辣/蒜 → 咏物寄兴加分（李鱓"取材之广"是文人特质）
    # v5: 蔬果从"吉语祥瑞"改为"咏物寄兴"
    painting_text = f"{title or ''} {analysis_note or ''}"
    if any(kw in painting_text for kw in ["蔬果", "葱", "蒜", "姜", "白菜", "萝卜", "茄", "瓜", "茭白"]):
        if any(kw in (text or "") for kw in ["辣", "蒜", "葱"]):
            merged_scores[2] = merged_scores.get(2, 0) + 1.5  # v5: 2=咏物寄兴
            special_rules.append("蔬果+辣/蒜 → 咏物寄兴加分（日常物中见性情）")

    # 规则D：交游赠答需明确受赠人（"写/摹/作"不等于应酬）
    # 受赠人标记和降权系数从规则中心读取
    if merged_scores.get(6, 0) > 0:
        has_recipient = any(m in (text or "") for m in RECIPIENT_MARKERS)
        if not has_recipient:
            merged_scores[6] = merged_scores[6] * SOCIAL_NO_RECIPIENT_DISCOUNT
            special_rules.append("无明确受赠人，交游赠答得分降权")

    # ── 画家情感基线修正 ─────────────────────────────────────────────
    # v5.4: 基线修正系数按分期差异化——晚期更强，早期更弱
    artist_name = get_artist_display_name(artist) if artist else ""
    artist_rules = _load_artist_rules(artist_name)
    baseline = artist_rules.get("emotion_baseline", 0.0)
    if baseline != 0.0:
        if abs(text_emotion_score) < 1.5:
            stage_name = life_stage.get("stage", "")
            if stage_name.startswith("早期"):
                baseline_factor = 0.15
            elif stage_name.startswith("晚期"):
                baseline_factor = 0.6
            elif stage_name.startswith("中期"):
                baseline_factor = 0.4
            else:
                baseline_factor = 0.3  # 未知分期，用默认值
            emotion_score += baseline * baseline_factor
            _offset = round(baseline * baseline_factor, 2)
            special_rules.append(f"画家情感基线修正: {artist_name} baseline={baseline}, factor={baseline_factor}")
            emotion_rules.append({"text": f"画家底色 {artist_name} {baseline}×{baseline_factor}", "offset": _offset})

    # ── 生成主题结果 ─────────────────────────────────────────────
    # 按得分排序，取前3个非零主题
    sorted_themes = sorted(merged_scores.items(), key=lambda x: x[1], reverse=True)

    themes_result = []
    for code, score in sorted_themes:
        if score <= 0:
            continue
        # 置信度：基于得分归一化
        if score >= 5:
            confidence = 0.9
        elif score >= 3:
            confidence = 0.8
        elif score >= 2:
            confidence = 0.7
        elif score >= 1:
            confidence = 0.6
        else:
            confidence = 0.5
        # 第一主题至少0.5
        if len(themes_result) == 0:
            confidence = max(confidence, 0.5)
        # 后续主题按与第一主题的得分比降权
        if themes_result:
            ratio = score / max(themes_result[0]["score"], 0.01)
            confidence = min(confidence * ratio, 0.9)
        # 尺寸boost置信度折扣：纯boost贡献的主题比有文本/画作信号的置信度低
        if code in size_theme_boost and size_theme_boost[code] > 0:
            boost_score = size_theme_boost[code]
            boost_ratio = min(boost_score / max(score, 0.01), 1.0)
            confidence *= (0.5 + 0.5 * (1 - boost_ratio))
        themes_result.append({
            "code": code,
            "name": THEMES[code]["name"],
            "confidence": round(confidence, 2),
            "score": round(score, 2),
        })
        if len(themes_result) >= 3:
            break

    # v5: 无主题时默认咏物寄兴（而非记录创作信息）
    if not themes_result:
        themes_result = [{"code": 2, "name": "咏物寄兴", "confidence": 0.5, "score": 1.0}]

    # ── 主题-情感关联修正（最后一步，优先级最高） ─────────────────
    main_theme_code = None
    if themes_result:
        main_theme_code = themes_result[0]["code"]
    
    theme_sentiment_applied = False
    if main_theme_code and main_theme_code in THEME_SENTIMENT_OVERRIDE:
        override_rule = THEME_SENTIMENT_OVERRIDE[main_theme_code]

        # v5.5: 合并 DB 中的画家特殊例外优先级高于规则中心
        db_exceptions = artist_rules.get("theme_exceptions", {})
        merged_exception = dict(override_rule.get("artist_exception", {}))
        if str(main_theme_code) in db_exceptions:
            db_exc = db_exceptions[str(main_theme_code)]
            merged_exception[artist_name] = db_exc

        if artist_name in merged_exception:
            exc = merged_exception[artist_name]
            if any(kw in (text or "") for kw in exc.get("override_if_contains", [])):
                special_rules.append(f"画家特殊例外: {artist_name} 含{exc['override_if_contains']}，极性反转")
                emotion_score -= 3.0
                emotion_rules.append({"text": f"画家例外反转 {artist_name}", "offset": -3.0})
                theme_sentiment_applied = True
            else:
                special_rules.append(override_rule["note"])
                _bonus = override_rule["override_bonus"]
                emotion_score += _bonus
                emotion_rules.append({"text": override_rule["note"], "offset": round(_bonus, 2)})
                if override_rule["polarity"] == "negative" and emotion_score > override_rule["min_score"]:
                    emotion_score = min(emotion_score, override_rule["min_score"])
                theme_sentiment_applied = True
        else:
            special_rules.append(override_rule["note"])
            _bonus = override_rule["override_bonus"]
            emotion_score += _bonus
            emotion_rules.append({"text": override_rule["note"], "offset": round(_bonus, 2)})
            if override_rule["polarity"] == "negative" and emotion_score > override_rule["min_score"]:
                emotion_score = min(emotion_score, override_rule["min_score"])
            theme_sentiment_applied = True

    # ── 生成情感结果 ─────────────────────────────────────────────
    if emotion_score > 0.5:
        polarity = "positive"
    elif emotion_score < -0.5:
        polarity = "negative"
    else:
        polarity = "neutral"
    
    # 主题强制极性（兜底）
    if theme_sentiment_applied and main_theme_code in THEME_SENTIMENT_OVERRIDE:
        override_rule = THEME_SENTIMENT_OVERRIDE[main_theme_code]
        merged_exception = dict(override_rule.get("artist_exception", {}))
        db_exceptions = artist_rules.get("theme_exceptions", {})
        if str(main_theme_code) in db_exceptions:
            merged_exception[artist_name] = db_exceptions[str(main_theme_code)]
        if artist_name in merged_exception and any(kw in (text or "") for kw in merged_exception[artist_name].get("override_if_contains", [])):
            polarity = "negative"
        else:
            polarity = override_rule["polarity"]

    sentiment_result = {
        "polarity": polarity,
        "emotion_score": round(emotion_score, 2),
        "reasoning": _build_sentiment_reasoning(polarity, emotion_score, life_stage, painting_matches, special_rules),
        "reasoning_steps": _build_sentiment_reasoning_steps(
            polarity, round(emotion_score, 2), life_stage, painting_matches,
            special_rules, text_emotion_score, baseline, artist_name,
            text_emotion_details, emotion_rules
        ),
    }

    return {
        "themes": themes_result,
        "sentiment": sentiment_result,
        "signals": signals,
        "special_rules": special_rules,
        "confidence": compute_confidence(themes_result, sentiment_result, signals, special_rules),
    }


def compute_confidence(themes: list, sentiment: dict, signals: dict, special_rules: list) -> float:
    """
    计算规则引擎输出的综合置信度（0~1）。
    用于决定是否需要 LLM 二次分析。

    六个维度：
    1. 主题信号差距（权重 0.25）：最高主题分与第二高分的差距
    2. 情感信号强度（权重 0.20）：emotion_score 绝对值
    3. 信号来源多样性（权重 0.15）：time/painting/text/size 触发数
    4. 特殊规则触发（权重 0.15）：人工先验加持
    5. 文本有效信号量（权重 0.15）：实际匹配的关键词和信号数
    6. 推导步骤完整性（权重 0.10）：reasoning_steps 数量
    """
    score = 0.0

    # 1. 主题信号差距（25%）
    top_scores = sorted([t.get("score", 0) for t in themes], reverse=True)
    if len(top_scores) >= 2:
        gap = top_scores[0] - top_scores[1]
    elif top_scores:
        gap = top_scores[0]
    else:
        gap = 0
    score += min(gap / 5.0, 1.0) * 0.25

    # 2. 情感信号强度（20%）
    es = abs(sentiment.get("emotion_score", 0))
    score += min(es / 4.0, 1.0) * 0.20

    # 3. 信号来源多样性（15%）
    sig_count = 0
    if signals.get("time", {}).get("year"):
        sig_count += 1
    if signals.get("painting") and len(signals["painting"]) > 0:
        sig_count += 1
    text_scores = signals.get("text", {}).get("theme_scores", {})
    if text_scores and any(float(v) > 0 for v in text_scores.values()):
        sig_count += 1
    if signals.get("size", {}).get("width_cm") or signals.get("size", {}).get("height_cm"):
        sig_count += 1
    score += min(sig_count / 4.0, 1.0) * 0.15

    # 4. 文本有效信号量（15%）—— 实际匹配到的关键词和规则数，惩罚空文本
    text_emotion_score = abs(float(signals.get("text", {}).get("emotion_score", 0)))
    # 统计 theme_scores 中有多少主题非零
    active_theme_count = sum(1 for v in text_scores.values() if float(v) > 0) if text_scores else 0
    # 信号越丰富得分越高，0 个活跃主题 → 0
    signal_richness = (min(active_theme_count / 4.0, 1.0) * 0.6 + min(text_emotion_score / 3.0, 1.0) * 0.4)
    score += signal_richness * 0.15

    # 5. 特殊规则触发（15%）
    has_special = len(special_rules) > 0
    score += (1.0 if has_special else 0.3) * 0.15

    # 6. 推导步骤完整性（10%）
    steps = len(sentiment.get("reasoning_steps", []))
    score += min(steps / 5.0, 1.0) * 0.10

    return round(score, 2)


def _build_sentiment_reasoning(polarity, emotion_score, life_stage, painting_matches, special_rules) -> str:
    """构建情感判断理由（兼容旧格式）"""
    parts = []
    if life_stage.get("stage") and life_stage["stage"] != "未知":
        parts.append(f"{life_stage['stage']}({life_stage['baseline_emotion']})")
    if painting_matches:
        emotions = list(set(m["rule"]["visual_emotion"] for m in painting_matches))
        parts.append(f"画材:{'/'.join(emotions)}")
    parts.append(f"情感分={emotion_score:.1f}")
    if special_rules:
        parts.append(special_rules[0][:30])
    return "；".join(parts)


def _build_sentiment_reasoning_steps(
    polarity, emotion_score, life_stage, painting_matches,
    special_rules, text_emotion_score, artist_baseline, artist_name,
    text_emotion_details=None, emotion_rules=None
) -> list:
    """
    构建结构化推导步骤，用于前端分步展示。
    返回 [{"label": "时期基线", "detail": "...", "offset": +0.63, "icon": "📅"}, ...]
    """
    steps = []

    # 步骤1：时期基线
    if life_stage.get("stage") and life_stage["stage"] != "未知":
        offset = life_stage.get("emotion_offset", 0)
        steps.append({
            "label": "时期基线",
            "detail": f"{life_stage['stage']}作品，情感偏{life_stage.get('baseline_emotion', '中性')}",
            "offset": round(offset, 2),
            "icon": "📅",
        })

    # 步骤2：画材情感
    if painting_matches:
        emotions = list(set(m["rule"]["visual_emotion"] for m in painting_matches))
        painting_offset = sum(m["rule"].get("emotion_offset", 0) for m in painting_matches)
        steps.append({
            "label": "画材情感",
            "detail": f"画面元素→{'、'.join(emotions)}",
            "offset": round(painting_offset, 2),
            "icon": "🎨",
        })

    # 步骤3：文本情感 —— 用具体词替代硬编码说明
    if text_emotion_details:
        # 按分数绝对值排序，取前5个最具代表性的词
        sorted_details = sorted(text_emotion_details, key=lambda d: abs(d["score"]), reverse=True)[:5]
        word_parts = [f'"{d["word"]}"({d["score"]:+.1f})' for d in sorted_details]
        detail_text = f"题跋中出现 {'、'.join(word_parts)}"
    else:
        detail_text = "题跋中无明显情感倾向词"
    steps.append({
        "label": "文本情感",
        "detail": detail_text,
        "offset": round(text_emotion_score, 2) if text_emotion_score else 0,
        "icon": "📝",
    })

    # 步骤4：画家底色
    if artist_baseline and artist_baseline != 0:
        steps.append({
            "label": "画家底色",
            "detail": f"{artist_name}的创作风格底色",
            "offset": round(artist_baseline, 2),
            "icon": "🖌️",
        })

    # 步骤5：特殊规则（只展示影响情感分数的规则）
    if emotion_rules:
        # 合并显示所有情感相关规则的偏移
        total_emotion_offset = sum(r["offset"] for r in emotion_rules)
        detail_parts = [f'{r["text"]}({r["offset"]:+.2f})' for r in emotion_rules]
        steps.append({
            "label": "特殊规则",
            "detail": " + ".join(detail_parts),
            "offset": round(total_emotion_offset, 2),
            "icon": "⚡",
        })

    # 最终判定
    polarity_cn = {"positive": "积极", "negative": "消极", "neutral": "中性"}.get(polarity, "中性")
    steps.append({
        "label": "最终判定",
        "detail": f"综合得分 {emotion_score:+.2f} → {polarity_cn}",
        "offset": None,  # 最终结果，不显示偏移
        "icon": "✅" if polarity == "positive" else "❌" if polarity == "negative" else "➖",
    })

    return steps


# ── 空间情绪分析 ────────────────────────────────────────────────────────────────
def analyze_spatial_emotion(
    position_analysis: Dict,
    blank_percent: float,
    inscription_coverage: float = None,
) -> Dict:
    """
    基于论文框架，将题跋位置类型 + 留白比例映射为情感信号。

    Args:
        position_analysis: analyze_inscription_position_simple() 的输出
        blank_percent: 留白百分比 (0-100)
        inscription_coverage: 题跋覆盖率 (0-1)，可选

    Returns:
        {
            "signals": [{"type": "拦边封角式", "emotion": "克制收敛", "desc": "..."}],
            "blank_analysis": "...",
            "combined_spatial_sentiment": "...",
            "blank_percent": 52.3,
            "coverage_ratio": 0.08,
        }
    """
    from app.services.tibi_analysis_rules import SPATIAL_EMOTION_RULES

    form_emotion_map = SPATIAL_EMOTION_RULES["form_emotion_map"]
    blank_modifiers = SPATIAL_EMOTION_RULES["blank_modifiers"]
    emotion_label = SPATIAL_EMOTION_RULES["emotion_label"]

    coverage = inscription_coverage
    if coverage is None and position_analysis:
        coverage = position_analysis.get("coverage_ratio", 0)

    signals = []
    form_types = position_analysis.get("form_types", []) if position_analysis else []

    # 从匹配的布局类型提取情感信号
    for ft in form_types:
        if not ft.get("matched"):
            continue
        code = ft.get("code")
        if code and code in form_emotion_map:
            em = form_emotion_map[code]
            signals.append({
                "type": ft.get("name", ""),
                "code": code,
                "emotion": emotion_label.get(em["emotion"], em["emotion"]),
                "emotion_key": em["emotion"],
                "score": em.get("score", 0.0),
                "desc": em["desc"],
            })

    # 留白修正
    blank_desc = ""
    blank_mod = 0.0
    b = blank_percent if blank_percent is not None else 50
    c = coverage if coverage is not None else 0.1
    for rule in blank_modifiers:
        try:
            if rule["cond"](b, c):
                blank_desc = rule["desc"]
                blank_mod = rule["modifier"]
                break
        except Exception:
            continue

    if not blank_desc:
        if b >= 50:
            blank_desc = "留白充足，画面气息舒展从容"
        elif b >= 30:
            blank_desc = "留白适中，布局均衡"
        else:
            blank_desc = "留白偏少，画面饱满紧凑"

    # 综合空间情感判断 — 取最极端的情绪，而非第一个
    if not signals:
        combined = "无题跋标注，无法分析空间情绪"
    else:
        # 情绪优先级：intense > 其他
        priority = {"negative_intense": 5, "positive_unrestrained": 5,
                     "negative_controlled": 3, "positive_defiant": 3,
                     "positive_resolved": 2, "negative": 2, "positive": 2,
                     "neutral_controlled": 1, "neutral_balanced": 1, "neutral": 0}
        main_signal = max(signals, key=lambda s: priority.get(s["emotion_key"], 0))
        main_emotion = main_signal["emotion_key"]
        if blank_mod < -0.2:
            combined = f"{emotion_label.get(main_emotion, main_emotion)}，偏压抑"
        elif blank_mod > 0.1:
            combined = f"{emotion_label.get(main_emotion, main_emotion)}，偏正面"
        else:
            combined = emotion_label.get(main_emotion, main_emotion)

    # 计算综合空间分数：主信号分数 + 留白修正
    spatial_score = 0.0
    if signals:
        main_signal_for_score = max(signals, key=lambda s: priority.get(s["emotion_key"], 0))
        spatial_score = main_signal_for_score.get("score", 0.0) + blank_mod

    return {
        "signals": signals,
        "blank_analysis": blank_desc,
        "blank_modifier": round(blank_mod, 2),
        "combined_spatial_sentiment": combined,
        "combined_spatial_score": round(spatial_score, 2),
        "blank_percent": round(b, 1),
        "coverage_ratio": round(c, 4),
    }


@dataclass
class AnalysisResult:
    """题跋内容分析结果"""
    char_count: int
    word_count: int
    ttr: float  # Type-Token Ratio
    themes: List[Dict]  # [{"code": 1, "name": "...", "confidence": 0.9}, ...]
    sentiment: Dict  # {"polarity": "positive", "intensity": 0.8}
    feature_words: Dict  # 各维度特征词统计
    objects_mentioned: List[str]  # 具体物象词
    top_words: List[Tuple[str, int]]  # 高频词Top20


def _score_to_emotion_label(score: float) -> str:
    """将印章情感分数转为情绪标签"""
    if score >= 0.5:
        return "positive"
    elif score <= -0.5:
        return "negative"
    elif score > 0:
        return "neutral_slight_positive"
    elif score < 0:
        return "neutral_slight_negative"
    return "neutral"


def analyze_seal_emotion(seal_content: str, artist: str = None) -> dict:
    """
    印章情感分析 —— 第三个维度

    数据来源优先级：
    1. 画家规则中的 seal_rules（画家特定的印章情感规则）
    2. 硬编码 SEAL_EMOTION_RULES（全局兜底）

    Args:
        seal_content: 印章文本，如 "宗杨、鱓印"
        artist: 画家名称（用于加载画家特定的印章规则）

    Returns:
        {
            "signals": [{"seal": "苦李", "category": "spirit", "emotion": "苦涩自况", "score": -1.0}, ...],
            "composite_score": -0.8,      # 加权综合分（-2 ~ +2）
            "seal_emotion": "偏消极",      # 综合判断
            "dominant_category": "spirit", # 主导类别
            "total_seals": 3,
            "matched_seals": 2,
        }
    """
    from app.services.tibi_analysis_rules import SEAL_EMOTION_RULES

    if not seal_content or not seal_content.strip():
        return {
            "signals": [],
            "composite_score": 0,
            "seal_emotion": "无印章",
            "dominant_category": None,
            "total_seals": 0,
            "matched_seals": 0,
        }

    catalog = SEAL_EMOTION_RULES.get("seal_catalog", {})
    cat_weights = SEAL_EMOTION_RULES.get("category_weight", {})
    unknown_rule = SEAL_EMOTION_RULES.get("unknown_seal", {"score": 0, "desc": "未知印章"})

    # 从画家规则加载印章情感数据（优先级最高）
    artist_seal_rules = {}
    if artist:
        try:
            artist_name = get_artist_display_name(artist) if artist else ""
            rules = _load_artist_rules(artist_name)
            seal_rules = rules.get("seal_rules", {})
            if isinstance(seal_rules, dict):
                artist_seal_rules = seal_rules
        except Exception:
            pass

    # 兜底：从 DB seals 表加载
    db_seal_cache = _load_seal_emotion_cache()

    # 解析印章文本（用、或,分隔）
    import re
    seal_names = re.split(r'[、,，\s]+', seal_content.strip())
    seal_names = [s.strip() for s in seal_names if s.strip()]

    signals = []
    total_score = 0.0
    category_scores = {}

    for name in seal_names:
        # 画家规则 → DB seals 表 → 硬编码兜底
        rule = artist_seal_rules.get(name) or db_seal_cache.get(name) or catalog.get(name)
        if rule:
            weight = cat_weights.get(rule.get("category", "unknown"), 0.5)
            weighted = rule["score"] * weight
            total_score += weighted

            cat = rule.get("category", "unknown")
            category_scores[cat] = category_scores.get(cat, 0) + weighted

            signals.append({
                "seal": name,
                "category": cat,
                "emotion": rule.get("emotion", "neutral"),
                "desc": rule.get("desc", ""),
                "raw_score": rule["score"],
                "weighted_score": round(weighted, 2),
            })
        else:
            signals.append({
                "seal": name,
                "category": "unknown",
                "emotion": "neutral",
                "desc": unknown_rule["desc"],
                "raw_score": 0,
                "weighted_score": 0,
            })

    # 综合判断
    if not signals:
        seal_emotion = "无印章"
    elif total_score >= 0.5:
        seal_emotion = "偏积极"
    elif total_score <= -0.5:
        seal_emotion = "偏消极"
    else:
        seal_emotion = "中性"

    # 主导类别
    dominant = max(category_scores, key=lambda k: abs(category_scores[k])) if category_scores else None

    return {
        "signals": signals,
        "composite_score": round(total_score, 2),
        "seal_emotion": seal_emotion,
        "dominant_category": dominant,
        "total_seals": len(seal_names),
        "matched_seals": sum(1 for s in signals if s["category"] != "unknown"),
    }


def get_period_phase(year: int, artist: str = None) -> str:
    """
    画家艺术生涯分期（基于出生年份计算年龄阶段）
    
    默认按李鱓分期（早期≤36岁/中期37-59岁/晚期≥60岁），
    如果传入 artist 参数则使用该画家的出生年份计算。
    year=None 时返回"年代不详"。
    """
    if year is None:
        return "年代不详"
    
    birth_year = get_artist_birth_year(artist) if artist else None
    
    if birth_year:
        age = year - birth_year
        if age <= 36:
            return "早期"
        elif age <= 59:
            return "中期"
        else:
            return "晚期"
    else:
        # 无出生年份时，使用通用分期（按世纪中叶划分）
        if year <= 1722:
            return "早期"
        elif year <= 1745:
            return "中期"
        else:
            return "晚期"


def count_chars(text: str) -> int:
    """统计字符数（不含标点）"""
    # 移除标点符号
    text_no_punct = re.sub(r'[，。！？、；：""''（）【】《》\\n\\s]', '', text)
    return len(text_no_punct)


def jieba_tokenize(text: str) -> List[str]:
    """jieba分词，去除停用词"""
    words = jieba.lcut(text)
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]




def extract_material_tags(title: str, inscription_content: str) -> List[str]:
    """从作品标题和题跋文字中提取画材标签，返回去重列表。"""
    combined = (title or "") + " " + (inscription_content or "")
    if not combined.strip():
        return []
    
    tags = []
    seen = set()
    
    for keyword, tag in MATERIAL_KEYWORDS:
        if tag in seen:
            continue
        
        # 单字特殊处理
        if keyword in GENERIC_SINGLE_CHARS and len(keyword) == 1:
            if keyword == "石":
                if keyword in (title or ""):
                    idx = (title or "").find(keyword)
                    if idx > 0 and title[idx - 1] in "湖怪奇":
                        tags.append(tag)
                        seen.add(tag)
            elif keyword == "鸟":
                bird_keywords = ["鸟", "雀", "燕", "鹦鹉", "鹭", "鹤", "鸽", "鸡", "鸭", "鹅", "鹌鹑", "喜鹊", "鹰", "黄鹂"]
                has_bird = any(k in (inscription_content or "") for k in bird_keywords)
                if has_bird:
                    tags.append(tag)
                    seen.add(tag)
            else:
                if keyword in (title or ""):
                    tags.append(tag)
                    seen.add(tag)
            continue
        
        # 多字关键词：在标题+题跋内容中匹配
        if keyword in combined:
            tags.append(tag)
            seen.add(tag)
    
    return tags


def calculate_ttr(words: List[str]) -> float:
    """计算词汇多样性指数（Type-Token Ratio）"""
    if not words:
        return 0.0
    unique_words = set(words)
    return len(unique_words) / len(words)


def extract_feature_words(words: List[str]) -> Dict:
    """提取特征词统计"""
    word_set = set(words)
    result = {}

    # 核心艺术理念
    result["core_arts"] = [w for w in FEATURE_WORDS["core_arts"] if w in word_set]
    # 情感词
    result["emotion"] = [w for w in FEATURE_WORDS["emotion"] if w in word_set]
    # 社会民生
    result["social"] = [w for w in FEATURE_WORDS["social"] if w in word_set]
    # 时空
    result["spacetime"] = [w for w in FEATURE_WORDS["spacetime"] if w in word_set]
    # 哲学审美
    result["philosophy"] = [w for w in FEATURE_WORDS["philosophy"] if w in word_set]

    return result


def extract_objects(text: str) -> List[str]:
    """提取具体物象词"""
    objects = []
    for category, words in FEATURE_WORDS["objects"].items():
        for word in words:
            if word in text:
                objects.append(word)
    return list(set(objects))


def rule_based_theme_classification(text: str) -> List[Dict]:
    """
    基于规则的主题分类（快速初筛）
    返回可能的多标签分类结果
    """
    themes = []
    text_lower = text.lower()

    for code, theme_info in THEMES.items():
        score = 0
        for keyword in theme_info["keywords"]:
            if keyword in text_lower:
                score += 1
        if score > 0:
            confidence = min(score / 3, 0.9)  # 最高0.9
            themes.append({
                "code": code,
                "name": theme_info["name"],
                "confidence": round(confidence, 2)
            })

    # 按置信度排序
    themes.sort(key=lambda x: x["confidence"], reverse=True)
    return themes if themes else [{"code": 0, "name": "未分类", "confidence": 0.0}]


def rule_based_sentiment_analysis(text: str, feature_words: Dict) -> Dict:
    """
    基于情感词的情感分析（通道1）
    """
    # 从特征词中提取情感词
    emotion_words = feature_words.get("emotion", [])

    positive_count = sum(1 for w in emotion_words if w in POSITIVE_WORDS)
    negative_count = sum(1 for w in emotion_words if w in NEGATIVE_WORDS)

    # 判定极性
    if positive_count > negative_count:
        polarity = "positive"
    elif negative_count > positive_count:
        polarity = "negative"
    else:
        polarity = "neutral"

    # 情感强度（0-1）
    total_emotion = positive_count + negative_count
    intensity = min(total_emotion / 3, 1.0) if total_emotion > 0 else 0.0

    return {
        "polarity": polarity,
        "intensity": round(intensity, 2),
        "positive_words": [w for w in emotion_words if w in POSITIVE_WORDS],
        "negative_words": [w for w in emotion_words if w in NEGATIVE_WORDS],
    }




def detect_sentiment_theme_conflict(text: str, llm_themes: List[Dict], llm_sentiment: Dict) -> Tuple[bool, str]:
    """
    检测主题和情感的矛盾
    返回 (has_conflict, conflict_description)
    """
    if not llm_themes or not llm_sentiment:
        return False, ""

    main_theme = llm_themes[0].get("name", "") if llm_themes else ""
    polarity = llm_sentiment.get("polarity", "neutral")

    text_lower = text or ""

    # 矛盾1：讽喻主题 + 积极情感 + 有强批判词
    strong_satire_words = ["恶态", "簪缨", "纨绔", "夺朱", "世味辣", "催租", "舆隶",
                           "官粮", "画贱", "衣食", "俗尘", "冷落"]
    has_strong_satire = any(w in text_lower for w in strong_satire_words)

    if main_theme == "讽喻社会与民生" and polarity == "positive" and has_strong_satire:
        return True, f"讽喻主题但情感为positive，且有强批判词（{'/'.join([w for w in strong_satire_words if w in text_lower])}）"

    # 茅盾2：应酬送人主题 + 消极情感 + 有牢骚词
    if main_theme == "应酬送人与雅交" and polarity == "negative":
        complaint_words = ["苦", "难", "卖画", "寒", "老", "穷"]
        if any(w in text_lower for w in complaint_words):
            return True, f"应酬送人主题但情感为negative，有牢骚词"

    # 茅盾3：世俗祈愿主题 + 消极情感（一般不应该）
    if main_theme == "世俗祈愿与谐趣" and polarity == "negative":
        # 如果同时有强烈的批判词，可能是矛盾
        if has_strong_satire:
            return True, f"世俗祈愿主题但情感为negative，且有强批判词"

    # 茅盾4：记录创作信息 + 消极情感（一般不应该，除非有很强的人生感慨）
    if main_theme == "记录创作信息" and polarity == "negative":
        strong_life_sorrow = ["老夫", "白发", "艰难", "困", "衰"]
        if any(w in text_lower for w in strong_life_sorrow):
            return True, f"记录创作信息但情感为negative，有人生感慨词"

    return False, ""


async def llm_retry_with_conflict(text: str, llm_themes: List[Dict], llm_sentiment: Dict, conflicts: str) -> Dict:
    """
    当检测到矛盾时，用更详细的 prompt 让 LLM 重新判断
    """
    from app.core.config import get_settings
    from app.services.qwen_llm_client import get_text_llm_config
    settings = get_settings()
    api_key, base_url, text_model = get_text_llm_config()

    if not api_key:
        return {"success": False, "error": "未配置API Key"}

    # 构建当前主题和情感的文字描述
    themes_str = ", ".join([f"{t['name']}({t['confidence']})" for t in llm_themes[:3]])
    sentiment_str = f"{llm_sentiment.get('polarity', 'unknown')}(强度{llm_sentiment.get('intensity', 0)})"

    prompt = LLM_CONFLICT_RETRY_PROMPT.format(
        themes=themes_str,
        sentiment=sentiment_str,
        text=text[:500],
        conflicts=conflicts
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": text_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.1,
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)

            return {
                "themes": parsed.get("themes", []),
                "sentiment": parsed.get("sentiment", {}),
                "resolved": parsed.get("resolved", False),
                "explanation": parsed.get("explanation", ""),
                "success": True
            }
    except Exception as e:
        return {"success": False, "error": f"LLM重试失败: {str(e)[:50]}"}


async def llm_theme_classification_v3(text: str, artist: str = None) -> List[Dict]:
    """
    调用 LLM 分析主题分类（v3多标签版本）
    返回格式： [{"code": 3, "name": "讽喻社会与民生", "confidence": 0.9}, ...]
    """
    from app.core.config import get_settings
    from app.services.qwen_llm_client import get_text_llm_config
    settings = get_settings()
    api_key, base_url, text_model = get_text_llm_config()

    if not api_key:
        return [{"code": 0, "name": "未分类", "confidence": 0.0}]

    note, se_names = _get_artist_theme_note(artist)
    prompt = LLM_THEME_PROMPT_V3.format(text=text[:500], artist_note=note, artist_se_names=se_names)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": text_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.1,
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)
            themes = parsed.get("themes", [])
            return [{"code": t.get("code", 0), "name": t.get("name", "未分类"), "confidence": float(t.get("confidence", 0.0))} for t in themes]
    except Exception as e:
        return [{"code": 0, "name": "未分类", "confidence": 0.0}]


async def llm_sentiment_analysis_v3(text: str, artist: str = None) -> Dict:
    """
    调用 LLM 分析情感（v3详细版本）
    """
    from app.core.config import get_settings
    from app.services.qwen_llm_client import get_text_llm_config
    settings = get_settings()
    api_key, base_url, text_model = get_text_llm_config()

    if not api_key:
        return {"polarity": "neutral", "reasoning": "未配置API Key"}

    artist_note = _get_artist_sentiment_note(artist)
    prompt = LLM_SENTIMENT_PROMPT_V3.format(text=text[:500], artist_note=artist_note)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": text_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.1,
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)
            return {
                "polarity": parsed.get("polarity", "neutral"),
                "reasoning": parsed.get("reasoning", "")
            }
    except Exception as e:
        return {"polarity": "neutral", "reasoning": f"LLM调用失败: {str(e)[:20]}"}


def analyze_tiba_content(text: str, year: int = None, title: str = None, analysis_note: str = None, width_cm: float = None, height_cm: float = None, artist: str = None) -> AnalysisResult:
    """
    分析单条题跋内容
    本地规则版本（无需调用LLM，用于快速统计）
    支持v4多维信号融合（year/title/analysis_note）
    """
    if not text or len(text.strip()) < 2:
        return AnalysisResult(
            char_count=0,
            word_count=0,
            ttr=0.0,
            themes=[{"code": 0, "name": "无内容", "confidence": 0.0}],
            sentiment={"polarity": "neutral", "intensity": 0.0},
            feature_words={},
            objects_mentioned=[],
            top_words=[]
        )

    # 1. 字符统计
    char_count = count_chars(text)

    # 2. 分词
    words = jieba_tokenize(text)
    word_count = len(words)

    # 3. 词汇多样性
    ttr = calculate_ttr(words)

    # 4. v4多维信号融合分类（纯规则，不调LLM）
    v4_result = classify_inscription_v4(text, year, title, analysis_note, None, width_cm, height_cm, artist=artist)

    # 5. 特征词提取
    feature_words = extract_feature_words(words)
    feature_words["v4_signals"] = v4_result["signals"]
    feature_words["v4_special_rules"] = v4_result["special_rules"]

    # 6. 物象提取
    objects = extract_objects(text)

    # 7. 高频词统计
    from collections import Counter
    word_freq = Counter(words)
    top_words = word_freq.most_common(20)

    return AnalysisResult(
        char_count=char_count,
        word_count=word_count,
        ttr=round(ttr, 3),
        themes=v4_result["themes"],
        sentiment=v4_result["sentiment"],
        feature_words=feature_words,
        objects_mentioned=objects,
        top_words=top_words
    )


async def analyze_tiba_content_dual(
    text: str,
    year: int = None,
    title: str = None,
    analysis_note: str = None,
    width_cm: float = None,
    height_cm: float = None,
    artist: str = None,
) -> AnalysisResult:
    """
    双通道分析（v4多维信号融合 + LLM v3）
    ─────────────────────────────────────────
    v4规则引擎为主，LLM为辅（验证/边界case）
    新增参数：year, title, analysis_note 用于多维信号融合
    """
    # 1. 字符统计
    char_count = count_chars(text)
    # 2. 分词
    words = jieba_tokenize(text)
    word_count = len(words)
    # 3. 词汇多样性
    ttr = calculate_ttr(words)
    # 4. 特征词提取
    feature_words = extract_feature_words(words)
    # 5. 物象提取
    objects = extract_objects(text)
    # 6. 高频词
    from collections import Counter
    word_freq = Counter(words)
    top_words = word_freq.most_common(20)

    # ── v4 多维信号融合分类（主通道） ──────────────────────────────
    v4_result = classify_inscription_v4(text, year, title, analysis_note, None, width_cm, height_cm, artist=artist)
    v4_themes = v4_result["themes"]
    v4_sentiment = v4_result["sentiment"]
    v4_signals = v4_result["signals"]
    v4_special_rules = v4_result["special_rules"]

    # ── LLM v3 分类（辅助通道，用于交叉验证） ──────────────────────
    llm_themes = await llm_theme_classification_v3(text, artist=artist)
    llm_sentiment = await llm_sentiment_analysis_v3(text, artist=artist)

    # ── 融合策略：v4规则为主，LLM为辅 ─────────────────────────────
    # 主题：以v4规则结果为主
    # 如果v4只有一个低置信度主题且LLM有不同意见，参考LLM补充
    final_themes = v4_themes
    if len(v4_themes) == 1 and v4_themes[0]["confidence"] < 0.6:
        # v4不确定时，参考LLM补充第二主题
        v4_codes = {t["code"] for t in v4_themes}
        for lt in llm_themes:
            if lt["code"] not in v4_codes and lt.get("confidence", 0) >= 0.5:
                final_themes.append(lt)
                break

    # 情感：v4规则为主，LLM为交叉验证
    final_polarity = v4_sentiment["polarity"]
    llm_polarity = llm_sentiment.get("polarity", "neutral")
    agreement = final_polarity == llm_polarity

    sentiment = {
        "polarity": final_polarity,
        "intensity": min(abs(v4_sentiment["emotion_score"]) / 3, 1.0),
        "emotion_score": v4_sentiment["emotion_score"],  # 连续值，用于时间序列
        "reasoning": v4_sentiment["reasoning"],
        "reasoning_steps": v4_sentiment.get("reasoning_steps", []),
        "llm_polarity": llm_polarity,
        "agreement": agreement,
        "channel_v4": v4_sentiment,
        "channel_llm": llm_sentiment,
    }

    # 保存完整信号明细到 feature_words（用于前端展示和调试）
    feature_words["v4_signals"] = v4_signals
    feature_words["v4_special_rules"] = v4_special_rules

    return AnalysisResult(
        char_count=char_count,
        word_count=word_count,
        ttr=round(ttr, 3),
        themes=final_themes,
        sentiment=sentiment,
        feature_words=feature_words,
        objects_mentioned=objects,
        top_words=top_words
    )


def analyze_with_llm(image_path: str, text: str, api_key: str = None) -> Dict:
    """
    调用LLM进行高精度主题分类和情感分析
    返回结构化JSON结果
    """
    # TODO: 集成 Qwen VL Plus API
    # 当前返回本地规则结果作为占位
    result = analyze_tiba_content(text)
    return {
        "char_count": result.char_count,
        "word_count": result.word_count,
        "ttr": result.ttr,
        "themes": result.themes,
        "sentiment": result.sentiment,
        "objects_mentioned": result.objects_mentioned,
        "feature_words": result.feature_words,
        "reasoning": "基于规则分析（LLM集成待实现）",
    }


async def llm_analyze_combined(text: str, artist: str = None) -> Dict:
    """
    组合LLM分析：一次API调用同时返回主题+情感
    返回格式：{"success": bool, "themes": [...], "sentiment": {...}, "error": str}
    """
    from app.core.config import get_settings
    from app.services.qwen_llm_client import get_text_llm_config
    settings = get_settings()
    api_key, base_url, text_model = get_text_llm_config()

    if not api_key:
        return {"success": False, "error": "未配置 API Key", "themes": [], "sentiment": {}}

    note, _ = _get_artist_theme_note(artist)
    # 无画家信息时不注入过长注释（避免 prompt 溢出）
    artist_context = artist or ""
    prompt = LLM_COMBINED_PROMPT_V1.format(text=text[:500], artist_note=note if artist_context else "")

    try:
        request_body = {
            "model": text_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.1,
        }
        # DeepSeek 用 thinking 参数，Qwen 用 enable_thinking
        if "deepseek" in base_url.lower() or "deepseek" in text_model.lower():
            request_body["thinking"] = {"type": "disabled"}
        else:
            request_body["enable_thinking"] = False

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=request_body
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            # 提取 JSON：支持 markdown 代码块、多余文本等边缘情况
            raw_clean = raw.strip()
            # 去除 markdown 代码块
            if raw_clean.startswith("```"):
                raw_clean = raw_clean.split("\n", 1)[-1] if "\n" in raw_clean else raw_clean
                raw_clean = raw_clean.rsplit("```", 1)[0] if "```" in raw_clean else raw_clean
            # 取第一个 { 到最后一个 }
            brace_start = raw_clean.find("{")
            brace_end = raw_clean.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                raw_clean = raw_clean[brace_start:brace_end+1]
            parsed = json.loads(raw_clean)
            
            themes = parsed.get("themes", [])
            sentiment = parsed.get("sentiment", {})
            
            # 标准化主题格式
            standardized_themes = []
            for t in themes:
                standardized_themes.append({
                    "code": t.get("code", 0),
                    "name": t.get("name", "未分类"),
                    "confidence": float(t.get("confidence", 0.0))
                })
            
            # 标准化情感格式
            if "polarity" not in sentiment:
                sentiment["polarity"] = "neutral"
            if "intensity" not in sentiment:
                sentiment["intensity"] = 0.5
            
            return {
                "success": True,
                "themes": standardized_themes,
                "sentiment": sentiment,
                "overall_reasoning": parsed.get("overall_reasoning", "")
            }
    except Exception as e:
        return {"success": False, "error": str(e), "themes": [], "sentiment": {}}


def hybrid_analyze_with_divergence(
    text: str,
    year: int = None,
    title: str = None,
    analysis_note: str = None,
    width_cm: float = None,
    height_cm: float = None,
    artist: str = None,
    record_id: int = None,
    image_id: str = None,
) -> Dict:
    """
    混合推理 + 分歧检测。
    1. 先跑规则引擎（快）
    2. 置信度 >= 0.6 → 直接返回
    3. 置信度 < 0.6 → 调 DeepSeek LLM 二次判断
    4. 对比结果，返回分歧信息

    返回：
    {
        "v4_result": {...},         # 规则引擎完整结果
        "llm_result": {...},        # LLM 结果（仅低置信度时有）
        "used_llm": bool,
        "divergence": {...} | None, # 分歧信息
    }
    """
    import asyncio

    v4_result = classify_inscription_v4(
        text, year=year, title=title, analysis_note=analysis_note,
        width_cm=width_cm, height_cm=height_cm, artist=artist
    )
    confidence = v4_result.get("confidence", 0)

    result = {
        "v4_result": v4_result,
        "llm_result": None,
        "used_llm": False,
        "divergence": None,
    }

    if confidence >= 0.6:
        return result

    # 低置信度 → 调 LLM
    try:
        llm_raw = asyncio.run(llm_analyze_combined(text, artist=artist))
    except Exception as e:
        # LLM 不可用，静默降级
        return result
    if not llm_raw.get("success"):
        return result

    result["used_llm"] = True
    result["llm_result"] = llm_raw

    # 对比分歧
    v4_primary = v4_result["themes"][0] if v4_result.get("themes") else None
    llm_primary = llm_raw["themes"][0] if llm_raw.get("themes") else None

    v4_polarity = v4_result.get("sentiment", {}).get("polarity", "")
    llm_polarity = llm_raw.get("sentiment", {}).get("polarity", "")

    theme_diverge = v4_primary and llm_primary and v4_primary.get("code") != llm_primary.get("code")
    sentiment_diverge = v4_polarity and llm_polarity and v4_polarity != llm_polarity

    if theme_diverge or sentiment_diverge:
        div_type = "both" if (theme_diverge and sentiment_diverge) else ("theme" if theme_diverge else "sentiment")
        detail_parts = []
        if theme_diverge:
            detail_parts.append(
                f"主题: 规则={v4_primary['name']}(c={v4_primary.get('confidence',0):.2f}) "
                f"vs LLM={llm_primary.get('name','?')}(c={llm_primary.get('confidence',0):.2f})"
            )
        if sentiment_diverge:
            detail_parts.append(
                f"情感极性: 规则={v4_polarity}({v4_result['sentiment'].get('emotion_score',0):.1f}) "
                f"vs LLM={llm_polarity}"
            )
        result["divergence"] = {
            "type": div_type,
            "detail": " | ".join(detail_parts),
            "v4_confidence": confidence,
        }

    return result


if __name__ == "__main__":
    # 测试
    test_text = "八大山人长于笔，清湘大涤子长于墨，至予则长于水。水为笔墨之介绍，而今人不知也。"
    result = analyze_tiba_content(test_text)
    print(f"字符数: {result.char_count}")
    print(f"词数: {result.word_count}")
    print(f"TTR: {result.ttr}")
    print(f"主题: {result.themes}")
    print(f"情感: {result.sentiment}")
    print(f"物象: {result.objects_mentioned}")
