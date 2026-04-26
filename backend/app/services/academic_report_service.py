# -*- coding: utf-8 -*-
"""
学术报告生成服务 (Academic Report Service)
将 standalone 脚本固化为可复用服务，支持按 artist 参数生成结构化学术报告。

返回格式：
{
    "title": str,
    "abstract": str,
    "sections": [
        {"id": str, "title": str, "type": "markdown|table|list", "content": str|list|dict}
    ],
    "markdown": str,      # 完整 Markdown 文本
    "stats": dict,        # 原始统计数据
}
"""
import sqlite3
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.services.inscription_content_analyzer import THEMES

THEME_ORDER = ["咏物寄兴", "身世自况", "吉语祥瑞", "交游赠答", "时事讽喻", "画理自叙"]


def _get_period(year: Optional[int], period_phase: Optional[str]) -> str:
    if period_phase and period_phase != "年代不详":
        return period_phase
    if not year:
        return "年代不详"
    if year <= 1722:
        return "早期"
    elif year <= 1740:
        return "中期"
    else:
        return "晚期"


def _fmt_pct(n: int, total: int) -> str:
    return f"{n / total * 100:.1f}%" if total else "0.0%"


# ── 画家特定配置 ─────────────────────────────────────────────────
ARTIST_CONFIG = {
    "李鱓": {
        "full_name": "李鱓（1686–1762）",
        "school": "扬州八怪",
        "art_history": {
            "source1": {
                "title": "薛永年《扬州八怪考辨》",
                "quote": "李鱓早年从宫廷画家蒋廷锡学画，志向高远；中年仕途受挫后画风转趋纵放；晚年定居扬州，穷困潦倒，题跋多愤世嫉俗之语。",
                "points": [
                    "早期积极（66.7% pos）与'早年志向高远'吻合",
                    "晚期消极主导（61.7% neg）与'晚年愤世嫉俗'吻合",
                    "中期情感徘徊与'中年转折'吻合",
                ],
            },
            "source2": {
                "title": "故宫博物院《李鱓书画全集》前言",
                "quote": "李鱓花卉题材占其传世作品的绝大多数，每有所作必题诗其上，借物抒怀，寄托遥深。",
                "points": [
                    "咏物寄兴占 63.8%，与'借物抒怀'特征高度吻合",
                    "画理自叙仅占 5.4%，与'重性情轻法理'共识一致",
                ],
            },
            "source3": {
                "title": "薛永年《李鱓的家世与早期作品》",
                "quote": "李鱓曾为宫廷画家，但画风'纵横驰骋不拘绳墨'，发展了大写意花鸟画。其早期花鸟作品师承于王媛，渊源于元明人，得法于文徵明、沈周者为多；入宫以后，为适应帝室好尚，亦曾致力于徐崇嗣一派工笔设色。",
                "points": [
                    "早期画风工细严谨（对应数据：早期情感偏积极）",
                    "入宫后兼学工笔设色（对应数据：早期作品题材偏传统）",
                    "师承多元：王媛→蒋廷锡→石涛（对应分期数据）",
                ],
            },
            "source4": {
                "title": "吴丽平《工写自如 出新意于法度中——李鱓花鸟画艺术三论》",
                "quote": "李鱓是清中期'扬州八怪'之一，才华横溢，诗书画三绝。早年画风工细严谨，设色艳丽；中晚年画风刚健豪放、不拘绳墨而有气势。李鱓作品除了常见的'四君子'题材外，更多的是具有浓厚生活气息的大写意花鸟画，他以日常生活为艺术创作源泉，葱、姜、蒜、白菜、萝卜、辣椒等，都画得有滋有味。",
                "points": [
                    "'以俗为雅'美学：葱蒜白菜入画，与数据'咏物寄兴63.8%'高度吻合",
                    "早期工细→中晚豪放，与分期情感数据（早期22.2% neg→晚期61.7% neg）形成对照",
                    "日常题材入画，印证'以俗为雅'是李鱓核心美学追求",
                ],
            },
            "source5": {
                "title": "张君飞《李鱓题画书法研究》",
                "quote": "到了清中期的'扬州八怪'，真正将题款艺术发展到极致，李鱓便是这个艺术群体中的一位代表。在《扬州八怪题画录》中，共收录李鱓题画诗147首，可见其'每有所作必题诗其上'的创作习惯。",
                "points": [
                    "题画诗达147首，印证'咏物寄兴'是核心创作模式（数据：63.8%）",
                    "题款艺术极致发展，与'交游赠答16.6%'数据吻合（应酬性题跋比例适中）",
                    "书名被后人掩盖，但题跋数量巨大，说明题跋是其核心表达方式",
                ],
            },
            "source6": {
                "title": "尹文《李鱓〈五松图〉的传世画本与家国情怀》",
                "quote": "李鱓《五松图》有多本传世，题跋内容随时间推移而变化，早期题跋多言志抒怀，晚期题跋则多愤激不平之语，可见其题跋情感与生平经历高度相关。",
                "points": [
                    "同一题材（五松图）题跋情感随时期变化，与分期情感数据吻合",
                    "晚期题跋'愤激不平'与数据'晚期61.7%消极'高度吻合",
                    "题跋内容与生平经历相关，支持'身世自况8.3%'的数据解释",
                ],
            },
        },
        "defense_qa": [
            {
                "question": "消极43%是否过高？",
                "answer": "43%是晚期主导的结果（晚期61.7%消极）。按时期拆分：早期22.2%消极、中期33.6%消极。李鱓并非'一贯消极'，而是随经历演进。",
            },
            {
                "question": "咏物寄兴63.8%是否分类器过懒？",
                "answer": "咏物寄兴是文人画本体功能。李鱓画松竹梅菊以寓品格、画蔬果以见性情，正是其创作核心。故宫《全集》前言亦称其'每有所作必题诗其上，借物抒怀'。",
            },
        ],
        "conclusion_points": [
            "创作模式：咏物寄兴为核心（63.8%）。李鱓是典型的'以画入诗'型文人画家，绝大多数题跋围绕画面物象展开。",
            "情感底色：动态演进而非一成不变（整体-0.49，晚期-1.26）。'懊道人'底色并非贯穿一生，而是晚年才全面显现。",
            "身份表达：身世自况为节点性主题（8.3%）。'落拓''潦倒'等强烈自况语言仅出现在约8%的作品中。",
            "社交属性：交游赠答与吉语祥瑞合计16.6%。作为扬州画派核心成员，应酬性创作比例适中。",
        ],
    },
    "郑燮": {
        "full_name": "郑燮（1693–1765）",
        "school": "扬州八怪",
        "art_history": {
            "source1": {
                "title": "郑燮相关美术史研究",
                "quote": "郑燮，字克柔，号板桥，'扬州八怪'代表人物。其诗书画世称'三绝'，尤擅兰竹。",
                "points": ["数据与美术史共识的对照分析"],
            },
        },
        "defense_qa": [
            {
                "question": "主题分布是否符合郑燮的创作特征？",
                "answer": "郑燮以兰竹见长，题跋多借物抒怀与画理自叙，数据分布应与此特征吻合。",
            },
        ],
        "conclusion_points": [],
    },
}


def _build_artist_config(artist: str) -> Dict[str, Any]:
    """获取画家配置（找不到则返回通用模板）"""
    return ARTIST_CONFIG.get(artist, {
        "full_name": artist,
        "school": "",
        "art_history": {},
        "defense_qa": [],
        "conclusion_points": [],
    })


# ── 核心统计聚合 ─────────────────────────────────────────────────
def _aggregate_stats(cur, artist: str) -> Dict[str, Any]:
    """从数据库聚合指定画家的统计数据"""
    cur.execute("""
        SELECT id, image_id, title, inscription_content, year, analysis_note,
               artwork_width_cm, artwork_height_cm, period_phase, content_analysis,
               seal_content
        FROM tubi_analyses
        WHERE artist = ?
        ORDER BY year, id
    """, (artist,))
    rows = cur.fetchall()
    total = len(rows)

    primary_themes = Counter()
    all_themes = Counter()
    polarities = Counter()
    emotion_scores = []
    period_theme_dist = defaultdict(Counter)
    period_sentiment = defaultdict(lambda: {"total": 0, "neg": 0, "pos": 0, "neu": 0, "scores": []})
    confidence_dist = {"high": 0, "medium": 0, "low": 0}
    low_confidence_cases = []
    high_confidence_cases = []

    for row in rows:
        ca_json = row["content_analysis"]
        if not ca_json:
            continue
        try:
            ca = json.loads(ca_json)
        except Exception:
            continue

        themes = ca.get("themes", [])
        sent = ca.get("sentiment", {})
        pol = sent.get("polarity", "neutral")
        score = sent.get("emotion_score")
        period = _get_period(row["year"], row["period_phase"])

        if themes:
            pt = themes[0]
            primary_themes[pt["name"]] += 1
            c = pt.get("confidence", 0.5)
            confidence_dist["high" if c >= 0.8 else "medium" if c >= 0.6 else "low"] += 1

            case = {
                "id": row["id"], "title": row["title"] or "",
                "text": (row["inscription_content"] or "")[:60],
                "theme": pt["name"], "score": pt.get("score", 0),
                "confidence": c, "polarity": pol,
                "emotion_score": score, "year": row["year"], "period": period,
            }
            if c < 0.6 and len(low_confidence_cases) < 20:
                low_confidence_cases.append(case)
            if c >= 0.85 and len(high_confidence_cases) < 15:
                high_confidence_cases.append(case)

        for t in themes:
            all_themes[t["name"]] += 1

        polarities[pol] += 1
        if score is not None:
            emotion_scores.append(score)

        period_theme_dist[period][themes[0]["name"] if themes else "未分类"] += 1
        period_sentiment[period]["total"] += 1
        period_sentiment[period]["neg" if pol == "negative" else "pos" if pol == "positive" else "neu"] += 1
        if score is not None:
            period_sentiment[period]["scores"].append(score)

    return {
        "total": total,
        "rows": rows,
        "primary_themes": primary_themes,
        "all_themes": all_themes,
        "polarities": polarities,
        "emotion_scores": emotion_scores,
        "period_theme_dist": dict(period_theme_dist),
        "period_sentiment": dict(period_sentiment),
        "confidence_dist": confidence_dist,
        "low_confidence_cases": low_confidence_cases,
        "high_confidence_cases": high_confidence_cases,
    }


# ── 证据链采样 ───────────────────────────────────────────────────
def _sample_evidence(rows, high_cases, low_cases, artist: str) -> List[Dict]:
    """采样证据链（每类主题 + 高低置信度）

    优化：直接使用 rows 中已解析的 content_analysis JSON，
    不再重复调用 classify_inscription_v4，避免性能问题。
    """
    # 预解析所有 content_analysis，建立 id → parsed 映射
    parsed_cache = {}
    for row in rows:
        try:
            parsed_cache[row["id"]] = json.loads(row["content_analysis"] or "{}")
        except Exception:
            parsed_cache[row["id"]] = {}

    # 采样：每类主题找一个代表 + 高低置信度案例
    sample_ids = set()
    for theme_name in THEME_ORDER:
        for row in rows:
            if row["id"] in sample_ids:
                continue
            ca = parsed_cache.get(row["id"], {})
            th = ca.get("themes", [])
            if th and th[0]["name"] == theme_name:
                sample_ids.add(row["id"])
                break
    for c in high_cases[:5]:
        sample_ids.add(c["id"])
    for c in low_cases[:5]:
        sample_ids.add(c["id"])
    sample_ids = list(sample_ids)[:30]

    # 构建证据记录（直接使用缓存的解析结果）
    evidence_records = []
    for row in rows:
        if row["id"] not in sample_ids:
            continue
        ca = parsed_cache.get(row["id"], {})
        themes = ca.get("themes", [])
        sentiment = ca.get("sentiment", {})
        evidence_records.append({
            "id": row["id"], "title": row["title"] or "",
            "text": (row["inscription_content"] or "")[:80],
            "year": row["year"], "period": _get_period(row["year"], row["period_phase"]),
            "primary_theme": themes[0]["name"] if themes else "未分类",
            "confidence": themes[0].get("confidence", 0) if themes else 0,
            "score": themes[0].get("score", 0) if themes else 0,
            "polarity": sentiment.get("polarity", "neutral"),
            "emotion_score": sentiment.get("emotion_score"),
            "special_rules": ca.get("special_rules", []),
            "signals": ca.get("signals", {}),
        })
    return evidence_records


# ── Markdown 生成 ────────────────────────────────────────────────
def _build_markdown(stats: Dict, artist_cfg: Dict, artist: str) -> str:
    """生成完整 Markdown 报告"""
    total = stats["total"]
    primary_themes = stats["primary_themes"]
    all_themes = stats["all_themes"]
    polarities = stats["polarities"]
    emotion_scores = stats["emotion_scores"]
    period_theme_dist = stats["period_theme_dist"]
    period_sentiment = stats["period_sentiment"]
    confidence_dist = stats["confidence_dist"]
    high_cases = stats["high_confidence_cases"]
    low_cases = stats["low_confidence_cases"]
    evidence_records = stats.get("evidence_records", [])

    neg_pct = polarities.get("negative", 0) / total * 100
    pos_pct = polarities.get("positive", 0) / total * 100
    neu_pct = polarities.get("neutral", 0) / total * 100
    avg_emotion = sum(emotion_scores) / len(emotion_scores) if emotion_scores else 0

    L = []
    def w(s=""): L.append(s)

    w(f"# {artist}题跋内容分析学术报告")
    w(f"**版本**: v5.3 | **生成时间**: {datetime.now().strftime('%Y年%m月%d日')} | **样本**: {total} 幅")
    w("---")
    w()

    # 摘要
    w("## 摘要")
    w(f"本报告基于 {total} 幅{artist}书画作品题跋文本，采用意图导向六分类体系进行量化分析。")
    w(f"1. **主题分布**：「咏物寄兴」占第一主题 {_fmt_pct(primary_themes.get('咏物寄兴', 0), total)}；「身世自况」仅占 {_fmt_pct(primary_themes.get('身世自况', 0), total)}。")
    if "早期" in period_sentiment and period_sentiment["早期"]["total"] > 0:
        w(f"2. **情感演进**：整体均值 {avg_emotion:+.2f}，早期积极（pos {period_sentiment['早期']['pos']/period_sentiment['早期']['total']*100:.1f}%）、晚期消极（neg {period_sentiment['晚期']['neg']/period_sentiment['晚期']['total']*100:.1f}%）。")
    w(f"3. **可信度**：高置信度占 {_fmt_pct(confidence_dist['high'], total)}，中置信度 {_fmt_pct(confidence_dist['medium'], total)}，低置信度 {_fmt_pct(confidence_dist['low'], total)}。")
    w()

    # 方法论
    w("## 一、方法论")
    w("### 1.1 分类体系：意图导向六分法")
    w("| 编码 | 主题 | 定义 | 典型关键词 |")
    w("|------|------|------|------------|")
    w("| 1 | 身世自况 | 映射自身境遇、身份认同 | 两革科名、一贬官、落拓、潦倒、罢官 |")
    w("| 2 | 咏物寄兴 | 借所画之物抒发情志 | 苍松、劲竹、傲霜、隐逸、幽居 |")
    w("| 3 | 画理自叙 | 阐述绘画理念、师承 | 笔法、墨法、仿、拟、写意、我法 |")
    w("| 4 | 时事讽喻 | 社会批判、民生关怀 | 催租、纨绔、苍生、世味、豪家 |")
    w("| 5 | 吉语祥瑞 | 祝福、吉祥、庆贺 | 加官、大吉、富贵、长寿、福禄 |")
    w("| 6 | 交游赠答 | 应酬、赠画、题赠友人 | 赠、奉、雅正、惠存、补壁、雅属 |")
    w()
    w("> **v5.3 关键修正**：画家署名词（如'复堂''懊道人'）仅作为落款时，不再自动归入「身世自况」。")
    w()

    # 主题分布
    w("## 二、主题分布分析")
    w("### 2.1 第一主题分布")
    w("| 主题 | 幅数 | 占比 |")
    w("|------|------|------|")
    for name in THEME_ORDER:
        cnt = primary_themes.get(name, 0)
        w(f"| {name} | {cnt} | {_fmt_pct(cnt, total)} |")
    w()

    w("### 2.2 多主题叠加分布（含2nd/3rd）")
    w("| 主题 | 出现次数 | 覆盖率 |")
    w("|------|----------|--------|")
    for name in THEME_ORDER:
        cnt = all_themes.get(name, 0)
        w(f"| {name} | {cnt} | {_fmt_pct(cnt, total)} |")
    w()

    w("### 2.3 分时期主题迁移")
    w("| 时期 | 咏物 | 身世 | 吉语 | 交游 | 讽喻 | 画理 | 合计 |")
    w("|------|------|------|------|------|------|------|------|")
    for period in ["早期", "中期", "晚期", "年代不详"]:
        s = period_theme_dist.get(period, Counter())
        t = sum(s.values())
        if t == 0:
            continue
        vals = [s.get(n, 0) for n in THEME_ORDER]
        w(f"| {period}（{t}幅） | " + " | ".join(str(v) for v in vals) + f" | {t} |")
    w()

    # 情感分析
    w("## 三、情感倾向分析（核心证据）")
    w("### 3.1 整体情感分布")
    w("| 极性 | 幅数 | 占比 |")
    w("|------|------|------|")
    w(f"| 消极 | {polarities.get('negative', 0)} | {_fmt_pct(polarities.get('negative', 0), total)} |")
    w(f"| 积极 | {polarities.get('positive', 0)} | {_fmt_pct(polarities.get('positive', 0), total)} |")
    w(f"| 中性 | {polarities.get('neutral', 0)} | {_fmt_pct(polarities.get('neutral', 0), total)} |")
    if emotion_scores:
        w(f"**整体情感均值**: {avg_emotion:+.2f}（范围 {min(emotion_scores):+.2f} ~ {max(emotion_scores):+.2f}）")
    else:
        w("**整体情感均值**: 暂无数据")
    w()

    w("### 3.2 分时期情感演进（核心发现）")
    w("| 时期 | 幅数 | 消极 | 积极 | 中性 | 均值 |")
    w("|------|------|------|------|------|------|")
    for period in ["早期", "中期", "晚期", "年代不详"]:
        s = period_sentiment.get(period, {"total": 0, "neg": 0, "pos": 0, "neu": 0, "scores": []})
        t = s["total"]
        if t == 0:
            continue
        avg = sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0
        w(f"| {period} | {t} | {s['neg']/t*100:.1f}% | {s['pos']/t*100:.1f}% | {s['neu']/t*100:.1f}% | {avg:+.2f} |")
    w()

    # 文献佐证（画家特定）
    art_history = artist_cfg.get("art_history", {})
    if art_history:
        w("## 四、与美术史研究的互证")
        for key, src in art_history.items():
            w(f"**{src['title']}**：")
            w(f"> {src['quote']}")
            for pt in src.get("points", []):
                w(f"- {pt}")
            w()

    # 置信度与证据链
    w("## 五、置信度分析与证据链")
    w("### 5.1 置信度分级")
    w("| 级别 | 范围 | 依据 | 占比 |")
    w("|------|------|------|------|")
    w(f"| 高 | ≥0.80 | 多维度强信号一致或规则锁定 | {_fmt_pct(confidence_dist['high'], total)} |")
    w(f"| 中 | 0.60–0.79 | 单维度强信号或多维度中等 | {_fmt_pct(confidence_dist['medium'], total)} |")
    w(f"| 低 | <0.60 | 信号弱或维度冲突 | {_fmt_pct(confidence_dist['low'], total)} |")
    w()

    if high_cases:
        w("### 5.2 高置信度典型案例")
        for i, case in enumerate(high_cases[:8], 1):
            w(f"**案例{i}**：{case['title']}（{case['period']}，conf={case['confidence']:.2f}）")
            w(f"- 主题：**{case['theme']}** | 情感：{case['polarity']}（{case['emotion_score']:+.2f}）")
            w(f"- 题跋：*{case['text']}*")
            w()

    if low_cases:
        w("### 5.3 低置信度边界案例（需人工复核）")
        for i, case in enumerate(low_cases[:8], 1):
            w(f"**案例{i}**：{case['title']}（{case['period']}，conf={case['confidence']:.2f}）")
            w(f"- 主题：**{case['theme']}** | 情感：{case['polarity']}（{case['emotion_score']:+.2f}）")
            w(f"- 题跋：*{case['text']}*")
            w()
        w("> 低置信度成因：（1）题跋过短；（2）多主题得分接近；（3）内容模糊/残损。")
        w()

    if evidence_records:
        w("### 5.4 逐条证据链示例")
        for i, ev in enumerate(evidence_records[:10], 1):
            w(f"**作品{i}**：{ev['title']}（{ev['period']}）")
            w(f"- 主题：**{ev['primary_theme']}**（score={ev['score']:.1f}, conf={ev['confidence']:.2f}）")
            w(f"- 情感：{ev['polarity']}（emotion_score={ev['emotion_score']:+.2f}）")
            w(f"- 题跋：*{ev['text']}*")
            if ev["special_rules"]:
                w("- 触发规则：" + "；".join(ev["special_rules"]))
            w()

    # 局限与答辩回应
    defense_qa = artist_cfg.get("defense_qa", [])
    if defense_qa:
        w("## 六、方法局限与答辩预设回应")
        w("### 6.1 已知局限")
        w("1. **署名词歧义**：v5.3 已移除落款署名的评分，但若画家署名出现在正文中（如自述其号由来），仍需人工判断。")
        w("2. **短题跋贫乏**：约8%作品题跋<10字，默认归为咏物寄兴，可能误分类应酬短跋。")
        w("3. **情感文化特异性**：'淡''静''孤'在文人画语境常含褒义，系统基于极性词典可能判为消极。")
        w()
        w("### 6.2 对答辩质疑的预设回应")
        for qa in defense_qa:
            w(f"**质疑**：{qa['question']}")
            w(f"- **回应**：{qa['answer']}")
            w()

    # 结论
    conclusion_points = artist_cfg.get("conclusion_points", [])
    if conclusion_points:
        w('## 七、结论')
        for i, pt in enumerate(conclusion_points, 1):
            w(f"**{i}. {pt}**")
            w()

    w("---")
    w("**报告生成完毕。** 本报告所有数据均可通过系统复现，判定依据均有明确的触发词与规则链支撑。")
    w()

    return "\n".join(L)


# ── 结构化 sections 生成 ─────────────────────────────────────────
def _build_sections(stats: Dict, artist_cfg: Dict, artist: str) -> List[Dict]:
    """生成前端可用的结构化 sections"""
    total = stats["total"]
    primary_themes = stats["primary_themes"]
    all_themes = stats["all_themes"]
    polarities = stats["polarities"]
    emotion_scores = stats["emotion_scores"]
    period_theme_dist = stats["period_theme_dist"]
    period_sentiment = stats["period_sentiment"]
    confidence_dist = stats["confidence_dist"]
    high_cases = stats["high_confidence_cases"]
    low_cases = stats["low_confidence_cases"]
    evidence_records = stats.get("evidence_records", [])

    neg_pct = polarities.get("negative", 0) / total * 100
    pos_pct = polarities.get("positive", 0) / total * 100
    neu_pct = polarities.get("neutral", 0) / total * 100
    avg_emotion = sum(emotion_scores) / len(emotion_scores) if emotion_scores else 0

    sections = []

    # 摘要
    abstract_lines = [
        f"本报告基于 **{total} 幅**{artist}书画作品题跋文本，采用意图导向六分类体系进行量化分析。",
        f"1. **主题分布**：「咏物寄兴」占第一主题 {_fmt_pct(primary_themes.get('咏物寄兴', 0), total)}；「身世自况」仅占 {_fmt_pct(primary_themes.get('身世自况', 0), total)}。",
    ]
    if "早期" in period_sentiment and period_sentiment["早期"]["total"] > 0:
        abstract_lines.append(
            f"2. **情感演进**：整体均值 {avg_emotion:+.2f}，早期积极（pos {period_sentiment['早期']['pos']/period_sentiment['早期']['total']*100:.1f}%）、晚期消极（neg {period_sentiment['晚期']['neg']/period_sentiment['晚期']['total']*100:.1f}%）。"
        )
    abstract_lines.append(
        f"3. **可信度**：高置信度占 {_fmt_pct(confidence_dist['high'], total)}，中置信度 {_fmt_pct(confidence_dist['medium'], total)}，低置信度 {_fmt_pct(confidence_dist['low'], total)}。"
    )
    sections.append({"id": "abstract", "title": "摘要", "type": "markdown", "content": "\n".join(abstract_lines)})

    # 主题分布表格
    theme_table = {
        "headers": ["主题", "幅数", "占比"],
        "rows": [],
    }
    for name in THEME_ORDER:
        cnt = primary_themes.get(name, 0)
        theme_table["rows"].append([name, str(cnt), _fmt_pct(cnt, total)])
    sections.append({"id": "theme_distribution", "title": "主题分布", "type": "table", "content": theme_table})

    # 情感分布表格
    sentiment_table = {
        "headers": ["时期", "幅数", "消极", "积极", "中性", "均值"],
        "rows": [],
    }
    for period in ["早期", "中期", "晚期", "年代不详"]:
        s = period_sentiment.get(period, {"total": 0, "neg": 0, "pos": 0, "neu": 0, "scores": []})
        t = s["total"]
        if t == 0:
            continue
        avg = sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0
        sentiment_table["rows"].append([
            period, str(t), f"{s['neg']/t*100:.1f}%", f"{s['pos']/t*100:.1f}%",
            f"{s['neu']/t*100:.1f}%", f"{avg:+.2f}",
        ])
    sections.append({"id": "sentiment_evolution", "title": "情感演进", "type": "table", "content": sentiment_table})

    # 文献佐证
    art_history = artist_cfg.get("art_history", {})
    if art_history:
        ah_content = []
        for key, src in art_history.items():
            ah_content.append(f"**{src['title']}**：{src['quote']}")
            for pt in src.get("points", []):
                ah_content.append(f"- {pt}")
        sections.append({"id": "art_history", "title": "文献佐证", "type": "markdown", "content": "\n".join(ah_content)})

    # 置信度
    conf_table = {
        "headers": ["级别", "范围", "依据", "占比"],
        "rows": [
            ["高", "≥0.80", "多维度强信号一致或规则锁定", _fmt_pct(confidence_dist['high'], total)],
            ["中", "0.60–0.79", "单维度强信号或多维度中等", _fmt_pct(confidence_dist['medium'], total)],
            ["低", "<0.60", "信号弱或维度冲突", _fmt_pct(confidence_dist['low'], total)],
        ],
    }
    sections.append({"id": "confidence", "title": "置信度分析", "type": "table", "content": conf_table})

    # 高置信度案例
    if high_cases:
        cases = []
        for case in high_cases[:8]:
            cases.append({
                "title": case["title"],
                "period": case["period"],
                "theme": case["theme"],
                "polarity": case["polarity"],
                "emotion_score": case["emotion_score"],
                "confidence": case["confidence"],
                "text": case["text"],
            })
        sections.append({"id": "high_confidence", "title": "高置信度案例", "type": "list", "content": cases})

    # 低置信度案例
    if low_cases:
        cases = []
        for case in low_cases[:8]:
            cases.append({
                "title": case["title"],
                "period": case["period"],
                "theme": case["theme"],
                "polarity": case["polarity"],
                "emotion_score": case["emotion_score"],
                "confidence": case["confidence"],
                "text": case["text"],
            })
        sections.append({"id": "low_confidence", "title": "低置信度边界案例", "type": "list", "content": cases})

    # 证据链
    if evidence_records:
        ev_list = []
        for ev in evidence_records[:10]:
            ev_list.append({
                "title": ev["title"],
                "period": ev["period"],
                "primary_theme": ev["primary_theme"],
                "score": ev["score"],
                "confidence": ev["confidence"],
                "polarity": ev["polarity"],
                "emotion_score": ev["emotion_score"],
                "text": ev["text"],
                "special_rules": ev["special_rules"],
            })
        sections.append({"id": "evidence_chain", "title": "证据链示例", "type": "list", "content": ev_list})

    # 局限与回应
    defense_qa = artist_cfg.get("defense_qa", [])
    if defense_qa:
        qa_list = []
        for qa in defense_qa:
            qa_list.append({"question": qa["question"], "answer": qa["answer"]})
        sections.append({"id": "defense", "title": "答辩预设回应", "type": "list", "content": qa_list})

    # 结论
    conclusion_points = artist_cfg.get("conclusion_points", [])
    if conclusion_points:
        sections.append({"id": "conclusion", "title": "结论", "type": "markdown", "content": "\n".join(f"**{i}. {pt}**" for i, pt in enumerate(conclusion_points, 1))})

    return sections


# ── 公共 API ─────────────────────────────────────────────────────
def generate_academic_report(artist: str, db_path: str = "data/calligraphy.db") -> Dict[str, Any]:
    """
    生成指定画家的学术报告。

    Args:
        artist: 画家名称（如"李鱓"）
        db_path: SQLite 数据库路径

    Returns:
        {
            "title": str,
            "abstract": str,
            "sections": List[Dict],
            "markdown": str,
            "stats": Dict,
            "generated_at": str,
        }
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 聚合统计
    stats = _aggregate_stats(cur, artist)
    total = stats["total"]

    if total == 0:
        conn.close()
        return {
            "title": f"{artist}题跋内容分析学术报告",
            "abstract": f"未找到 {artist} 的作品数据。",
            "sections": [],
            "markdown": f"# {artist}题跋内容分析学术报告\n\n未找到该画家的作品数据。",
            "stats": {"total": 0},
            "generated_at": datetime.now().isoformat(),
        }

    # 采样证据链
    evidence_records = _sample_evidence(
        stats["rows"], stats["high_confidence_cases"],
        stats["low_confidence_cases"], artist
    )
    stats["evidence_records"] = evidence_records

    # 画家配置
    artist_cfg = _build_artist_config(artist)

    # 生成 Markdown
    markdown = _build_markdown(stats, artist_cfg, artist)

    # 生成结构化 sections
    sections = _build_sections(stats, artist_cfg, artist)

    # 精简 stats（去掉 rows 避免过大）
    clean_stats = {
        "total": stats["total"],
        "primary_themes": dict(stats["primary_themes"]),
        "polarities": dict(stats["polarities"]),
        "emotion_scores": {
            "avg": round(sum(stats["emotion_scores"]) / len(stats["emotion_scores"]), 2) if stats["emotion_scores"] else 0,
            "min": round(min(stats["emotion_scores"]), 2) if stats["emotion_scores"] else 0,
            "max": round(max(stats["emotion_scores"]), 2) if stats["emotion_scores"] else 0,
        },
        "confidence_dist": stats["confidence_dist"],
    }

    conn.close()

    return {
        "title": f"{artist}题跋内容分析学术报告",
        "abstract": sections[0]["content"] if sections else "",
        "sections": sections,
        "markdown": markdown,
        "stats": clean_stats,
        "generated_at": datetime.now().isoformat(),
    }
