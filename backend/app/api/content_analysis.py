"""
题跋内容学术分析 API
- 分期统计
- 主题分类
- 词频分析
- 情感分布
- 内容-形式关联
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.auth import require_editor
from app.core.database import get_db_connection
from app.services.inscription_content_analyzer import (
    analyze_tiba_content,
    analyze_tiba_content_dual,
    get_period_phase,
    FEATURE_WORDS,
    THEMES,
)
from app.services.content_form_correlation import (
    build_contingency_table,
    chi_square_test,
    compute_correlation_stats,
    get_invasive_analysis,
)
from app.services.inscription_position_analyzer import FORM_TYPES

router = APIRouter(prefix="/content-analysis", tags=["content-analysis"])


# ============ 辅助函数 ============

def build_artist_condition(artist: str) -> tuple:
    """
    构建画家筛选条件
    
    Args:
        artist: 画家名称，'all' 表示所有画家
    
    Returns:
        (where_clause, params): SQL WHERE 子句和参数
    """
    if not artist or artist == 'all':
        # 所有画家
        return "1=1", ()
    else:
        # 特定画家（支持模糊匹配）
        return "(artist LIKE ? OR artist LIKE ?)", (f"%{artist}%", f"%{artist}%")


# ============ 公共服务函数 ============

def persist_analysis_result(cur, record_id, result, year=None, artist=None, extra_fields=None):
    """
    统一持久化题跋分析结果到 tubi_analyses 表。
    供 /verify、/analyze/、/batch、/batch-reanalyze 等端点复用。

    Args:
        extra_fields: 额外合并到 content_analysis JSON 的字段，如 {"v4_confidence": 0.8, "rules_version": "5.5"}
    """
    from app.services.inscription_content_analyzer import get_period_phase

    content_analysis = {
        "char_count": result.char_count,
        "word_count": result.word_count,
        "ttr": result.ttr,
        "themes": result.themes,
        "sentiment": result.sentiment,
        "feature_words": result.feature_words,
        "objects_mentioned": result.objects_mentioned,
    }
    if extra_fields:
        content_analysis.update(extra_fields)

    theme_tags = ",".join([t["name"] for t in result.themes])
    period_phase = get_period_phase(year, artist)

    cur.execute("""
        UPDATE tubi_analyses
        SET char_count = ?,
            word_count = ?,
            theme_tags = ?,
            content_analysis = ?,
            period_phase = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        content_analysis["char_count"],
        content_analysis["word_count"],
        theme_tags,
        json.dumps(content_analysis, ensure_ascii=False),
        period_phase,
        datetime.now(),
        record_id
    ))

    return content_analysis


async def analyze_single_record(record_id: int, cur) -> dict:
    """
    单条记录的统一分析管道（规则引擎 → 低可信度 → 人工智能修正 → 保存DB）。
    供 reanalyze_single 和 batch_reanalyze 复用，确保两条路径行为一致。

    Args:
        record_id: 记录ID
        cur: 数据库游标（由调用方管理连接和提交）

    Returns:
        {"success": True, "record_id": ..., "themes": [...], "sentiment": {...},
         "confidence": ..., "llm_fixed": bool, "llm_error": str|None}
    """
    import json
    import logging
    logger = logging.getLogger(__name__)
    from app.services.inscription_content_analyzer import (
        classify_inscription_v4, THEME_NAME_MIGRATION, llm_analyze_combined
    )
    from app.services.auto_tags import compute_tags

    cur.execute("""
        SELECT id, inscription_content, year, title, analysis_note,
               artwork_width_cm, artwork_height_cm, artist, content_analysis, period_phase,
               seal_content
        FROM tubi_analyses WHERE id = ?
    """, (record_id,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": "Record not found"}

    text = row["inscription_content"] or ""
    if not text or len(text.strip()) < 2:
        return {"success": False, "error": "题跋内容为空"}

    old_ca = None
    if row["content_analysis"]:
        try: old_ca = json.loads(row["content_analysis"])
        except Exception: pass

    # 1. 规则引擎
    result = classify_inscription_v4(
        text=text, year=row["year"], title=row["title"],
        analysis_note=row["analysis_note"],
        width_cm=row["artwork_width_cm"], height_cm=row["artwork_height_cm"],
        artist=row["artist"],
    )
    conf = result.get("confidence", 0)

    # 2. 低可信度 → DeepSeek
    llm_fixed = False
    llm_error = None
    llm_detail = ""
    if conf < 0.6 and len(text) > 3:
        try:
            llm_raw = await llm_analyze_combined(text, artist=row["artist"])
            if llm_raw.get("success"):
                llm_primary = llm_raw["themes"][0] if llm_raw.get("themes") else None
                v4_primary = result["themes"][0] if result.get("themes") else None

                # 主题分歧
                if llm_primary and v4_primary and llm_primary.get("code") != v4_primary.get("code"):
                    llm_fixed = True
                    llm_detail = f"{v4_primary['name']}->{llm_primary['name']}"
                    normalized = []
                    for t in llm_raw["themes"]:
                        name = t.get("name", "")
                        norm_name = THEME_NAME_MIGRATION.get(name, name)
                        normalized.append({"code": t.get("code", 0), "name": norm_name, "confidence": float(t.get("confidence", 0.0))})
                    result["themes"] = normalized
                    result["special_rules"].append(f"[人工智能采纳] 主题分歧: {llm_detail}")
                    result["sentiment"]["reasoning_steps"].append({
                        "label": "人工智能复核",
                        "detail": f"低可信度({conf:.2f})触发DeepSeek二次判断，原规则判[{v4_primary['name']}]，人工智能判[{llm_primary['name']}]",
                        "offset": 0, "icon": "🤖",
                    })

                # 情感分歧
                llm_pol = llm_raw.get("sentiment", {}).get("polarity", "")
                v4_pol = result["sentiment"].get("polarity", "")
                if llm_pol and v4_pol != llm_pol and llm_pol != "neutral":
                    result["sentiment"]["polarity"] = llm_pol
                    llm_intensity = llm_raw["sentiment"].get("intensity", 0.5)
                    if llm_pol == "positive": result["sentiment"]["emotion_score"] = llm_intensity * 5
                    elif llm_pol == "negative": result["sentiment"]["emotion_score"] = -llm_intensity * 5
                    _pol_cn = {"positive": "积极", "negative": "消极", "neutral": "中性"}
                    result["special_rules"].append(f"[人工智能采纳] 情感分歧: {_pol_cn.get(v4_pol, v4_pol)}→{_pol_cn.get(llm_pol, llm_pol)}")
                    result["sentiment"]["reasoning_steps"].append({
                        "label": "人工智能复核",
                        "detail": f"低可信度({conf:.2f})触发DeepSeek二次判断，情感极性{_pol_cn.get(v4_pol, v4_pol)}→{_pol_cn.get(llm_pol, llm_pol)}",
                        "offset": 0, "icon": "🤖",
                    })
                # LLM无分歧时也同步emotion_score
                elif llm_pol == v4_pol and llm_pol != "neutral":
                    llm_intensity = llm_raw["sentiment"].get("intensity", 0.5)
                    if llm_pol == "positive":
                        result["sentiment"]["emotion_score"] = max(result["sentiment"].get("emotion_score", 0), llm_intensity * 4)
                    elif llm_pol == "negative":
                        result["sentiment"]["emotion_score"] = min(result["sentiment"].get("emotion_score", 0), -llm_intensity * 4)
            else:
                llm_error = llm_raw.get("error", "LLM分析返回失败")
        except Exception as e:
            llm_error = str(e)[:120]

    # 3. 构建 content_analysis 并保存
    new_ca = dict(old_ca) if old_ca else {}
    new_ca["themes"] = result.get("themes", [])
    new_ca["sentiment"] = result["sentiment"]
    new_ca["v4_confidence"] = conf
    new_ca["rules_version"] = "5.6"
    new_ca["batch_reanalyze_at"] = datetime.now().isoformat()

    # 4. 空间情绪分析（如果已标注区域）
    se = None  # spatial_emotion result
    try:
        cur.execute("SELECT regions, blank_percent, position_analysis, image_width, image_height FROM tubi_analyses WHERE id = ?", (record_id,))
        sr = cur.fetchone()
        if sr and sr["regions"]:
            regions_raw = sr["regions"]
            if isinstance(regions_raw, str):
                regions = json.loads(regions_raw)
                if isinstance(regions, str):
                    regions = json.loads(regions)
            else:
                regions = regions_raw
            if regions and isinstance(regions, dict) and regions.get("inscription_regions"):
                from app.services.inscription_position_analyzer import analyze_inscription_position_simple
                from app.services.inscription_content_analyzer import analyze_spatial_emotion

                pos = analyze_inscription_position_simple(regions, sr["image_width"] or 1000, sr["image_height"] or 1000)
                cur.execute("UPDATE tubi_analyses SET position_analysis = ? WHERE id = ?",
                            (json.dumps(pos, ensure_ascii=False), record_id))

                se = analyze_spatial_emotion(pos, sr["blank_percent"] or 50, pos.get("coverage_ratio", 0))
                new_ca["spatial_emotion"] = se
    except Exception as e:
        logger.warning(f"空间情绪分析跳过 (record_id={record_id}): {e}")

    # 5. 印章情感分析（独立维度，不受空间分析影响）
    try:
        from app.services.inscription_content_analyzer import analyze_seal_emotion
        seal_text = row["seal_content"] or ""
        seal_result = analyze_seal_emotion(seal_text)
        new_ca["seal_emotion"] = seal_result
    except Exception as e:
        logger.warning(f"印章分析跳过 (record_id={record_id}): {e}")
        seal_result = None

    # 6. 合并文字 + 空间 + 印章三维综合
    text_pol = new_ca.get("sentiment", {}).get("polarity", "neutral")
    is_seal_neg = seal_result["seal_emotion"] == "偏消极" if seal_result else False
    is_seal_pos = seal_result["seal_emotion"] == "偏积极" if seal_result else False
    seal_score = seal_result.get("composite_score", 0) if seal_result else 0

    if se:
        spatial_sig = se.get("combined_spatial_sentiment", "")
        is_sp_neg = any(kw in spatial_sig for kw in ["压抑", "宣泄", "紧张"])
        is_sp_pos = any(kw in spatial_sig for kw in ["正面", "舒展", "狂放", "自信"])
    else:
        spatial_sig = ""
        is_sp_neg = is_sp_pos = False

    neg_count = sum([text_pol == "negative", is_sp_neg, is_seal_neg])
    pos_count = sum([text_pol == "positive", is_sp_pos, is_seal_pos])

    # 构建推理文案
    def _seal_text():
        if not seal_result or not seal_result.get("total_seals"):
            return ""
        if is_seal_neg: return "印章偏消极"
        if is_seal_pos: return "印章偏积极"
        return "印章中性"
    def _space_text():
        if not se: return ""
        if is_sp_neg: return "空间压抑"
        if is_sp_pos: return "空间舒展"
        return "空间克制"
    def _text_label():
        return {"positive": "积极", "negative": "消极"}.get(text_pol, "中性")

    parts = [f"文字{_text_label()}"]
    st = _space_text()
    if st: parts.append(st)
    sl = _seal_text()
    if sl: parts.append(sl)

    if neg_count >= 2 and pos_count == 0:
        cp, cr = "negative", "、".join(parts) + "，综合偏负面"
    elif pos_count >= 2 and neg_count == 0:
        cp, cr = "positive", "、".join(parts) + "，综合偏正面"
    elif text_pol == "negative" and is_sp_pos:
        cp, cr = "ambiguous", "文字消极但空间舒展，存在矛盾信号"
    elif text_pol == "positive" and is_sp_neg:
        cp, cr = "ambiguous", "文字积极但空间压抑，存在矛盾信号"
    elif text_pol == "negative":
        cp, cr = "negative", "、".join(parts) + "，综合偏负面"
    elif text_pol == "positive":
        cp, cr = "positive", "、".join(parts) + "，综合偏正面"
    else:
        cp, cr = "neutral", "、".join(parts) + "，无明显倾向"
    new_ca["combined_sentiment"] = {"polarity": cp, "reasoning": cr,
        "text_score": new_ca.get("sentiment", {}).get("emotion_score") or 0,
        "spatial_score": -1 if is_sp_neg else (1 if is_sp_pos else 0),
        "seal_score": seal_score,
        "combined_score": round((new_ca.get("sentiment", {}).get("emotion_score") or 0) +
                                (-1 if is_sp_neg else (1 if is_sp_pos else 0)) +
                                seal_score, 1)}

    theme_tags = ",".join(t["name"] for t in result.get("themes", []) if t.get("name"))
    cur.execute("""
        UPDATE tubi_analyses SET content_analysis = ?, theme_tags = ? WHERE id = ?
    """, (json.dumps(new_ca, ensure_ascii=False), theme_tags, record_id))

    # 重新计算自动标签
    record_for_tags = {
        "title": row["title"],
        "period_phase": row["period_phase"],
        "artwork_height_cm": row["artwork_height_cm"],
        "artwork_width_cm": row["artwork_width_cm"],
        "content_analysis": json.dumps(new_ca, ensure_ascii=False),
        "material_tags": None,
    }
    auto_tags = compute_tags(record_for_tags)
    if auto_tags:
        cur.execute("UPDATE tubi_analyses SET tags = ? WHERE id = ?",
                    (json.dumps(auto_tags, ensure_ascii=False), record_id))

    return {
        "success": True,
        "record_id": record_id,
        "themes": result["themes"],
        "sentiment": result["sentiment"],
        "confidence": conf,
        "llm_fixed": llm_fixed,
        "llm_error": llm_error,
        "llm_detail": llm_detail,
    }


def stale_analysis_result(cur, record_id):
    """
    将分析结果标记为过期（清空所有题跋衍生字段）。
    用于文本清空或分析不可用场景，确保前端不继续展示旧结果。
    """
    cur.execute("""
        UPDATE tubi_analyses
        SET content_analysis = NULL,
            theme_tags = NULL,
            char_count = NULL,
            word_count = NULL,
            period_phase = NULL,
            updated_at = ?
        WHERE id = ?
    """, (datetime.now(), record_id))


# ============ 数据模型 ============

class PeriodStats(BaseModel):
    period: str
    count: int
    avg_char_count: float
    max_char_count: int
    min_char_count: int
    avg_word_count: float
    avg_ttr: float


class WordFreqItem(BaseModel):
    word: str
    count: int
    period: str


class ThemeDistItem(BaseModel):
    theme_code: int
    theme_name: str
    period: str
    count: int
    percentage: float


class SentimentDistItem(BaseModel):
    polarity: str  # positive/negative/neutral
    period: str
    count: int
    percentage: float


class LayoutFormDistItem(BaseModel):
    form_name: str
    count: int
    percentage: float


class FeatureWordStat(BaseModel):
    dimension: str
    word: str
    count: int
    period: str


class MaterialTagItem(BaseModel):
    tag: str
    count: int
    percentage: float


class AreaDistItem(BaseModel):
    range: str
    inscription_count: int
    painting_count: int
    blank_count: int


class AreaThemeItem(BaseModel):
    theme_name: str
    avg_inscription_percent: float
    avg_painting_percent: float
    avg_blank_percent: float


class AreaSizeItem(BaseModel):
    artwork_height_cm: float
    inscription_percent: float
    theme_name: str
    title: str
    period: str


class StatsResponse(BaseModel):
    artist: str
    total_count: int
    period_stats: List[PeriodStats]
    theme_distribution: List[ThemeDistItem]
    sentiment_distribution: List[SentimentDistItem]
    layout_form_distribution: List[LayoutFormDistItem]
    feature_word_stats: List[FeatureWordStat]
    top_words: List[WordFreqItem]
    material_tags: List[MaterialTagItem] = []
    area_distribution: List[AreaDistItem] = []
    area_theme_stats: List[AreaThemeItem] = []
    area_size_correlation: List[AreaSizeItem] = []


class CorrelationItem(BaseModel):
    theme: str
    form_type: str
    count: int
    expected: float
    chi2_contrib: float


class CorrelationResponse(BaseModel):
    artist: str
    chi2_statistic: float
    p_value: float
    significant: bool  # p < 0.05
    correlation_table: List[CorrelationItem]


class VerifyRequest(BaseModel):
    inscription_content: str
    seal_content: Optional[str] = None
    analysis_note: Optional[str] = None


class VerifyResponse(BaseModel):
    success: bool
    message: str
    record_id: int
    analysis_status: str = "unchanged"
    content_analysis: Optional[Dict[str, Any]] = None
    theme_tags: Optional[str] = None


class ArtistInfo(BaseModel):
    name: str
    birth_year: Optional[int] = None
    dynasty: str = ""
    artwork_count: int = 0

class ArtistsResponse(BaseModel):
    success: bool
    artists: List[str] = []  # 兼容旧版
    artists_info: List[ArtistInfo] = []  # 新：含朝代/生年/作品数


# ============ API 端点 ============

@router.get("/artists", response_model=ArtistsResponse)
async def get_artists():
    """
    获取数据库中所有去重作者列表（含朝代/生年/作品数）
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # 主列表：从 tubi_analyses 统计
    cur.execute("""
        SELECT ta.artist,
               a.birth_year,
               COUNT(*) as cnt
        FROM tubi_analyses ta
        LEFT JOIN artists a ON a.name = ta.artist
        WHERE ta.artist IS NOT NULL AND ta.artist != ''
        GROUP BY ta.artist
        ORDER BY ta.artist
    """)
    rows = cur.fetchall()

    artists_info = []
    for name, birth_year, cnt in rows:
        artists_info.append(ArtistInfo(
            name=name,
            birth_year=birth_year,
            dynasty=_dynasty_from_year(birth_year),
            artwork_count=cnt,
        ))

    artists = [a.name for a in artists_info]
    return {"success": True, "artists": artists, "artists_info": artists_info}


def _dynasty_from_year(birth_year) -> str:
    """根据生年推断朝代"""
    if birth_year is None:
        return "年代不详"
    if birth_year < 0:
        return "先秦"
    if birth_year <= 220:
        return "秦汉"
    if birth_year <= 589:
        return "魏晋南北朝"
    if birth_year <= 907:
        return "隋唐"
    if birth_year <= 960:
        return "五代十国"
    if birth_year <= 1234:
        return "辽金"
    if birth_year <= 1279:
        return "宋"
    if birth_year <= 1368:
        return "元"
    if birth_year <= 1644:
        return "明"
    if birth_year <= 1911:
        return "清"
    if birth_year <= 1949:
        return "近现代"
    return "当代"


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    artist: str = Query(default="all", description="画家名称，'all'表示所有画家"),
):
    """
    获取分期统计：字数、词频、主题分布、情感分布
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    artist_where, artist_params = build_artist_condition(artist)

    # 1. 基础统计（按分期）
    cur.execute(f"""
        SELECT 
            period_phase,
            COUNT(*) as count,
            AVG(COALESCE(char_count, 0)) as avg_chars,
            MAX(COALESCE(char_count, 0)) as max_chars,
            MIN(CASE WHEN COALESCE(char_count, 0) > 0 THEN char_count END) as min_chars,
            AVG(COALESCE(word_count, 0)) as avg_words
        FROM tubi_analyses
        WHERE {artist_where}
          AND inscription_content IS NOT NULL
          AND LENGTH(inscription_content) > 0
        GROUP BY period_phase
        ORDER BY period_phase
    """, artist_params)

    period_stats = []
    for row in cur.fetchall():
        period_stats.append(PeriodStats(
            period=row[0] or "未分期",
            count=row[1],
            avg_char_count=round(row[2] or 0, 1),
            max_char_count=row[3] or 0,
            min_char_count=row[4] or 0,
            avg_word_count=round(row[5] or 0, 1),
            avg_ttr=0.0  # TODO: 从content_analysis解析
        ))

    # 2. 主题分布（从content_analysis JSON解析）
    cur.execute(f"""
        SELECT period_phase, content_analysis
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL
    """, artist_params)

    theme_counts = {}  # {(period, theme_name): count}
    sentiment_counts = {}  # {(period, polarity): count}
    feature_word_stats = []  # FeatureWordStat list
    all_top_words = []

    import json
    for row in cur.fetchall():
        period, content_json = row
        period = period or "未分期"

        try:
            analysis = json.loads(content_json)

            # 主题统计
            themes = analysis.get("themes", [])
            for theme in themes:
                key = (period, theme.get("name", "未知"))
                theme_counts[key] = theme_counts.get(key, 0) + 1

            # 情感统计
            sentiment = analysis.get("sentiment", {})
            polarity = sentiment.get("polarity", "neutral")
            key = (period, polarity)
            sentiment_counts[key] = sentiment_counts.get(key, 0) + 1

            # 特征词统计
            feature_words = analysis.get("feature_words", {})
            for dim, words in feature_words.items():
                for word in words:
                    feature_word_stats.append(FeatureWordStat(
                        dimension=dim,
                        word=word,
                        count=1,
                        period=period
                    ))

        except:
            continue

    # 计算主题分布百分比
    theme_distribution = []
    period_totals = {}
    for (period, theme), count in theme_counts.items():
        period_totals[period] = period_totals.get(period, 0) + count

    for (period, theme), count in theme_counts.items():
        total = period_totals.get(period, 1)
        theme_distribution.append(ThemeDistItem(
            theme_code=0,  # TODO: 映射code
            theme_name=theme,
            period=period,
            count=count,
            percentage=round(count / total * 100, 1)
        ))

    # 计算情感分布百分比
    sentiment_distribution = []
    for (period, polarity), count in sentiment_counts.items():
        total = period_totals.get(period, 1)
        sentiment_distribution.append(SentimentDistItem(
            polarity=polarity,
            period=period,
            count=count,
            percentage=round(count / total * 100, 1)
        ))

    # 3. 总数量
    cur.execute(f"""
        SELECT COUNT(*) FROM tubi_analyses
        WHERE {artist_where}
          AND inscription_content IS NOT NULL
          AND LENGTH(inscription_content) > 0
    """, artist_params)
    total_count = cur.fetchone()[0]

    # 4. 布局形式分布（从 position_analysis JSON 解析 form_types）
    cur.execute(f"""
        SELECT position_analysis FROM tubi_analyses
        WHERE {artist_where}
          AND position_analysis IS NOT NULL
    """, artist_params)
    form_counts = {}
    total_form_count = 0
    for row in cur.fetchall():
        try:
            pos = json.loads(row[0])
            for ft in pos.get("form_types", []):
                if ft.get("matched"):
                    name = ft.get("name", "未知")
                    form_counts[name] = form_counts.get(name, 0) + 1
                    total_form_count += 1
        except:
            continue

    layout_form_distribution = []
    for name, count in form_counts.items():
        layout_form_distribution.append(LayoutFormDistItem(
            form_name=name,
            count=count,
            percentage=round(count / max(total_form_count, 1) * 100, 1)
        ))
    layout_form_distribution.sort(key=lambda x: x.count, reverse=True)

    # 5. 画材标签统计
    cur.execute(f"""
        SELECT material_tags FROM tubi_analyses
        WHERE {artist_where}
          AND material_tags IS NOT NULL
          AND material_tags != ''
    """, artist_params)
    
    tag_counts = {}
    total_tagged = 0
    for row in cur.fetchall():
        tags = row[0].split(',')
        for tag in tags:
            tag = tag.strip()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                total_tagged += 1
    
    material_tags = []
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        material_tags.append(MaterialTagItem(
            tag=tag,
            count=count,
            percentage=round(count / max(total_tagged, 1) * 100, 1)
        ))

    # ============ 6. 面积分布直方图 ============
    cur.execute(f"""
        SELECT inscription_percent, painting_percent, blank_percent
        FROM tubi_analyses
        WHERE {artist_where}
          AND inscription_percent IS NOT NULL
    """, artist_params)

    bins = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
            (50, 60), (60, 70), (70, 80), (80, 90), (90, 100)]
    bucket_counts = {}
    for low, high in bins:
        bucket_counts[f"{low}-{high}%"] = {"inscription": 0, "painting": 0, "blank": 0}

    for row in cur.fetchall():
        insc, paint, blank = row
        for low, high in bins:
            key = f"{low}-{high}%"
            if low <= insc < high or (high == 100 and insc >= 100):
                bucket_counts[key]["inscription"] += 1
            if low <= paint < high or (high == 100 and paint >= 100):
                bucket_counts[key]["painting"] += 1
            if low <= blank < high or (high == 100 and blank >= 100):
                bucket_counts[key]["blank"] += 1

    area_distribution = []
    for low, high in bins:
        key = f"{low}-{high}%"
        area_distribution.append(AreaDistItem(
            range=key,
            inscription_count=bucket_counts[key]["inscription"],
            painting_count=bucket_counts[key]["painting"],
            blank_count=bucket_counts[key]["blank"]
        ))

    # ============ 7. 面积-主题堆叠柱状图 ============
    cur.execute(f"""
        SELECT content_analysis, inscription_percent, painting_percent, blank_percent
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL
          AND content_analysis != ''
          AND content_analysis != '{{}}'
          AND inscription_percent IS NOT NULL
    """, artist_params)

    theme_area_sums = {}
    theme_area_counts = {}
    for row in cur.fetchall():
        content_json, insc, paint, blank = row
        try:
            analysis = json.loads(content_json)
            themes = analysis.get("themes", [])
            for theme in themes:
                name = theme.get("name", "未知")
                if name not in theme_area_sums:
                    theme_area_sums[name] = {"insc": 0.0, "paint": 0.0, "blank": 0.0}
                    theme_area_counts[name] = 0
                theme_area_sums[name]["insc"] += insc or 0
                theme_area_sums[name]["paint"] += paint or 0
                theme_area_sums[name]["blank"] += blank or 0
                theme_area_counts[name] += 1
        except Exception:
            continue

    area_theme_stats = []
    for name in theme_area_sums:
        count = theme_area_counts[name]
        area_theme_stats.append(AreaThemeItem(
            theme_name=name,
            avg_inscription_percent=round(theme_area_sums[name]["insc"] / count, 1),
            avg_painting_percent=round(theme_area_sums[name]["paint"] / count, 1),
            avg_blank_percent=round(theme_area_sums[name]["blank"] / count, 1),
        ))

    # ============ 8. 面积-尺寸相关性散点图 ============
    cur.execute(f"""
        SELECT content_analysis, inscription_percent, artwork_height_cm, title, period_phase
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL
          AND content_analysis != ''
          AND content_analysis != '{{}}'
          AND inscription_percent IS NOT NULL
          AND artwork_height_cm IS NOT NULL
    """, artist_params)

    area_size_correlation = []
    for row in cur.fetchall():
        content_json, insc, height, title, period = row
        try:
            analysis = json.loads(content_json)
            themes = analysis.get("themes", [])
            theme_name = themes[0].get("name", "未知") if themes else "未知"
            area_size_correlation.append(AreaSizeItem(
                artwork_height_cm=height,
                inscription_percent=insc,
                theme_name=theme_name,
                title=title or "未命名",
                period=period or "未分期",
            ))
        except Exception:
            continue

    conn.close()

    return StatsResponse(
        artist=artist,
        total_count=total_count,
        period_stats=period_stats,
        theme_distribution=theme_distribution,
        sentiment_distribution=sentiment_distribution,
        layout_form_distribution=layout_form_distribution,
        feature_word_stats=feature_word_stats,
        top_words=[],  # TODO: 从分词结果聚合
        material_tags=material_tags,
        area_distribution=area_distribution,
        area_theme_stats=area_theme_stats,
        area_size_correlation=area_size_correlation,
    )


@router.get("/correlation")
async def get_correlation(
    artist: str = Query(default="all", description="画家名称，'all'表示所有画家"),
):
    """
    内容-形式关联分析（列联表 + 卡方检验）
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    artist_where, artist_params = build_artist_condition(artist)

    cur.execute(f"""
        SELECT content_analysis, position_analysis, period_phase
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL
          AND position_analysis IS NOT NULL
    """, artist_params)

    records = []
    for r in cur.fetchall():
        try:
            pos = json.loads(r[1]) if r[1] else {}
        except Exception:
            pos = {}
        records.append({
            "content_analysis": r[0],
            "position_analysis": pos,
            "period_phase": r[2]
        })
    conn.close()

    if not records:
        return {
            "artist": artist,
            "chi2_statistic": 0.0,
            "p_value": 1.0,
            "significant": False,
            "correlation_table": [],
            "invasive_analysis": {"invasive_items": [], "total": 0},
            "message": "暂无数据"
        }

    contingency = build_contingency_table(records)
    chi2_result = chi_square_test(contingency)
    correlation_stats = compute_correlation_stats(contingency)
    invasive_analysis = get_invasive_analysis(contingency)

    return {
        "artist": artist,
        "chi2_statistic": chi2_result["chi2"],
        "p_value": chi2_result["p_value"],
        "dof": chi2_result.get("dof", 0),
        "significant": chi2_result["significant"],
        "highly_significant": chi2_result.get("highly_significant", False),
        "correlation_table": correlation_stats,
        "invasive_analysis": invasive_analysis,
        "total_records": contingency["total_count"],
    }


@router.post("/batch")
async def batch_analyze(
    editor=Depends(require_editor),
    artist: str = Query(default="all", description="画家名称"),
    force_reanalyze: bool = Query(default=False, description="强制重新分析已校验记录"),
    use_llm: bool = Query(default=True, description="启用LLM双通道情感分析"),
):
    """
    批量触发题跋内容分析
    """
    artist_where, artist_params = build_artist_condition(artist)
    conn = get_db_connection()
    cur = conn.cursor()

    # 获取待分析记录（包含尺寸字段）
    # 增量模式：跳过已有分析结果的记录（content_analysis 非空且非空字典）
    skip_analyzed = "" if force_reanalyze else """
        AND (content_analysis IS NULL
             OR content_analysis = ''
             OR content_analysis = '{}')"""

    cur.execute(f"""
        SELECT id, inscription_content, year, title, analysis_note, 
               artwork_width_cm, artwork_height_cm, artist
        FROM tubi_analyses
        WHERE {artist_where}
          AND inscription_content IS NOT NULL
          AND LENGTH(inscription_content) > 0
        {skip_analyzed}
    """, artist_params)

    rows = cur.fetchall()
    analyzed = 0

    import json
    import asyncio

    async def process_record(record_id, content, year, title, analysis_note, width_cm, height_cm, record_artist=None):
        if use_llm:
            result = await analyze_tiba_content_dual(content, year=year, title=title, analysis_note=analysis_note, 
                                                       width_cm=width_cm, height_cm=height_cm, artist=record_artist)
        else:
            result = analyze_tiba_content(content, year=year, title=title, analysis_note=analysis_note,
                                         width_cm=width_cm, height_cm=height_cm, artist=record_artist)
        content_analysis = {
            "char_count": result.char_count,
            "word_count": result.word_count,
            "ttr": result.ttr,
            "themes": result.themes,
            "sentiment": result.sentiment,
            "feature_words": result.feature_words,
            "objects_mentioned": result.objects_mentioned,
        }
        theme_tags = ",".join([t["name"] for t in result.themes])
        return record_id, content_analysis, theme_tags, year, record_artist

    # 并发处理（限制5个并发）
    semaphore = asyncio.Semaphore(5)

    async def sem_process(record_id, content, year, title, analysis_note, width_cm, height_cm, record_artist=None):
        async with semaphore:
            return await process_record(record_id, content, year, title, analysis_note, width_cm, height_cm, record_artist)

    tasks = [sem_process(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows]
    results = await asyncio.gather(*tasks)

    # 批量更新数据库
    for record_id, content_analysis, theme_tags, year, record_artist in results:
        cur.execute("""
            UPDATE tubi_analyses
            SET char_count = ?,
                word_count = ?,
                theme_tags = ?,
                content_analysis = ?,
                period_phase = ?
            WHERE id = ?
        """, (
            content_analysis["char_count"],
            content_analysis["word_count"],
            theme_tags,
            json.dumps(content_analysis, ensure_ascii=False),
            get_period_phase(year, record_artist),
            record_id
        ))
        analyzed += 1

    conn.commit()
    conn.close()

    return {
        "success": True,
        "analyzed_count": analyzed,
        "artist": artist,
        "force_reanalyze": force_reanalyze
    }


@router.post("/verify/{record_id}", response_model=VerifyResponse)
async def verify_inscription(
    record_id: int,
    request: VerifyRequest,
    editor=Depends(require_editor),
):
    """
    用户校对确认题跋文本。
    如果题跋内容或分析说明发生变化，自动以规则引擎同步重算分析结果，
    确保预览、列表和统计不继续展示旧数据。
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, inscription_content, analysis_note, year, artist,
               artwork_width_cm, artwork_height_cm
        FROM tubi_analyses WHERE id = ?
    """, (record_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Record not found")

    old_content = row["inscription_content"] or ""
    old_note = row["analysis_note"] or ""
    new_content = request.inscription_content or ""
    new_note = request.analysis_note or ""

    content_changed = new_content != old_content
    note_changed = new_note != old_note

    char_count = len(new_content) if new_content else 0

    cur.execute("""
        UPDATE tubi_analyses
        SET inscription_content = ?,
            char_count = ?,
            inscription_verified = 1,
            inscription_verified_at = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        request.inscription_content,
        char_count,
        datetime.now(),
        datetime.now(),
        record_id
    ))

    if request.seal_content is not None:
        cur.execute("""
            UPDATE tubi_analyses
            SET seal_content = ?,
                seal_verified = 1,
                seal_verified_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            request.seal_content,
            datetime.now(),
            datetime.now(),
            record_id
        ))

    if request.analysis_note is not None:
        cur.execute("""
            UPDATE tubi_analyses
            SET analysis_note = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            request.analysis_note,
            datetime.now(),
            record_id
        ))

    analysis_status = "unchanged"
    refreshed_ca = None
    refreshed_theme_tags = None

    if content_changed or note_changed:
        if new_content and len(new_content.strip()) > 0:
            try:
                from app.services.inscription_content_analyzer import analyze_tiba_content

                result = analyze_tiba_content(
                    new_content,
                    year=row["year"],
                    title=None,
                    analysis_note=new_note,
                    width_cm=row["artwork_width_cm"],
                    height_cm=row["artwork_height_cm"],
                    artist=row["artist"]
                )
                refreshed_ca = persist_analysis_result(cur, record_id, result, year=row["year"], artist=row["artist"])
                refreshed_theme_tags = ",".join([t["name"] for t in result.themes])
                analysis_status = "refreshed"
            except Exception:
                stale_analysis_result(cur, record_id)
                analysis_status = "stale"
        else:
            stale_analysis_result(cur, record_id)
            analysis_status = "stale"

    conn.commit()
    conn.close()

    return VerifyResponse(
        success=True,
        message="Text verified and updated",
        record_id=record_id,
        analysis_status=analysis_status,
        content_analysis=refreshed_ca,
        theme_tags=refreshed_theme_tags
    )


@router.get("/records")
async def get_records(
    artist: str = Query(default="all", description="画家名称，'all'表示所有画家"),
    period: Optional[str] = Query(default=None, description="分期筛选"),
    verified_only: bool = Query(default=False, description="仅已校验"),
    keyword: Optional[str] = Query(default=None, description="搜索关键词（作品名/年份/题跋文字）"),
    annotated_status: Optional[str] = Query(default=None, description="标注状态筛选: all/unannotated/annotated"),
    library_id: Optional[int] = Query(default=None, description="按作品库筛选"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0),
):
    """
    获取记录列表（用于校对界面）
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    artist_where, artist_params = build_artist_condition(artist)

    params = list(artist_params)
    where_clauses = [
        artist_where,
        "(page_role IS NULL OR page_role = '')",
    ]

    if library_id is not None:
        where_clauses.append("library_id = ?")
        params.append(library_id)

    if period:
        where_clauses.append("period_phase = ?")
        params.append(period)

    if verified_only:
        where_clauses.append("inscription_verified = 1")

    if keyword:
        where_clauses.append("(title LIKE ? OR CAST(year AS TEXT) LIKE ? OR inscription_content LIKE ?)")
        keyword_filter = f"%{keyword}%"
        params.extend([keyword_filter, keyword_filter, keyword_filter])

    if annotated_status == "annotated":
        where_clauses.append("is_manual_annotated = 1")
    elif annotated_status == "unannotated":
        where_clauses.append("(is_manual_annotated = 0 OR is_manual_annotated IS NULL)")

    # 在这里保存用于 COUNT 查询的 WHERE 条件和参数（在主查询添加 LIMIT/OFFSET 之前）
    count_where = list(where_clauses)  # 复制一份，避免后续修改影响 COUNT 查询
    count_params = list(params)         # 复制一份

    sql = f"""
        SELECT id, image_id, title, year, period_phase,
               inscription_content, inscription_modern, inscription_verified,
               inscription_verified_at,
               seal_content, seal_verified,
               filepath, thumbnail_path,
               content_analysis, analysis_note,
               is_manual_annotated
        FROM tubi_analyses
        WHERE {' AND '.join(where_clauses)}
        ORDER BY (CASE WHEN inscription_verified = 1 THEN 0 ELSE 1 END) ASC, inscription_verified_at DESC, year, id
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    cur.execute(sql, params)
    rows = cur.fetchall()

    import json as _json
    records = []
    for row in rows:
        content_analysis_str = row[13]
        content_analysis = None
        themes = []
        sentiment = None
        if content_analysis_str:
            try:
                content_analysis = _json.loads(content_analysis_str)
                themes = [t.get("name") for t in content_analysis.get("themes", [])]
                sentiment = content_analysis.get("sentiment", {}).get("polarity")
            except Exception:
                pass

        records.append({
            "id": row[0],
            "image_id": row[1],
            "title": row[2],
            "year": row[3],
            "period_phase": row[4],
            "inscription_content": row[5],
            "inscription_modern": row[6],
            "inscription_verified": bool(row[7]),
            "inscription_verified_at": row[8],
            "seal_content": row[9],
            "seal_verified": bool(row[10]),
            "filepath": row[11],
            "thumbnail_path": row[12],
            "content_analysis": content_analysis,
            "theme_tags": themes,
            "sentiment": sentiment,
            "analysis_note": row[14],
            "is_manual_annotated": bool(row[15]) if row[15] else False,
        })

    # 获取总数（使用与主查询相同的 WHERE 条件，仅去掉 LIMIT/OFFSET 参数）
    count_sql = f"""
        SELECT COUNT(*) FROM tubi_analyses
        WHERE {' AND '.join(count_where)}
    """
    cur.execute(count_sql, count_params)
    total = cur.fetchone()[0]

    # 单独计算 verified_count, translated_count, analyzed_count（不受 limit/offset 影响）
    # 所有三个 COUNT 查询都复用相同的 count_params（没有额外参数，因为新增条件都是硬编码的）
    # verified_count
    where_v = list(count_where) + ["inscription_verified = 1"]
    cur.execute(f"SELECT COUNT(*) FROM tubi_analyses WHERE {' AND '.join(where_v)}", count_params)
    verified_count = cur.fetchone()[0]

    # translated_count
    where_t = list(count_where) + ["inscription_modern IS NOT NULL AND LENGTH(inscription_modern) > 0"]
    cur.execute(f"SELECT COUNT(*) FROM tubi_analyses WHERE {' AND '.join(where_t)}", count_params)
    translated_count = cur.fetchone()[0]

    # analyzed_count
    where_a = list(count_where) + [
        "content_analysis IS NOT NULL AND content_analysis != '' AND content_analysis != '{}'"
    ]
    cur.execute(f"SELECT COUNT(*) FROM tubi_analyses WHERE {' AND '.join(where_a)}", count_params)
    analyzed_count = cur.fetchone()[0]

    # annotated_count
    where_anno = list(count_where) + ["is_manual_annotated = 1"]
    cur.execute(f"SELECT COUNT(*) FROM tubi_analyses WHERE {' AND '.join(where_anno)}", count_params)
    annotated_count = cur.fetchone()[0]

    conn.close()

    return {
        "records": records,
        "total": total,
        "verified_count": verified_count,
        "translated_count": translated_count,
        "analyzed_count": analyzed_count,
        "annotated_count": annotated_count,
        "artist": artist,
        "period": period,
    }


class SentimentPaintingsItem(BaseModel):
    id: str
    title: str
    period: str
    char_count: int
    inscription_content: str
    sentiment: str
    confidence: float


class SentimentPaintingsResponse(BaseModel):
    success: bool
    polarity: str
    polarity_name: str
    total: int
    paintings: List[SentimentPaintingsItem]


class PeriodPaintingsItem(BaseModel):
    id: str
    title: str
    period: str
    char_count: int
    inscription_content: str
    sentiment: str
    confidence: float


class PeriodPaintingsResponse(BaseModel):
    success: bool
    period: str
    total: int
    paintings: List[PeriodPaintingsItem]


class ThemePaintingsItem(BaseModel):
    id: str
    title: str
    period: str
    char_count: int
    inscription_content: str
    sentiment: str
    confidence: float


class ThemePaintingsResponse(BaseModel):
    success: bool
    theme_code: int
    theme_name: str
    total: int
    paintings: List[ThemePaintingsItem]


@router.get("/theme/{theme_code}/paintings", response_model=ThemePaintingsResponse)
async def get_theme_paintings(
    theme_code: int,
    artist: str = Query(default="all", description="画家名称，'all'表示所有画家"),
    limit: int = Query(default=5, le=100),
    offset: int = Query(default=0),
):
    """
    按主题 code 获取该主题的所有画作（用于饼图点击弹窗）
    theme_code: 1=记录创作信息, 2=阐述画理画法, 3=即景寄兴与抒怀, 4=世俗祈愿与谐趣, 5=讽喻社会与民生, 6=应酬送人与雅交
    """
    THEME_MAP = {
        1: "记录创作信息",
        2: "即景寄兴与抒怀",
        3: "讽喻社会与民生",
        4: "阐述画理画法",
        5: "世俗祈愿与谐趣",
        6: "应酬送人与雅交",
    }
    theme_name = THEME_MAP.get(theme_code, "未知")

    conn = get_db_connection()
    cur = conn.cursor()
    
    artist_where, artist_params = build_artist_condition(artist)

    params = list(artist_params)
    cur.execute(f"""
        SELECT image_id, title, period_phase, char_count, inscription_content, content_analysis
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL
        ORDER BY id DESC
    """, params)

    paintings = []
    for row in cur.fetchall():
        row_image_id, title, period, char_count, inscription, content_json = row
        try:
            analysis = json.loads(content_json)
            themes = analysis.get("themes", [])
            # 找该记录中匹配指定 theme_code 的主题
            matched = next((t for t in themes if t.get("code") == theme_code), None)
            if matched:
                sentiment = analysis.get("sentiment", {}).get("polarity", "neutral")
                paintings.append(ThemePaintingsItem(
                    id=row_image_id,
                    title=title or f"画作 #{row_image_id}",
                    period=period or "未分期",
                    char_count=char_count or 0,
                    inscription_content=inscription[:80] if inscription else "",
                    sentiment=sentiment,
                    confidence=matched.get("confidence", 0),
                ))
        except:
            continue

    conn.close()

    total = len(paintings)
    paginated = paintings[offset:offset + limit]

    return ThemePaintingsResponse(
        success=True,
        theme_code=theme_code,
        theme_name=theme_name,
        total=total,
        paintings=paginated,
    )


@router.get("/sentiment/{polarity}/paintings", response_model=SentimentPaintingsResponse)
async def get_sentiment_paintings(
    polarity: str,
    artist: str = Query(default="all", description="画家名称，'all'表示所有画家"),
    limit: int = Query(default=5, le=100),
    offset: int = Query(default=0),
):
    """
    按情感极性获取该极性的所有画作（用于饼图点击弹窗）
    polarity: positive / negative / neutral
    """
    POLARITY_MAP = {"positive": "积极", "negative": "消极", "neutral": "中性"}
    polarity_name = POLARITY_MAP.get(polarity, "未知")

    conn = get_db_connection()
    cur = conn.cursor()
    
    artist_where, artist_params = build_artist_condition(artist)
    params = list(artist_params)
    cur.execute(f"""
        SELECT image_id, title, period_phase, char_count, inscription_content, content_analysis
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL
        ORDER BY id DESC
    """, params)

    paintings = []
    for row in cur.fetchall():
        row_image_id, title, period, char_count, inscription, content_json = row
        try:
            analysis = json.loads(content_json)
            sent = analysis.get("sentiment", {})
            if sent.get("polarity") == polarity:
                paintings.append(SentimentPaintingsItem(
                    id=row_image_id,
                    title=title or f"画作 #{row_image_id}",
                    period=period or "未分期",
                    char_count=char_count or 0,
                    inscription_content=inscription[:80] if inscription else "",
                    sentiment=polarity,
                    confidence=sent.get("intensity", 0),
                ))
        except:
            continue

    conn.close()
    total = len(paintings)
    paginated = paintings[offset:offset + limit]

    return SentimentPaintingsResponse(
        success=True,
        polarity=polarity,
        polarity_name=polarity_name,
        total=total,
        paintings=paginated,
    )


# ============ 尺寸统计端点 ============

class SizeStatsResponse(BaseModel):
    artist: str
    total_count: int
    size_distribution: List[Dict[str, Any]]  # [{"category": "小幅", "count": 50, "percentage": 30.5}, ...]
    period_size_distribution: List[Dict[str, Any]]  # [{"period": "早期", "avg_height": 68.5, "avg_width": 45.2, "count": 20}, ...]
    percentile_data: List[float]  # 高度百分位数，用于计算百分位排名 [10th, 25th, 50th, 75th, 90th]


@router.get("/size-stats", response_model=SizeStatsResponse)
async def get_size_stats(
    artist: str = Query(default="all", description="画家名称，'all'表示所有画家"),
):
    """
    获取尺寸统计数据：分布、分期平均、百分位数
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    artist_where, artist_params = build_artist_condition(artist)

    # 1. 获取所有有高度的记录
    cur.execute(f"""
        SELECT artwork_height_cm, artwork_width_cm, period_phase
        FROM tubi_analyses
        WHERE {artist_where}
          AND artwork_height_cm IS NOT NULL
        ORDER BY artwork_height_cm
    """, artist_params)
    rows = cur.fetchall()
    total_count = len(rows)

    if total_count == 0:
        return SizeStatsResponse(
            artist=artist,
            total_count=0,
            size_distribution=[],
            period_size_distribution=[],
            percentile_data=[]
        )

    heights = [r[0] for r in rows if r[0]]

    # 2. 尺寸分组统计
    size_cats = {"小幅": 0, "中幅": 0, "大幅": 0}
    for h in heights:
        if h < 70:
            size_cats["小幅"] += 1
        elif h <= 150:
            size_cats["中幅"] += 1
        else:
            size_cats["大幅"] += 1

    size_distribution = []
    for cat, cnt in size_cats.items():
        size_distribution.append({
            "category": cat,
            "count": cnt,
            "percentage": round(cnt / total_count * 100, 1)
        })

    # 3. 分期尺寸统计
    from collections import defaultdict
    period_data = defaultdict(lambda: {"heights": [], "widths": [], "count": 0})
    for h, w, p in rows:
        period = p or "未分期"
        period_data[period]["heights"].append(h or 0)
        period_data[period]["widths"].append(w or 0)
        period_data[period]["count"] += 1

    period_size_distribution = []
    period_order = ["早期", "中期", "晚期", "年代不详", "未分期"]
    for period in period_order:
        if period not in period_data:
            continue
        data = period_data[period]
        avg_h = sum(data["heights"]) / max(len(data["heights"]), 1)
        avg_w = sum(data["widths"]) / max(len(data["widths"]), 1)
        period_size_distribution.append({
            "period": period,
            "avg_height": round(avg_h, 1),
            "avg_width": round(avg_w, 1),
            "count": data["count"]
        })

    # 4. 百分位数（10/25/50/75/90）
    import math
    percentiles = []
    for p in [10, 25, 50, 75, 90]:
        idx = int(math.ceil(p / 100 * len(heights))) - 1
        percentiles.append(round(heights[max(0, min(idx, len(heights) - 1))], 1))

    conn.close()

    return SizeStatsResponse(
        artist=artist,
        total_count=total_count,
        size_distribution=size_distribution,
        period_size_distribution=period_size_distribution,
        percentile_data=percentiles
    )


# ============ 尺寸百分位端点 ============

class SizePercentileResponse(BaseModel):
    width_cm: Optional[float]
    height_cm: Optional[float]
    size_category: str
    height_percentile: Optional[float]  # 在全集中的百分位（0-100）
    interpretation: str


@router.get("/size-percentile", response_model=SizePercentileResponse)
async def get_size_percentile(
    width: Optional[float] = Query(None, description="作品宽度(cm)"),
    height: Optional[float] = Query(None, description="作品高度(cm)"),
    artist: str = Query(default="all", description="画家名称"),
):
    """
    获取单个作品尺寸的百分位和解读
    """
    from app.services.inscription_content_analyzer import get_size_category, get_size_interpretation, get_period_phase

    artist_where, artist_params = build_artist_condition(artist)
    conn = get_db_connection()
    cur = conn.cursor()

    # 获取所有有高度的记录
    cur.execute(f"""
        SELECT artwork_height_cm
        FROM tubi_analyses
        WHERE {artist_where}
          AND artwork_height_cm IS NOT NULL
        ORDER BY artwork_height_cm
    """, artist_params)
    all_heights = [r[0] for r in cur.fetchall()]
    conn.close()

    size_category = get_size_category(width, height)
    height_percentile = None

    if height and all_heights:
        # 计算高度百分位：有多少作品 <= 当前高度
        count_le = sum(1 for h in all_heights if h <= height)
        height_percentile = round(count_le / len(all_heights) * 100, 1)

    interpretation = get_size_interpretation(size_category)

    return SizePercentileResponse(
        width_cm=width,
        height_cm=height,
        size_category=size_category,
        height_percentile=height_percentile,
        interpretation=interpretation
    )


@router.get("/period/{period}/paintings", response_model=PeriodPaintingsResponse)
async def get_period_paintings(
    period: str,
    artist: str = Query(default="all", description="画家名称，'all'表示所有画家"),
    limit: int = Query(default=5, le=100),
    offset: int = Query(default=0),
):
    """
    按分期获取该时期的所有画作（用于饼图点击弹窗）
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    artist_where, artist_params = build_artist_condition(artist)
    params = list(artist_params) + [period]
    cur.execute(f"""
        SELECT image_id, title, period_phase, char_count, inscription_content, content_analysis
        FROM tubi_analyses
        WHERE {artist_where}
          AND period_phase = ?
          AND content_analysis IS NOT NULL
        ORDER BY id DESC
    """, params)

    paintings = []
    for row in cur.fetchall():
        row_image_id, title, period_phase, char_count, inscription, content_json = row
        try:
            analysis = json.loads(content_json)
            sentiment = analysis.get("sentiment", {}).get("polarity", "neutral")
            confidence = analysis.get("sentiment", {}).get("intensity", 0)
            paintings.append(PeriodPaintingsItem(
                id=row_image_id,
                title=title or f"画作 #{row_image_id}",
                period=period_phase or "未分期",
                char_count=char_count or 0,
                inscription_content=inscription[:80] if inscription else "",
                sentiment=sentiment,
                confidence=confidence,
            ))
        except:
            continue

    conn.close()
    total = len(paintings)
    paginated = paintings[offset:offset + limit]

    return PeriodPaintingsResponse(
        success=True,
        period=period,
        total=total,
        paintings=paginated,
    )


@router.get("/report")
async def get_report(
    artist: str = Query(default="all", description="画家名称，'all'表示所有画家"),
):
    """
    获取 Markdown 分析报告
    """
    from app.services.inscription_report_generator import (
        generate_markdown_report,
        generate_latex_tables,
    )

    conn = get_db_connection()
    cur = conn.cursor()
    
    artist_where, artist_params = build_artist_condition(artist)

    # --- 统计数据（与 /stats 逻辑相同） ---
    stats_data = {"period_stats": [], "theme_distribution": [], "sentiment_distribution": [], "layout_form_distribution": [], "feature_word_stats": [], "total_count": 0}

    cur.execute(f"""
        SELECT period_phase, COUNT(*) as cnt,
               AVG(COALESCE(char_count, 0)) as avg_chars,
               MAX(COALESCE(char_count, 0)) as max_chars,
               MIN(CASE WHEN COALESCE(char_count, 0) > 0 THEN char_count END) as min_chars,
               AVG(COALESCE(word_count, 0)) as avg_words
        FROM tubi_analyses
        WHERE {artist_where}
          AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0
        GROUP BY period_phase ORDER BY period_phase
    """, artist_params)

    for row in cur.fetchall():
        stats_data["period_stats"].append({
            "period": row[0] or "未分期", "count": row[1],
            "avg_char_count": round(row[2] or 0, 1), "max_char_count": row[3] or 0,
            "min_char_count": row[4] or 0, "avg_word_count": round(row[5] or 0, 1),
        })

    cur.execute(f"SELECT COUNT(*) FROM tubi_analyses WHERE {artist_where} AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0",
                artist_params)
    stats_data["total_count"] = cur.fetchone()[0]

    # 主题分布
    cur.execute(f"SELECT period_phase, content_analysis FROM tubi_analyses WHERE {artist_where} AND content_analysis IS NOT NULL",
                artist_params)
    theme_counts, sentiment_counts, feat_words = {}, {}, []
    for row in cur.fetchall():
        period = row[0] or "未分期"
        try:
            analysis = json.loads(row[1])
            for t in analysis.get("themes", []):
                key = (period, t.get("name", "未知"))
                theme_counts[key] = theme_counts.get(key, 0) + 1
            pol = analysis.get("sentiment", {}).get("polarity", "neutral")
            sentiment_counts[(period, pol)] = sentiment_counts.get((period, pol), 0) + 1
        except:
            pass

    period_totals = {}
    for (p, _), c in theme_counts.items():
        period_totals[p] = period_totals.get(p, 0) + c
    for (p, t), c in theme_counts.items():
        stats_data["theme_distribution"].append({
            "period": p, "theme_name": t, "count": c,
            "percentage": round(c / max(period_totals.get(p, 1), 1) * 100, 1),
        })
    for (p, pol), c in sentiment_counts.items():
        stats_data["sentiment_distribution"].append({
            "period": p, "polarity": pol, "count": c,
            "percentage": round(c / max(period_totals.get(p, 1), 1) * 100, 1),
        })

    # 布局形式分布（与 /stats 端点一致）
    cur.execute(f"""
        SELECT position_analysis FROM tubi_analyses
        WHERE {artist_where}
          AND position_analysis IS NOT NULL
    """, artist_params)
    form_counts_summary = {}
    total_form_count_summary = 0
    for row in cur.fetchall():
        try:
            pos = json.loads(row[0])
            for ft in pos.get("form_types", []):
                if ft.get("matched"):
                    name = ft.get("name", "未知")
                    form_counts_summary[name] = form_counts_summary.get(name, 0) + 1
                    total_form_count_summary += 1
        except:
            continue
    for name, count in sorted(form_counts_summary.items(), key=lambda x: x[1], reverse=True):
        stats_data["layout_form_distribution"].append({
            "form_name": name, "count": count,
            "percentage": round(count / max(total_form_count_summary, 1) * 100, 1),
        })

    # --- 关联数据 ---
    cur.execute(f"SELECT content_analysis, position_analysis, period_phase FROM tubi_analyses WHERE {artist_where} AND content_analysis IS NOT NULL AND position_analysis IS NOT NULL",
                artist_params)
    records = [{"content_analysis": r[0], "position_analysis": r[1], "period_phase": r[2]} for r in cur.fetchall()]
    conn.close()

    contingency = build_contingency_table(records)
    chi2_result = chi_square_test(contingency)
    corr_data = {
        "chi2_statistic": chi2_result["chi2"],
        "p_value": chi2_result["p_value"],
        "significant": chi2_result["significant"],
        "invasive_analysis": get_invasive_analysis(contingency),
        "total_records": contingency["total_count"],
    }

    md_report = generate_markdown_report(stats_data, corr_data, artist=artist)
    latex_tables = generate_latex_tables(stats_data, corr_data)

    return {
        "success": True,
        "artist": artist,
        "markdown": md_report,
        "latex": latex_tables,
    }


@router.get("/export/csv")
async def export_csv_report(
    artist: str = Query(default="all", description="画家名称"),
):
    """
    导出 CSV 报告文件
    """
    from fastapi.responses import FileResponse
    from app.services.inscription_report_generator import export_csv

    # 获取统计数据
    stats_resp = await get_stats(artist=artist)
    stats_data = stats_resp.model_dump() if hasattr(stats_resp, "model_dump") else dict(stats_resp)
    corr_resp = await get_correlation(artist=artist)
    corr_data = dict(corr_resp)

    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reports")
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{artist}_题跋分析报告_{datetime.now().strftime('%Y%m%d')}.csv"
    output_path = os.path.join(output_dir, filename)

    export_csv(stats_data, corr_data, output_path)

    return FileResponse(
        output_path,
        media_type="text/csv",
        filename=filename,
    )


# ============ 翻译相关 API ============

class TranslateRequest(BaseModel):
    inscription_content: str


class TranslateResponse(BaseModel):
    success: bool
    record_id: int
    original: str
    modern: str
    message: str


class AnalyzeRequest(BaseModel):
    use_llm: bool = True


class AnalyzeResponse(BaseModel):
    success: bool
    record_id: int
    message: str


@router.post("/translate/{record_id}", response_model=TranslateResponse)
async def translate_single(
    record_id: int,
    request: TranslateRequest,
    editor=Depends(require_editor),
):
    """
    单条记录翻译：将古文题跋翻译为现代文
    """
    from app.services.inscription_translation import translate_inscription

    conn = get_db_connection()
    cur = conn.cursor()

    # 检查记录存在
    cur.execute("SELECT id, inscription_content, inscription_modern FROM tubi_analyses WHERE id = ?", (record_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Record not found")

    # 使用请求中的内容或数据库中的内容
    content = request.inscription_content.strip() if request.inscription_content else row[1]
    if not content:
        conn.close()
        raise HTTPException(status_code=400, detail="题跋内容为空")

    # 调用翻译服务
    result = await translate_inscription(content)

    if not result.success:
        conn.close()
        raise HTTPException(status_code=500, detail=result.error)

    # 更新数据库
    cur.execute("""
        UPDATE tubi_analyses
        SET inscription_modern = ?,
            updated_at = ?
        WHERE id = ?
    """, (result.modern, datetime.now(), record_id))

    conn.commit()
    conn.close()

    return TranslateResponse(
        success=True,
        record_id=record_id,
        original=result.original,
        modern=result.modern,
        message="翻译完成"
    )


@router.post("/analyze/{record_id}", response_model=AnalyzeResponse)
async def analyze_single(
    record_id: int,
    request: AnalyzeRequest = AnalyzeRequest(),
    editor=Depends(require_editor),
):
    """
    单条记录重新分析：调用统一管道 analyze_single_record
    """
    conn = get_db_connection()
    cur = conn.cursor()

    result = await analyze_single_record(record_id, cur)

    conn.commit()
    conn.close()

    if not result["success"]:
        if result.get("error") == "Record not found":
            raise HTTPException(status_code=404, detail="Record not found")
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "分析失败"))

    return {
        "success": True,
        "record_id": record_id,
        "confidence": result["confidence"],
        "themes": result["themes"],
        "sentiment": result["sentiment"],
        "message": f"分析完成，可信度 {result['confidence']:.0%}"
    }


@router.post("/reanalyze-one/{record_id}")
async def reanalyze_single(record_id: int, editor=Depends(require_editor)):
    """
    单条混合引擎分析：调用统一管道 analyze_single_record
    """
    import traceback, sys
    from fastapi.responses import JSONResponse

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        result = await analyze_single_record(record_id, cur)
        conn.commit()
        conn.close()
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "tb": tb[-500:]})

    if not result["success"]:
        if result.get("error") == "Record not found":
            raise HTTPException(status_code=404, detail="Record not found")
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "分析失败"))

    return result


@router.post("/ping-test")
async def ping_test():
    """Minimal test endpoint"""
    return {"ok": True, "msg": "pong"}

    if not result["success"]:
        if result.get("error") == "Record not found":
            raise HTTPException(status_code=404, detail="Record not found")
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "分析失败"))

    return result


@router.post("/analyze-all/{image_id}")
async def analyze_all_spatial_and_text(
    image_id: str,
    editor=Depends(require_editor),
):
    """
    一键全维度分析：空间情绪 + 位置分析 + 文字情感
    前置条件：inscription_verified=1 且 regions 不为空
    """
    from app.services.inscription_content_analyzer import analyze_spatial_emotion
    from app.services.inscription_position_analyzer import analyze_inscription_position_simple
    import json as _json

    conn = get_db_connection()
    cur = conn.cursor()

    # 查询记录
    cur.execute(
        "SELECT id, image_id, inscription_content, regions, blank_percent, content_analysis, "
        "position_analysis, image_width, image_height, year, title, analysis_note, "
        "artwork_width_cm, artwork_height_cm, artist, inscription_verified "
        "FROM tubi_analyses WHERE image_id = ? OR CAST(id AS TEXT) = ?",
        (image_id, image_id)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="记录不存在")

    (db_id, img_id, text, regions_raw, blank_pct, content_raw, position_raw,
     img_w, img_h, year, title, note, w_cm, h_cm, artist, verified) = row

    if not verified:
        conn.close()
        raise HTTPException(status_code=400, detail="题跋尚未校对，请先完成题跋校对")

    # 解析 regions
    regions = None
    if regions_raw:
        try:
            regions = _json.loads(regions_raw) if isinstance(regions_raw, str) else regions_raw
        except Exception:
            pass

    if not regions or not regions.get("inscription_regions"):
        conn.close()
        raise HTTPException(status_code=400, detail="请先完成区域标注（需标注题跋区域）")

    # 1. 题跋位置分析
    position_analysis = None
    try:
        position_analysis = analyze_inscription_position_simple(regions, img_w or 1000, img_h or 1000)
        cur.execute(
            "UPDATE tubi_analyses SET position_analysis = ? WHERE id = ?",
            (_json.dumps(position_analysis, ensure_ascii=False), db_id)
        )
    except Exception as e:
        logger.error(f"位置分析失败: {e}")

    # 2. 空间情绪分析
    spatial_emotion = None
    if position_analysis:
        spatial_emotion = analyze_spatial_emotion(
            position_analysis,
            blank_pct or 50,
            position_analysis.get("coverage_ratio", 0)
        )

    # 3. 文字情感分析（调用现有管道）
    text_analysis = None
    content_analysis = None
    if text:
        try:
            from app.services.inscription_content_analyzer import classify_inscription_v4
            text_analysis = classify_inscription_v4(
                text, year, title, note, w_cm, h_cm, artist
            )
            # 合并现有 content_analysis
            content_analysis = _json.loads(content_raw) if isinstance(content_raw, str) else content_raw
            if not content_analysis or not isinstance(content_analysis, dict):
                content_analysis = {}
            content_analysis["themes"] = [
                {"code": t.theme_code, "name": t.theme_name, "confidence": t.confidence}
                for t in (text_analysis.themes if hasattr(text_analysis, 'themes') else [])
            ]
            content_analysis["sentiment"] = {
                "polarity": text_analysis.sentiment_polarity,
                "intensity": text_analysis.sentiment_intensity,
                "reasoning": text_analysis.reasoning_overall,
            } if hasattr(text_analysis, 'sentiment_polarity') else {}
        except Exception as e:
            logger.error(f"文字分析失败: {e}")

    # 4. 空间情绪 + 合并
    if content_analysis is None:
        content_analysis = _json.loads(content_raw) if isinstance(content_raw, str) else content_raw
        if not content_analysis or not isinstance(content_analysis, dict):
            content_analysis = {}

    if spatial_emotion:
        content_analysis["spatial_emotion"] = spatial_emotion

        # 合并空间+文字综合判断
        text_polarity = content_analysis.get("sentiment", {}).get("polarity", "neutral")
        spatial_signal = spatial_emotion.get("combined_spatial_sentiment", "")
        is_spatial_negative = any(kw in spatial_signal for kw in ["压抑", "宣泄", "紧张"])
        is_spatial_positive = any(kw in spatial_signal for kw in ["正面", "舒展", "狂放", "自信"])

        if text_polarity == "negative" and is_spatial_negative:
            combined_polarity = "negative"
            combined_reasoning = "文字与空间布局均传递压抑信号，情感一致偏负面"
        elif text_polarity == "positive" and is_spatial_positive:
            combined_polarity = "positive"
            combined_reasoning = "文字情感与空间布局均传递积极信号，情感一致偏正面"
        elif text_polarity == "negative" and is_spatial_positive:
            combined_polarity = "ambiguous"
            combined_reasoning = "文字表面消极，但空间布局克制自持，可能为含蓄表达而非真正压抑"
        elif text_polarity == "positive" and is_spatial_negative:
            combined_polarity = "ambiguous"
            combined_reasoning = "文字表面积极，但空间布局暗示压抑，需结合时期背景判断是否为反讽"
        else:
            combined_polarity = text_polarity or "neutral"
            combined_reasoning = "情感信号不显著"

        content_analysis["combined_sentiment"] = {
            "polarity": combined_polarity,
            "reasoning": combined_reasoning,
        }

    # 写入数据库
    cur.execute(
        "UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?",
        (_json.dumps(content_analysis, ensure_ascii=False), db_id)
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "image_id": img_id,
        "spatial_emotion": spatial_emotion,
        "position_analysis": position_analysis,
        "sentiment": content_analysis.get("sentiment"),
        "combined_sentiment": content_analysis.get("combined_sentiment"),
    }


@router.post("/translate/batch")
async def translate_batch(
    editor=Depends(require_editor),
    artist: str = Query(default="all", description="画家名称"),
    force_retranslate: bool = Query(default=False, description="强制重新翻译已翻译记录"),
):
    """
    批量翻译：对已校对但未翻译的记录进行翻译
    """
    from app.services.inscription_translation import translate_inscription

    artist_where, artist_params = build_artist_condition(artist)
    conn = get_db_connection()
    cur = conn.cursor()

    # 获取待翻译记录（已校验但未翻译）
    if force_retranslate:
        cur.execute(f"""
            SELECT id, inscription_content
            FROM tubi_analyses
            WHERE {artist_where}
              AND inscription_content IS NOT NULL
              AND LENGTH(inscription_content) > 0
              AND inscription_verified = 1
        """, artist_params)
    else:
        cur.execute(f"""
            SELECT id, inscription_content
            FROM tubi_analyses
            WHERE {artist_where}
              AND inscription_content IS NOT NULL
              AND LENGTH(inscription_content) > 0
              AND inscription_verified = 1
              AND (inscription_modern IS NULL OR LENGTH(inscription_modern) = 0)
        """, artist_params)

    rows = cur.fetchall()
    translated = 0
    failed = 0

    for row in rows:
        record_id, content = row

        # 调用翻译服务
        result = await translate_inscription(content)

        if result.success:
            cur.execute("""
                UPDATE tubi_analyses
                SET inscription_modern = ?,
                    updated_at = ?
                WHERE id = ?
            """, (result.modern, datetime.now(), record_id))
            translated += 1
        else:
            failed += 1

    conn.commit()
    conn.close()

    return {
        "success": True,
        "translated_count": translated,
        "failed_count": failed,
        "total": len(rows),
        "artist": artist,
        "force_retranslate": force_retranslate
    }


@router.post("/translate/batch/stream")
async def translate_batch_stream(
    editor=Depends(require_editor),
    artist: str = Query(default="all", description="画家名称"),
    force_retranslate: bool = Query(default=False, description="强制重新翻译已翻译记录"),
    library_id: Optional[int] = Query(None, description="按作品库筛选"),
):
    """
    批量翻译（SSE流式）：对已校对但未翻译的记录进行翻译，实时推送进度
    """
    from app.services.inscription_translation import translate_inscription
    import asyncio
    import logging
    logger = logging.getLogger(__name__)

    artist_where, artist_params = build_artist_condition(artist)

    async def event_generator():
        conn = get_db_connection()
        cur = conn.cursor()

        # 构建查询条件
        where_parts = [artist_where]
        params = list(artist_params)
        if library_id is not None:
            where_parts.append("library_id = ?")
            params.append(library_id)

        where_sql = " AND ".join(where_parts)

        # 获取待翻译记录（已校验但未翻译）
        if force_retranslate:
            cur.execute(f"""
                SELECT id, inscription_content
                FROM tubi_analyses
                WHERE {where_sql}
                  AND inscription_content IS NOT NULL
                  AND LENGTH(inscription_content) > 0
                  AND inscription_verified = 1
            """, params)
        else:
            cur.execute(f"""
                SELECT id, inscription_content
                FROM tubi_analyses
                WHERE {where_sql}
                  AND inscription_content IS NOT NULL
                  AND LENGTH(inscription_content) > 0
                  AND inscription_verified = 1
                  AND (inscription_modern IS NULL OR LENGTH(inscription_modern) = 0)
            """, params)

        rows = cur.fetchall()
        total = len(rows)

        # 先发送总条数
        yield f'data: {{"type": "start", "total": {total}, "artist": "{artist}"}}\n\n'

        translated = 0
        failed = 0

        for idx, row in enumerate(rows):
            record_id, content = row

            # 发送正在处理状态
            yield f'data: {{"type": "progress", "current": {idx + 1}, "total": {total}, "status": "translating", "record_id": {record_id}}}\n\n'

            # 调用翻译服务
            result = await translate_inscription(content)
            
            if not result.success:
                logger.error(f"翻译失败 record_id={record_id}: {result.error}")

            if result.success:
                cur.execute("""
                    UPDATE tubi_analyses
                    SET inscription_modern = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (result.modern, datetime.now(), record_id))
                conn.commit()  # 每条成功后立即提交
                translated += 1
                yield f'data: {{"type": "record_done", "current": {idx + 1}, "total": {total}, "record_id": {record_id}, "success": true}}\n\n'
            else:
                failed += 1
                error_msg = str(result.error)[:100].replace('"', '\\"')
                yield f'data: {{"type": "record_done", "current": {idx + 1}, "total": {total}, "record_id": {record_id}, "success": false, "error": "{error_msg}"}}\n\n'

            # 每条之间稍微喘息一下，避免阻塞
            await asyncio.sleep(0.05)

        conn.close()

        # 发送完成状态
        yield f'data: {{"type": "done", "total": {total}, "translated": {translated}, "failed": {failed}}}\n\n'

    from starlette.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        }
    )


# ============ 主题情感重新分类 API（SSE 流式） ============
THEMES_MAP = {
    1: "记录创作信息",
    2: "即景寄兴与抒怀",
    3: "讽喻社会与民生",
    4: "阐述画理画法",
    5: "世俗祈愿与谐趣",
    6: "应酬送人与雅交",
}

THEME_PROMPT_TEMPLATE = """你是一位中国古代书画题跋研究专家。请根据以下题跋内容，严格判断它属于哪个主题类别。

【主题类别定义】
1. 记录创作信息：题跋记录作画时间、地点、画家自述创作经过，或临摹前人画作、题写画名等
2. 即景寄兴与抒怀：题跋描写眼前景物、表达当下感怀、抒发诗情画意（纯粹的写景抒情）
3. 讽喻社会与民生：**重点关注**——包括讽刺官场腐败、揭露官吏欺压、反映民生疾苦（苛捐杂税、农民之苦）、文字狱风险（"夺朱"类敏感词）、市场冷遇（卖画艰难）、感叹世态炎凉/人心险恶（"世味"、"防辣"等）、借物讽世。表面写景但实质含社会批判的作品也归入此类
4. 阐述画理画法：题跋论说绘画技法、笔墨道理、师承渊源、雅俗之辨
5. 世俗祈愿与谐趣：题跋含有吉祥祝福（福寿富贵）、玩笑戏语、或世俗应景之词
6. 应酬送人与雅交：题跋提及为谁而作、请人指教、敬请雅正、赠送友人等应酬交往内容

【判定规则】
- **必须返回至少2个主题**，除非题跋少于5个字（这类极短题跋只归"记录创作信息"）
- 按相关程度排序，但讽喻社会与民生是主导时要排在前面
- 置信度：高度相关=0.9，中度=0.7，低度=0.5

【输出格式】只返回JSON，不要其他文字：
{{"themes": [{{"code": 1, "name": "记录创作信息", "confidence": 0.9}}, {{"code": 2, "name": "即景寄兴与抒怀", "confidence": 0.7}}], "reasoning": "简要说明"}}

【题跋内容】
{inscription}

【输出】"""

SENTIMENT_PROMPT_TEMPLATE = """你是一位中国古代书画题跋情感分析专家。请分析以下题跋的情感倾向。

【情感分类】
- positive（积极）：表达喜悦、畅快、热爱自然、田园雅兴、祝福吉祥等**明显正面**情绪
- negative（消极）：表达悲伤、愤怒、压抑、无奈、不平、讽刺、讥诮、困苦、世态炎凉、怀才不遇、理想受阻等**任何负面或批判性**情绪
- neutral（中性）：仅陈述作画事实（如记录时间地点）、或纯技法描述，无明显情感倾向

【判定规则】只要题跋中有任何负面情绪的蛛丝马迹，就必须判为 negative：
- 叹、悲、愁、苦、恼、愤、憾、哀 → negative
- 世味、世情、防辣、人情冷暖 → negative
- 卖画、利市、佣儿、租税、催租、老、残、衰、败、无力 → negative
- 讽刺、讥诮、无奈、困 → negative

只有明显正面情绪（喜悦、祝福、田园雅兴）才判 positive，其他都判 neutral。

【输出格式】只返回JSON，不要其他文字：
{{"polarity": "negative", "reasoning": "简要说明"}}

【题跋内容】
{inscription}

【输出】"""


def call_llm_json(prompt: str, model: str, api_key: str, base_url: str) -> dict:
    """调用 LLM 并解析 JSON 响应"""
    import httpx
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位严谨的中国古代书画题跋研究专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 512
    }
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(content)


@router.post("/reclassify/stream")
async def reclassify_themes_sentiment(
    editor=Depends(require_editor),
    artist: str = Query(default="all", description="画家名称"),
    force_reanalyze: bool = Query(default=False, description="强制重新分类所有记录"),
):
    """
    批量重新分类主题和情感（SSE流式），使用v3专家规则
    """
    import asyncio as _asyncio
    from starlette.responses import StreamingResponse
    from app.services.inscription_content_analyzer import llm_theme_classification_v3, llm_sentiment_analysis_v3, classify_inscription_v4, llm_analyze_combined, detect_sentiment_theme_conflict, llm_retry_with_conflict

    artist_where, artist_params = build_artist_condition(artist)

    async def event_generator():
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # 增量模式：只处理已校对、已翻译、但未分析的记录
            if force_reanalyze:
                extra_where = ""
            else:
                extra_where = """
                  AND inscription_verified = 1
                  AND inscription_modern IS NOT NULL
                  AND LENGTH(inscription_modern) > 0
                  AND (content_analysis IS NULL
                       OR content_analysis = ''
                       OR content_analysis = '{}')"""

            cur.execute(f"""
                SELECT id, inscription_content, content_analysis, year, title, analysis_note,
                       artwork_width_cm, artwork_height_cm, artist
                FROM tubi_analyses
                WHERE {artist_where}
                  AND inscription_content IS NOT NULL
                  AND LENGTH(inscription_content) > 0
                {extra_where}
            """, artist_params)
            rows = cur.fetchall()
            total = len(rows)

            yield f'data: {{"type": "start", "total": {total}, "artist": "{artist}"}}\n\n'

            updated = 0
            errors = 0

            for idx, (record_id, content, old_ca, year, title, analysis_note, width_cm, height_cm, record_artist) in enumerate(rows):
                yield f'data: {{"type": "progress", "current": {idx + 1}, "total": {total}, "status": "analyzing", "record_id": {record_id}}}\n\n'

                try:
                    # 步骤1：调用组合LLM分析（一次API同时返回主题+情感）
                    llm_result = await llm_analyze_combined(content.strip(), artist=record_artist)
                    
                    if not llm_result.get("success"):
                        # LLM调用失败时，回退到v4本地规则
                        v4_result = classify_inscription_v4(content.strip(), year=year, title=title, analysis_note=analysis_note,
                                                             inscription_content=content.strip(),
                                                             width_cm=width_cm, height_cm=height_cm, artist=record_artist)
                        themes = v4_result["themes"]
                        sentiment = v4_result["sentiment"]
                        sentiment["fallback"] = True
                        sentiment["fallback_reason"] = llm_result.get("error", "LLM调用失败")
                        retry_used = False
                    else:
                        # LLM调用成功，检查是否有矛盾
                        llm_themes = llm_result.get("themes", [])
                        llm_sentiment = llm_result.get("sentiment", {})
                        
                        # 步骤2：检测主题和情感的矛盾
                        has_conflict, conflict_desc = detect_sentiment_theme_conflict(
                            content.strip(), llm_themes, llm_sentiment
                        )
                        
                        if has_conflict:
                            # 步骤3：矛盾时重试
                            retry_result = await llm_retry_with_conflict(
                                content.strip(), llm_themes, llm_sentiment, conflict_desc
                            )
                            if retry_result.get("success"):
                                themes = retry_result.get("themes", llm_themes)
                                sentiment = retry_result.get("sentiment", llm_sentiment)
                                sentiment["retry_applied"] = True
                                sentiment["conflict_detected"] = True
                                sentiment["conflict_description"] = conflict_desc
                                sentiment["retry_explanation"] = retry_result.get("explanation", "")
                            else:
                                # 重试失败，采用第一次结果但标记有矛盾
                                themes = llm_themes
                                sentiment = llm_sentiment
                                sentiment["retry_failed"] = True
                                sentiment["conflict_detected"] = True
                                sentiment["conflict_description"] = conflict_desc
                        else:
                            themes = llm_themes
                            sentiment = llm_sentiment
                        
                        retry_used = llm_result.get("retry_used", False)
                    
                    # v4信号作为参考保存
                    v4_result = classify_inscription_v4(content.strip(), year=year, title=title, analysis_note=analysis_note,
                                                         inscription_content=content.strip(),
                                                         width_cm=width_cm, height_cm=height_cm, artist=record_artist)

                    # 验证themes
                    valid_themes = []
                    for t in themes:
                        if isinstance(t, dict) and "code" in t and 1 <= t["code"] <= 6:
                            valid_themes.append({
                                "code": t["code"],
                                "name": THEMES_MAP.get(t["code"], "未知"),
                                "confidence": min(float(t.get("confidence", 0.5)), 0.95),
                            })

                    if not valid_themes:
                        valid_themes = [{"code": 1, "name": "记录创作信息", "confidence": 0.9}]

                    valid_themes.sort(key=lambda x: x.get("confidence", 0), reverse=True)
                    theme_tags = ",".join([f"{t['name']}:{t['confidence']}" for t in valid_themes])

                    polarity = sentiment.get("polarity", "neutral")
                    if polarity not in ("positive", "negative", "neutral"):
                        polarity = "neutral"
                    
                    # 情感强度
                    intensity = sentiment.get("intensity", 0.5)
                    if isinstance(intensity, (int, float)) and intensity > 1:
                        intensity = min(intensity / 3, 1.0)
                    
                    final_sentiment = {
                        "polarity": polarity,
                        "intensity": round(float(intensity), 2),
                        "reasoning": sentiment.get("reasoning", ""),
                    }
                    
                    # 添加调试信息
                    if sentiment.get("retry_applied"):
                        final_sentiment["retry_applied"] = True
                    if sentiment.get("conflict_detected"):
                        final_sentiment["conflict_detected"] = True
                        final_sentiment["conflict_description"] = sentiment.get("conflict_description", "")

                    old_data = json.loads(old_ca) if old_ca else {}
                    old_data["themes"] = valid_themes
                    old_data["sentiment"] = final_sentiment
                    # 保存v4信号作为参考
                    if "feature_words" not in old_data:
                        old_data["feature_words"] = {}
                    old_data["feature_words"]["v4_signals"] = v4_result.get("signals", {})
                    old_data["feature_words"]["v4_special_rules"] = v4_result.get("special_rules", [])

                    # 计算分期（使用画家出生年份动态计算）
                    period_phase_val = get_period_phase(year, record_artist)
                    cur.execute("""
                        UPDATE tubi_analyses
                        SET content_analysis = ?, theme_tags = ?, period_phase = ?, updated_at = ?
                        WHERE id = ?
                    """, (json.dumps(old_data, ensure_ascii=False), theme_tags, period_phase_val, datetime.now(), record_id))
                    conn.commit()
                    updated += 1

                    yield f'data: {{"type": "record_done", "current": {idx + 1}, "total": {total}, "record_id": {record_id}, "success": true, "codes": "{"/".join(str(t["code"]) for t in valid_themes)}", "polarity": "{polarity}"}}\n\n'

                except Exception as e:
                    errors += 1
                    yield f'data: {{"type": "record_done", "current": {idx + 1}, "total": {total}, "record_id": {record_id}, "success": false, "error": "{str(e)[:80]}"}}\n\n'

                await _asyncio.sleep(0.05)

            conn.close()

            yield f'data: {{"type": "done", "total": {total}, "analyzed_count": {updated}, "errors": {errors}}}\n\n'

        except Exception as e:
            import traceback as _tb
            yield f'data: {{"type": "error", "message": "{str(e)[:100]}", "traceback": "{_tb.format_exc()[:200].replace(chr(10), " ")}"}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/batch-reanalyze")
async def batch_reanalyze(
    editor=Depends(require_editor),
    artist: str = Query(default="all", description="画家名称，all 表示全部"),
    incremental: bool = Query(default=False, description="增量模式：跳过已处理的记录（已有 v4_confidence + rules_version ≥ 5.5）"),
    library_id: Optional[int] = Query(None, description="按作品库筛选"),
):
    """
    统一分析引擎（规则 + 低可信度自动 DeepSeek 修正）。

    每条记录经过统一管道：
      1. 规则引擎 classify_inscription_v4 → 算出可信度
      2. 可信度 < 0.6 → 自动调 DeepSeek 二次判断
      3. 若有分歧 → 采纳 LLM 结论，标记 [LLM采纳]
      4. 保存到 DB

    incremental=true 时跳过已完整分析过的记录（已有 content_analysis.rules_version ≥ 5.5）。
    不存在覆盖问题——每条记录只用此管道跑一次。
    """
    import logging
    logger = logging.getLogger(__name__)
    from app.services.inscription_content_analyzer import classify_inscription_v4, THEME_NAME_MIGRATION, _load_artist_rules
    from app.services.tibi_analysis_rules import EXPECTED_THEME_DISTRIBUTION as _DEFAULT_EXPECTED_THEME
    from app.services.tibi_analysis_rules import EXPECTED_SENTIMENT_DISTRIBUTION as _DEFAULT_EXPECTED_SENTIMENT
    from app.services.auto_tags import compute_tags
    from collections import Counter
    import json

    artist_rules = _load_artist_rules(artist if artist and artist != "all" else "李鱓")
    EXPECTED_THEME_DISTRIBUTION = artist_rules.get("expected_theme_distribution", _DEFAULT_EXPECTED_THEME)
    EXPECTED_SENTIMENT_DISTRIBUTION = artist_rules.get("expected_sentiment_distribution", _DEFAULT_EXPECTED_SENTIMENT)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # ── 构建查询条件 ──────────────────────────────────
    where_clauses = []
    params = []

    if library_id is not None:
        where_clauses.append("library_id = ?")
        params.append(library_id)
    elif artist and artist != "all":
        where_clauses.append("artist = ?")
        params.append(artist)

    if incremental:
        # 增量模式：跳过已处理过的记录
        where_clauses.append(
            "(content_analysis IS NULL OR content_analysis = '' OR json_extract(content_analysis, '$.rules_version') IS NULL OR json_extract(content_analysis, '$.rules_version') < '5.5')"
        )

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cur.execute(f"""
        SELECT id, inscription_content, year, title, analysis_note,
               artwork_width_cm, artwork_height_cm, artist, content_analysis, period_phase
        FROM tubi_analyses
        {where_sql}
        ORDER BY id
    """, params)
    rows = cur.fetchall()
    total = len(rows)
    
    # 统计变量（用于生成对比报告）
    old_themes = Counter()           # all themes (1st+2nd+3rd) — 覆盖率
    old_primary_themes = Counter()   # 仅第一主题 — 分布
    new_themes = Counter()
    new_primary_themes = Counter()
    old_polarities = Counter()
    new_polarities = Counter()
    old_emotion_scores = []
    new_emotion_scores = []
    theme_changes = Counter()        # (旧主题→新主题) 变化统计
    confidences = []                 # v2.1: 可信度分布
    low_conf_records = []            # v2.2: 低可信度记录（record_id 列表）
    llm_corrected = 0    # 混合模式下人工智能修正的数量
    llm_errors = 0       # LLM调用失败数

    updated = 0
    errors = 0
    
    for row in rows:
        record_id = row["id"]
        text = row["inscription_content"] or ""
        year = row["year"]
        title = row["title"]
        analysis_note = row["analysis_note"]
        width_cm = row["artwork_width_cm"]
        height_cm = row["artwork_height_cm"]
        record_artist = row["artist"]

        # 解析旧 content_analysis
        old_ca = None
        if row["content_analysis"]:
            try:
                old_ca = json.loads(row["content_analysis"])
            except Exception:
                pass

        # 记录旧主题/情感
        if old_ca:
            themes_list = old_ca.get("themes", [])
            for t in themes_list:
                old_name = t.get("name", "")
                compat_name = THEME_NAME_MIGRATION.get(old_name, old_name)
                old_themes[compat_name] += 1
            if themes_list:
                old_primary_themes[THEME_NAME_MIGRATION.get(themes_list[0].get("name",""), themes_list[0].get("name",""))] += 1
            old_sent = old_ca.get("sentiment", {})
            old_pol = old_sent.get("polarity", "neutral")
            old_polarities[old_pol] += 1
            old_score = old_sent.get("emotion_score")
            if old_score is not None:
                old_emotion_scores.append(old_score)

        try:
            # 调用统一分析管道
            result = await analyze_single_record(record_id, cur)

            if not result["success"]:
                errors += 1
                if errors <= 5:
                    logger.error(f"批量重跑失败 id={record_id}: {result.get('error')}")
                continue

            conf = result["confidence"]
            confidences.append(conf)
            if result.get("llm_fixed"):
                llm_corrected += 1
            if result.get("llm_error"):
                llm_errors += 1

            if conf < 0.6:
                low_conf_records.append(record_id)

            # 记录新主题/情感（用于对比报告）
            new_themes_list = result.get("themes", [])
            for t in new_themes_list:
                new_themes[t["name"]] += 1
            if new_themes_list:
                new_primary_themes[new_themes_list[0]["name"]] += 1
            new_sent = result.get("sentiment", {})
            new_pol = new_sent.get("polarity", "neutral")
            new_polarities[new_pol] += 1
            new_score = new_sent.get("emotion_score")
            if new_score is not None:
                new_emotion_scores.append(new_score)
            
            # 记录主题变化
            old_main = ""
            if old_ca and old_ca.get("themes"):
                old_main = old_ca["themes"][0].get("name", "")
                old_main = THEME_NAME_MIGRATION.get(old_main, old_main)
            new_main = result["themes"][0]["name"] if result.get("themes") else ""
            if old_main and new_main and old_main != new_main:
                theme_changes[(old_main, new_main)] += 1
            
            # 注意：analyze_single_record 已经完成了 DB 保存和 auto_tags 计算，只需 commit
            conn.commit()

            updated += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                logger.error(f"批量重跑错误 id={record_id}: {e}")

    conn.commit()
    conn.close()
    
    # ═══════════════════════════════════════════════════════════════════
    # 生成对比报告（与 rebatch_analyze_li_shan.py 脚本格式一致）
    # ═══════════════════════════════════════════════════════════════════
    
    # 1. 主题覆盖率对比（all themes = 1st+2nd+3rd 覆盖率）
    all_theme_names = sorted(set(list(old_themes.keys()) + list(new_themes.keys())))
    theme_coverage = []
    for name in all_theme_names:
        old_cnt = old_themes.get(name, 0)
        new_cnt = new_themes.get(name, 0)
        old_pct = round(old_cnt / total * 100, 1) if total else 0
        new_pct = round(new_cnt / total * 100, 1) if total else 0
        diff = new_cnt - old_cnt
        theme_coverage.append({
            "name": name,
            "old_count": old_cnt,
            "old_percent": old_pct,
            "new_count": new_cnt,
            "new_percent": new_pct,
            "change": diff
        })
    
    # 1.5. 第一主题分布对比（Primary Themes）
    primary_names = sorted(set(list(old_primary_themes.keys()) + list(new_primary_themes.keys())))
    primary_theme_dist = []
    for name in primary_names:
        old_cnt = old_primary_themes.get(name, 0)
        new_cnt = new_primary_themes.get(name, 0)
        old_pct = round(old_cnt / total * 100, 1) if total else 0
        new_pct = round(new_cnt / total * 100, 1) if total else 0
        diff = new_cnt - old_cnt
        primary_theme_dist.append({
            "name": name,
            "old_count": old_cnt,
            "old_percent": old_pct,
            "new_count": new_cnt,
            "new_percent": new_pct,
            "change": diff
        })
    
    # 2. 情感分布对比
    sentiment_dist = []
    for pol in ["positive", "negative", "neutral"]:
        old_cnt = old_polarities.get(pol, 0)
        new_cnt = new_polarities.get(pol, 0)
        old_pct = round(old_cnt / total * 100, 1) if total else 0
        new_pct = round(new_cnt / total * 100, 1) if total else 0
        diff = new_cnt - old_cnt
        sentiment_dist.append({
            "polarity": pol,
            "old_count": old_cnt,
            "old_percent": old_pct,
            "new_count": new_cnt,
            "new_percent": new_pct,
            "change": diff
        })
    
    # 3. 情感分数对比
    emotion_score_stats = {}
    if new_emotion_scores:
        new_avg = sum(new_emotion_scores) / len(new_emotion_scores)
        old_avg = sum(old_emotion_scores) / len(old_emotion_scores) if old_emotion_scores else None
        emotion_score_stats = {
            "new_average": round(new_avg, 2),
            "old_average": round(old_avg, 2) if old_avg is not None else None,
            "new_min": round(min(new_emotion_scores), 2),
            "new_max": round(max(new_emotion_scores), 2),
        }
    
    # 4. 主题变化路径（Top 10）
    theme_change_paths = []
    for (old_t, new_t), cnt in theme_changes.most_common(10):
        theme_change_paths.append({
            "from": old_t,
            "to": new_t,
            "count": cnt
        })

    # 4.5. 置信度分布（v2.1）
    if confidences:
        high_conf = sum(1 for c in confidences if c >= 0.7)
        mid_conf = sum(1 for c in confidences if 0.4 <= c < 0.7)
        low_conf = sum(1 for c in confidences if c < 0.4)
        avg_conf = round(sum(confidences) / len(confidences), 2)
        confidence_stats = {
            "average": avg_conf,
            "high": high_conf,
            "high_percent": round(high_conf / total * 100, 1) if total else 0,
            "mid": mid_conf,
            "mid_percent": round(mid_conf / total * 100, 1) if total else 0,
            "low": low_conf,
            "low_percent": round(low_conf / total * 100, 1) if total else 0,
        }
    else:
        confidence_stats = None

    # 5. 偏差检测与调整建议（基于第一主题）
    # 从规则中心读取预期分布，保证与算法版本同步
    deviation_checks = []
    for name, (low, high) in EXPECTED_THEME_DISTRIBUTION.items():
        cnt = new_primary_themes.get(name, 0)
        pct = round(cnt / total * 100, 1) if total else 0
        if pct < low:
            status = "warning"
            suggestion = f"低于预期下限 {low}% -- 建议增加关键词权重或补充关键词"
        elif pct > high:
            status = "warning"
            suggestion = f"高于预期上限 {high}% -- 建议收紧定义或降低权重"
        else:
            status = "ok"
            suggestion = f"在预期范围内 [{low}%-{high}%]"
        deviation_checks.append({
            "theme": name,
            "percent": pct,
            "status": status,
            "suggestion": suggestion,
            "expected_range": [low, high]
        })
    
    # 情感偏差检测（从规则中心读取阈值）
    neg_pct = round(new_polarities.get("negative", 0) / total * 100, 1) if total else 0
    pos_pct = round(new_polarities.get("positive", 0) / total * 100, 1) if total else 0
    if neg_pct < EXPECTED_SENTIMENT_DISTRIBUTION["negative_min"]:
        deviation_checks.append({
            "theme": "消极情感",
            "percent": neg_pct,
            "status": "warning",
            "suggestion": f"低于预期{EXPECTED_SENTIMENT_DISTRIBUTION['negative_min']}% -- 李鱓'懊道人'底色应更偏阴",
            "expected_range": [EXPECTED_SENTIMENT_DISTRIBUTION["negative_min"], 100]
        })
    if pos_pct > EXPECTED_SENTIMENT_DISTRIBUTION["positive_max"]:
        deviation_checks.append({
            "theme": "积极情感",
            "percent": pos_pct,
            "status": "warning",
            "suggestion": f"高于预期{EXPECTED_SENTIMENT_DISTRIBUTION['positive_max']}% -- 可能被花鸟题材误导",
            "expected_range": [0, EXPECTED_SENTIMENT_DISTRIBUTION["positive_max"]]
        })
    if emotion_score_stats.get("new_average") is not None:
        avg = emotion_score_stats["new_average"]
        emotion_mean_max = EXPECTED_SENTIMENT_DISTRIBUTION["emotion_mean_max"]
        if avg > emotion_mean_max:
            deviation_checks.append({
                "theme": "情感均值",
                "percent": avg,
                "status": "warning",
                "suggestion": f"{avg:+.2f} 偏阳 -- 李鱓整体应偏阴(预期 < {emotion_mean_max})",
                "expected_range": [-100, emotion_mean_max]
            })
        else:
            deviation_checks.append({
                "theme": "情感均值",
                "percent": avg,
                "status": "ok",
                "suggestion": f"{avg:+.2f} 符合李鱓偏阴底色",
                "expected_range": [-100, emotion_mean_max]
            })
    
    return {
        "success": True,
        "total": total,
        "updated": updated,
        "errors": errors,
        "message": f"批量重跑完成：{updated} 幅更新，{errors} 幅错误" + (f"，人工智能修正 {llm_corrected} 幅" if llm_corrected > 0 else "") + (f"，LLM调用失败 {llm_errors} 次" if llm_errors > 0 else ""),
        # 详细对比报告数据
        "report": {
            "theme_coverage": theme_coverage,
            "primary_theme_distribution": primary_theme_dist,
            "sentiment_distribution": sentiment_dist,
            "emotion_score_stats": emotion_score_stats,
            "theme_change_paths": theme_change_paths,
            "deviation_checks": deviation_checks,
            "confidence_stats": confidence_stats,
            "low_conf_count": len(low_conf_records),
            "llm_corrected": llm_corrected,
            "llm_errors": llm_errors,
        }
    }


@router.post("/batch-reanalyze/stream")
async def batch_reanalyze_stream(
    editor=Depends(require_editor),
    artist: str = Query(default="all", description="画家名称，all 表示全部"),
    incremental: bool = Query(default=False, description="增量模式"),
    library_id: Optional[int] = Query(None, description="按作品库筛选"),
):
    """
    批量重跑 SSE 流式版本：实时推送每条记录的进度。
    与 /batch-reanalyze 逻辑完全相同，区别在于通过 SSE 推送进度事件。
    """
    from starlette.responses import StreamingResponse

    async def event_generator():
        import logging, json as _json
        logger = logging.getLogger(__name__)
        from app.services.inscription_content_analyzer import classify_inscription_v4, THEME_NAME_MIGRATION, _load_artist_rules, llm_analyze_combined
        from app.services.tibi_analysis_rules import EXPECTED_THEME_DISTRIBUTION as _DEFAULT_EXPECTED_THEME
        from app.services.tibi_analysis_rules import EXPECTED_SENTIMENT_DISTRIBUTION as _DEFAULT_EXPECTED_SENTIMENT
        from app.services.auto_tags import compute_tags
        from collections import Counter
        from datetime import datetime

        def sse(event_type: str, data: dict):
            return f"data: {_json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"

        artist_rules = _load_artist_rules(artist if artist and artist != "all" else "李鱓")
        EXPECTED_THEME_DISTRIBUTION = artist_rules.get("expected_theme_distribution", _DEFAULT_EXPECTED_THEME)
        EXPECTED_SENTIMENT_DISTRIBUTION = artist_rules.get("expected_sentiment_distribution", _DEFAULT_EXPECTED_SENTIMENT)

        conn = get_db_connection()
        cur = conn.cursor()

        where_clauses = []
        params = []
        if library_id is not None:
            where_clauses.append("library_id = ?")
            params.append(library_id)
        elif artist and artist != "all":
            where_clauses.append("artist = ?")
            params.append(artist)
        if incremental:
            where_clauses.append(
                "(content_analysis IS NULL OR content_analysis = '' OR json_extract(content_analysis, '$.rules_version') IS NULL OR json_extract(content_analysis, '$.rules_version') < '5.5')"
            )
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cur.execute(f"""
            SELECT id, inscription_content, year, title, analysis_note,
                   artwork_width_cm, artwork_height_cm, artist, content_analysis, period_phase
            FROM tubi_analyses {where_sql}
            ORDER BY id
        """, params)
        rows = cur.fetchall()
        total = len(rows)

        yield sse("total", {"total": total, "incremental": incremental})

        # 统计变量
        old_themes = Counter()
        old_primary_themes = Counter()
        new_themes = Counter()
        new_primary_themes = Counter()
        old_polarities = Counter()
        new_polarities = Counter()
        old_emotion_scores = []
        new_emotion_scores = []
        theme_changes = Counter()
        confidences = []
        low_conf_records = []
        llm_corrected = 0
        llm_errors = 0
        updated = 0
        errors = 0

        for idx, row in enumerate(rows):
            record_id = row["id"]
            text = row["inscription_content"] or ""
            year = row["year"]
            title = row["title"]
            analysis_note = row["analysis_note"]
            width_cm = row["artwork_width_cm"]
            height_cm = row["artwork_height_cm"]
            record_artist = row["artist"]

            # 解析旧 content_analysis
            old_ca = None
            if row["content_analysis"]:
                try:
                    old_ca = _json.loads(row["content_analysis"])
                except Exception:
                    pass

            if old_ca:
                themes_list = old_ca.get("themes", [])
                for t in themes_list:
                    old_name = t.get("name", "")
                    compat_name = THEME_NAME_MIGRATION.get(old_name, old_name)
                    old_themes[compat_name] += 1
                if themes_list:
                    old_primary_themes[THEME_NAME_MIGRATION.get(themes_list[0].get("name",""), themes_list[0].get("name",""))] += 1
                old_sent = old_ca.get("sentiment", {})
                old_pol = old_sent.get("polarity", "neutral")
                old_polarities[old_pol] += 1
                old_score = old_sent.get("emotion_score")
                if old_score is not None:
                    old_emotion_scores.append(old_score)

            try:
                # 调用统一分析管道
                analysis = await analyze_single_record(record_id, cur)

                if not analysis["success"]:
                    errors += 1
                    yield sse("record_done", {"current": idx + 1, "total": total, "record_id": record_id, "success": False, "error": analysis.get("error", "分析失败")})
                    continue

                conf = analysis["confidence"]
                confidences.append(conf)

                if analysis.get("llm_fixed"):
                    llm_corrected += 1
                    yield sse("llm_fix", {
                        "record_id": record_id,
                        "from_theme": analysis.get("llm_detail", ""),
                        "confidence": conf,
                    })
                if analysis.get("llm_error"):
                    llm_errors += 1

                if conf < 0.6:
                    low_conf_records.append(record_id)

                # 记录新主题/情感（用于对比报告）
                new_themes_list = analysis.get("themes", [])
                for t in new_themes_list:
                    new_themes[t["name"]] += 1
                if new_themes_list:
                    new_primary_themes[new_themes_list[0]["name"]] += 1
                new_sent = analysis.get("sentiment", {})
                new_pol = new_sent.get("polarity", "neutral")
                new_polarities[new_pol] += 1
                new_score = new_sent.get("emotion_score")
                if new_score is not None:
                    new_emotion_scores.append(new_score)

                # 记录主题变化
                old_main = ""
                if old_ca and old_ca.get("themes"):
                    old_main = old_ca["themes"][0].get("name", "")
                    old_main = THEME_NAME_MIGRATION.get(old_main, old_main)
                new_main = analysis["themes"][0]["name"] if analysis.get("themes") else ""
                if old_main and new_main and old_main != new_main:
                    theme_changes[(old_main, new_main)] += 1

                # 注意：analyze_single_record 已完成 DB 保存和 auto_tags
                conn.commit()

                updated += 1

            except Exception as e:
                errors += 1
                logger.error(f"记录 {record_id} 重跑失败: {str(e)[:80]}")

            # 每处理一条推送进度
            yield sse("progress", {
                "current": idx + 1,
                "total": total,
                "record_id": record_id,
                "confidence": locals().get("conf", 0),
                "fixed_by_llm": locals().get("analysis", {}).get("llm_fixed", False),
            })

        conn.commit()

        # 构建报告
        theme_coverage = []
        all_theme_names = sorted(set(list(old_themes.keys()) + list(new_themes.keys())))
        for name in all_theme_names:
            old_cnt = old_themes.get(name, 0)
            new_cnt = new_themes.get(name, 0)
            old_pct = round(old_cnt / total * 100, 1) if total else 0
            new_pct = round(new_cnt / total * 100, 1) if total else 0
            diff = new_cnt - old_cnt
            theme_coverage.append({"name": name, "old_count": old_cnt, "old_percent": old_pct, "new_count": new_cnt, "new_percent": new_pct, "change": diff})

        primary_names = sorted(set(list(old_primary_themes.keys()) + list(new_primary_themes.keys())))
        primary_theme_dist = []
        for name in primary_names:
            old_cnt = old_primary_themes.get(name, 0)
            new_cnt = new_primary_themes.get(name, 0)
            old_pct = round(old_cnt / total * 100, 1) if total else 0
            new_pct = round(new_cnt / total * 100, 1) if total else 0
            diff = new_cnt - old_cnt
            primary_theme_dist.append({"name": name, "old_count": old_cnt, "old_percent": old_pct, "new_count": new_cnt, "new_percent": new_pct, "change": diff})

        sentiment_dist = []
        for pol in ["positive", "negative", "neutral"]:
            old_cnt = old_polarities.get(pol, 0)
            new_cnt = new_polarities.get(pol, 0)
            old_pct = round(old_cnt / total * 100, 1) if total else 0
            new_pct = round(new_cnt / total * 100, 1) if total else 0
            diff = new_cnt - old_cnt
            sentiment_dist.append({"polarity": pol, "old_count": old_cnt, "old_percent": old_pct, "new_count": new_cnt, "new_percent": new_pct, "change": diff})

        emotion_score_stats = {}
        if new_emotion_scores:
            new_avg = sum(new_emotion_scores) / len(new_emotion_scores)
            old_avg = sum(old_emotion_scores) / len(old_emotion_scores) if old_emotion_scores else None
            emotion_score_stats = {"new_average": round(new_avg, 2), "old_average": round(old_avg, 2) if old_avg is not None else None, "new_min": round(min(new_emotion_scores), 2), "new_max": round(max(new_emotion_scores), 2)}

        theme_change_paths = []
        for (old_t, new_t), cnt in theme_changes.most_common(10):
            theme_change_paths.append({"from": old_t, "to": new_t, "count": cnt})

        confidence_stats = None
        if confidences:
            high_conf = sum(1 for c in confidences if c >= 0.7)
            mid_conf = sum(1 for c in confidences if 0.4 <= c < 0.7)
            low_conf = sum(1 for c in confidences if c < 0.4)
            avg_conf = round(sum(confidences) / len(confidences), 2)
            confidence_stats = {"average": avg_conf, "high": high_conf, "high_percent": round(high_conf / total * 100, 1) if total else 0, "mid": mid_conf, "mid_percent": round(mid_conf / total * 100, 1) if total else 0, "low": low_conf, "low_percent": round(low_conf / total * 100, 1) if total else 0}

        deviation_checks = []
        for name, (low, high) in EXPECTED_THEME_DISTRIBUTION.items():
            cnt = new_primary_themes.get(name, 0)
            pct = round(cnt / total * 100, 1) if total else 0
            if pct < low:
                status, suggestion = "warning", f"低于预期下限 {low}% -- 建议增加关键词权重或补充关键词"
            elif pct > high:
                status, suggestion = "warning", f"高于预期上限 {high}% -- 建议收紧定义或降低权重"
            else:
                status, suggestion = "ok", f"在预期范围内 [{low}%-{high}%]"
            deviation_checks.append({"theme": name, "percent": pct, "status": status, "suggestion": suggestion, "expected_range": [low, high]})

        if sentiment_dist:
            neg_pct = sentiment_dist[1]["new_percent"] if sentiment_dist[1]["polarity"] == "negative" else 0
            pos_pct = sentiment_dist[0]["new_percent"] if sentiment_dist[0]["polarity"] == "positive" else 0
            neg_min = EXPECTED_SENTIMENT_DISTRIBUTION["negative_min"]
            pos_max = EXPECTED_SENTIMENT_DISTRIBUTION["positive_max"]
            if neg_pct < neg_min:
                deviation_checks.append({"theme": "消极情感", "percent": neg_pct, "status": "warning", "suggestion": f"低于预期 {neg_min}% -- 李鱓底色应偏阴", "expected_range": [neg_min, 100]})
            if pos_pct > pos_max:
                deviation_checks.append({"theme": "积极情感", "percent": pos_pct, "status": "warning", "suggestion": f"高于预期 {pos_max}% -- 可能被花鸟题材误导", "expected_range": [0, pos_max]})
            if emotion_score_stats.get("new_average") is not None:
                avg = emotion_score_stats["new_average"]
                emotion_mean_max = EXPECTED_SENTIMENT_DISTRIBUTION["emotion_mean_max"]
                if avg > emotion_mean_max:
                    deviation_checks.append({"theme": "情感均值", "percent": avg, "status": "warning", "suggestion": f"{avg:+.2f} 偏阳 -- 李鱓整体应偏阴(预期 < {emotion_mean_max})", "expected_range": [-100, emotion_mean_max]})

        report = {
            "theme_coverage": theme_coverage,
            "primary_theme_distribution": primary_theme_dist,
            "sentiment_distribution": sentiment_dist,
            "emotion_score_stats": emotion_score_stats,
            "theme_change_paths": theme_change_paths,
            "deviation_checks": deviation_checks,
            "confidence_stats": confidence_stats,
            "low_conf_count": len(low_conf_records),
            "llm_corrected": llm_corrected,
        }

        yield sse("complete", {
            "total": total,
            "updated": updated,
            "errors": errors,
            "message": f"批量重跑完成：{updated} 幅更新，{errors} 幅错误" + (f"，人工智能修正 {llm_corrected} 幅" if llm_corrected > 0 else "") + (f"，LLM调用失败 {llm_errors} 次" if llm_errors > 0 else ""),
            "report": report,
        })

        conn.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ============ AI 总结 API ============

class SummaryRequest(BaseModel):
    artist: str = "all"
    force_regenerate: bool = False  # 强制重新生成


class SummaryResponse(BaseModel):
    success: bool
    summary: str  # Markdown 全文（向后兼容）
    report: Optional[Dict[str, Any]] = None  # 结构化报告数据（新增）
    error: Optional[str] = None
    cached: bool = False
    generated_at: Optional[str] = None


@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(
    request: SummaryRequest,
    editor=Depends(require_editor),
):
    """
    基于当前统计数据，生成结构化学术分析报告（v5.3 确定性规则引擎）
    报告显示在大数据分析页面顶部，替代原有的 LLM 洞察
    首次生成后自动缓存，后续直接读取缓存
    支持多画家，根据 artist 参数自动选择对应的背景上下文
    """
    from app.services.academic_report_service import generate_academic_report
    import json

    # 确保表存在（兼容旧缓存，新增 report_json 列存储结构化数据）
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analysis_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT NOT NULL UNIQUE,
            summary TEXT NOT NULL,
            stats_snapshot TEXT,
            record_count INTEGER DEFAULT 0,
            generated_at TEXT NOT NULL
        )
    """)
    # 尝试添加 report_json 列（若不存在）
    try:
        cur.execute("ALTER TABLE analysis_summary ADD COLUMN report_json TEXT")
    except Exception:
        pass
    conn.commit()

    # 先查缓存（force_regenerate=False 时直接返回缓存）
    if not request.force_regenerate:
        cur.execute(
            "SELECT summary, generated_at, report_json FROM analysis_summary WHERE artist = ?",
            (request.artist,)
        )
        row = cur.fetchone()
        if row:
            conn.close()
            report_data = None
            if row[2]:
                try:
                    report_data = json.loads(row[2])
                except Exception:
                    pass
            return SummaryResponse(
                success=True,
                summary=row[0],
                report=report_data,
                cached=True,
                generated_at=row[1],
            )

    # 未命中缓存，生成报告
    conn.close()

    db_path = "data/calligraphy.db"
    report = generate_academic_report(request.artist, db_path=db_path)

    # 保存到数据库
    conn = get_db_connection()
    cur = conn.cursor()
    generated_at = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO analysis_summary (artist, summary, stats_snapshot, record_count, generated_at, report_json)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(artist) DO UPDATE SET
            summary = excluded.summary,
            stats_snapshot = excluded.stats_snapshot,
            record_count = excluded.record_count,
            generated_at = excluded.generated_at,
            report_json = excluded.report_json
    """, (
        request.artist,
        report["markdown"],
        json.dumps(report["stats"], ensure_ascii=False),
        report["stats"].get("total", 0),
        generated_at,
        json.dumps(report, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()

    return SummaryResponse(
        success=True,
        summary=report["markdown"],
        report=report,
        cached=False,
        generated_at=generated_at,
    )


# ============ AI 深度洞察报告 API ============

class InsightRequest(BaseModel):
    artist: str = "all"
    force_regenerate: bool = False


class InsightResponse(BaseModel):
    success: bool
    report: str
    sections: Optional[Dict[str, str]] = None
    error: Optional[str] = None


@router.post("/insight", response_model=InsightResponse)
async def generate_insight_report(
    request: InsightRequest,
    editor=Depends(require_editor),
):
    """
    基于多维度统计数据，生成题跋艺术的深度洞察分析报告。
    包含四大板块：空间革命量化印证、文本语义网络、印章符号学、综合画像与矛盾调和。
    支持多画家，根据 artist 参数自动选择对应的背景上下文。
    """
    from app.services.insight_generator import generate_insight

    artist_where, artist_params = build_artist_condition(request.artist)
    conn = get_db_connection()
    cur = conn.cursor()

    # ---- 收集 stats_data（与 /summary 逻辑相同） ----
    import json as _json
    stats_data = {"period_stats": [], "theme_distribution": [], "sentiment_distribution": [],
                   "feature_word_stats": [], "layout_form_distribution": [], "total_count": 0}

    cur.execute(f"""
        SELECT period_phase, COUNT(*) as cnt,
               AVG(COALESCE(char_count, 0)) as avg_chars,
               MAX(COALESCE(char_count, 0)) as max_chars,
               MIN(CASE WHEN COALESCE(char_count, 0) > 0 THEN char_count END) as min_chars,
               AVG(COALESCE(word_count, 0)) as avg_words
        FROM tubi_analyses
        WHERE {artist_where}
          AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0
        GROUP BY period_phase ORDER BY period_phase
    """, artist_params)

    for row in cur.fetchall():
        stats_data["period_stats"].append({
            "period": row[0] or "未分期", "count": row[1],
            "avg_char_count": round(row[2] or 0, 1), "max_char_count": row[3] or 0,
            "min_char_count": row[4] or 0, "avg_word_count": round(row[5] or 0, 1),
        })

    cur.execute(f"""
        SELECT COUNT(*) FROM tubi_analyses
        WHERE {artist_where}
          AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0
    """, artist_params)
    stats_data["total_count"] = cur.fetchone()[0]

    # 主题分布
    cur.execute(f"""
        SELECT period_phase, content_analysis FROM tubi_analyses
        WHERE {artist_where} AND content_analysis IS NOT NULL
    """, artist_params)
    theme_counts, sent_counts, feat_words = {}, {}, []
    for row in cur.fetchall():
        period = row[0] or "未分期"
        try:
            analysis = _json.loads(row[1])
            for t in analysis.get("themes", []):
                key = (period, t.get("name", "未知"))
                theme_counts[key] = theme_counts.get(key, 0) + 1
            pol = analysis.get("sentiment", {}).get("polarity", "neutral")
            sent_counts[(period, pol)] = sent_counts.get((period, pol), 0) + 1
            feat_words.extend([
                {"dimension": dim, "word": w, "count": 1, "period": period}
                for dim, words in analysis.get("feature_words", {}).items()
                for w in words
            ])
        except:
            pass

    period_totals = {}
    for (p, _), c in theme_counts.items():
        period_totals[p] = period_totals.get(p, 0) + c
    for (p, t), c in theme_counts.items():
        stats_data["theme_distribution"].append({
            "period": p, "theme_name": t, "count": c,
            "percentage": round(c / max(period_totals.get(p, 1), 1) * 100, 1),
        })
    for (p, pol), c in sent_counts.items():
        stats_data["sentiment_distribution"].append({
            "period": p, "polarity": pol, "count": c,
            "percentage": round(c / max(period_totals.get(p, 1), 1) * 100, 1),
        })
    stats_data["feature_word_stats"] = feat_words[:300]

    # 布局形式分布
    cur.execute(f"""
        SELECT position_analysis FROM tubi_analyses
        WHERE {artist_where} AND position_analysis IS NOT NULL
    """, artist_params)
    form_counts = {}
    total_form = 0
    for row in cur.fetchall():
        try:
            pos = _json.loads(row[0])
            for ft in pos.get("form_types", []):
                if ft.get("matched"):
                    name = ft.get("name", "未知")
                    form_counts[name] = form_counts.get(name, 0) + 1
                    total_form += 1
        except:
            pass
    for name, count in sorted(form_counts.items(), key=lambda x: x[1], reverse=True):
        stats_data["layout_form_distribution"].append({
            "form_name": name, "count": count,
            "percentage": round(count / max(total_form, 1) * 100, 1),
        })

    # ---- 收集原始记录（含面积数据、印章等） ----
    cur.execute(f"""
        SELECT id, title, year, period_phase, inscription_content, inscription_modern,
               seal_content, content_analysis, position_analysis,
               inscription_percent, painting_percent, blank_percent
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL
        LIMIT 300
    """, artist_params)

    records = []
    for row in cur.fetchall():
        content_json = row[7]
        pos_json = row[8]
        try:
            ca = _json.loads(content_json) if content_json else {}
        except:
            ca = {}
        try:
            pa = _json.loads(pos_json) if pos_json else {}
        except:
            pa = {}
        records.append({
            "id": row[0],
            "title": row[1],
            "year": row[2],
            "period_phase": row[3],
            "inscription_content": row[4],
            "inscription_modern": row[5],
            "seal_content": row[6],
            "content_analysis": ca,
            "position_analysis": pa,
            "inscription_percent": row[9],
            "painting_percent": row[10],
            "blank_percent": row[11],
        })

    # ---- 关联数据 ----
    corr_data = None
    cur.execute(f"""
        SELECT content_analysis, position_analysis, period_phase
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL AND position_analysis IS NOT NULL
    """, artist_params)
    _recs_for_corr = []
    for r in cur.fetchall():
        try:
            pos = _json.loads(r[1]) if r[1] else {}
        except:
            pos = {}
        _recs_for_corr.append({"content_analysis": r[0], "position_analysis": pos, "period_phase": r[2]})

    if _recs_for_corr:
        contingency = build_contingency_table(_recs_for_corr)
        chi2_result = chi_square_test(contingency)
        inv_analysis = get_invasive_analysis(contingency)
        corr_data = {
            "chi2_statistic": chi2_result["chi2"],
            "p_value": chi2_result["p_value"],
            "significant": chi2_result["significant"],
            "invasive_analysis": inv_analysis,
        }

    conn.close()

    # ---- 调用 AI 生成洞察报告 ----
    result = await generate_insight(stats_data, corr_data, records, artist=request.artist)

    return InsightResponse(
        success=result.success,
        report=result.report,
        sections=result.sections,
        error=result.error,
    )


# ============ 内容×空间 关联分析 ============

class ThemeAreaItem(BaseModel):
    theme: str
    n: int
    avg_area: float
    avg_words: float


class PeriodTrendItem(BaseModel):
    period: str
    n: int
    avg_area: float


class AreaThemeStatsResponse(BaseModel):
    sample_total: int
    theme_area: List[ThemeAreaItem]
    period_trend: List[PeriodTrendItem]
    insights: List[str]


@router.get("/area-theme-stats", response_model=AreaThemeStatsResponse)
async def get_area_theme_stats(
    artist: str = Query(default="李鱓", description="画家名称"),
):
    conn = get_db_connection()
    cur = conn.cursor()
    artist_where, artist_params = build_artist_condition(artist)

    cur.execute(f"""
        SELECT content_analysis, inscription_percent, period_phase, word_count
        FROM tubi_analyses
        WHERE {artist_where}
          AND content_analysis IS NOT NULL
          AND content_analysis != ''
          AND content_analysis != '{{}}'
          AND inscription_percent IS NOT NULL
    """, artist_params)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        return AreaThemeStatsResponse(
            sample_total=0, theme_area=[], period_trend=[], insights=[]
        )

    from collections import defaultdict
    import statistics

    theme_data = defaultdict(list)
    period_data = defaultdict(list)
    all_areas = []

    for row in rows:
        content_json, insc, period, wc = row
        try:
            ca = json.loads(content_json)
        except Exception:
            continue
        themes = ca.get("themes", [])
        main_theme = themes[0].get("name", "") if themes else ""
        if main_theme:
            theme_data[main_theme].append({
                "area": insc or 0,
                "words": wc or 0,
            })
        p = period or "未分期"
        period_data[p].append(insc or 0)
        all_areas.append(insc or 0)

    theme_area = []
    for name in theme_data:
        items = theme_data[name]
        areas = [i["area"] for i in items]
        words = [i["words"] for i in items]
        theme_area.append(ThemeAreaItem(
            theme=name,
            n=len(items),
            avg_area=round(statistics.mean(areas), 1),
            avg_words=round(statistics.mean(words), 1),
        ))
    theme_area.sort(key=lambda x: -x.avg_area)

    period_order = {"早期": 0, "中期": 1, "晚期": 2, "未分期": 3}
    period_trend = []
    for p in sorted(period_data.keys(), key=lambda x: period_order.get(x, 99)):
        vals = period_data[p]
        period_trend.append(PeriodTrendItem(
            period=p,
            n=len(vals),
            avg_area=round(statistics.mean(vals), 1),
        ))

    insights = []
    if len(theme_area) >= 2:
        top = theme_area[0]
        bottom = theme_area[-1]
        if top.n >= 3 and bottom.n >= 3 and bottom.avg_area > 0:
            ratio = round(top.avg_area / bottom.avg_area, 1)
            insights.append(
                f"{top.theme}类作品题跋面积是{bottom.theme}的{ratio}倍，批判越尖锐，落字越密"
            )

    if len(period_trend) >= 2:
        early_avg = next((p.avg_area for p in period_trend if p.period == "早期"), None)
        late_avg = next((p.avg_area for p in period_trend if p.period == "晚期"), None)
        if early_avg is not None and late_avg is not None and early_avg > 0:
            pct_increase = round((late_avg - early_avg) / early_avg * 100)
            insights.append(
                f"晚年题跋面积比早期高{pct_increase}%，衰年变法在空间上亦可见证"
            )

    return AreaThemeStatsResponse(
        sample_total=len(rows),
        theme_area=theme_area,
        period_trend=period_trend,
        insights=insights,
    )
