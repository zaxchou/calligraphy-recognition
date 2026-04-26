# -*- coding: utf-8 -*-
"""
深度诊断：身世自况主题的触发来源分析
"""
import sqlite3
import json
import sys
import os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.inscription_content_analyzer import (
    classify_inscription_v4, TEXT_SCORING_RULES, THEMES,
    match_painting_materials, get_size_category, _extract_material_category_from_title,
    SIZE_THEME_RULES, SIZE_PERIOD_MOOD_RULES, get_period_phase
)

DB_PATH = "data/calligraphy.db"
ARTIST = "李鱓"

# 身世自况相关的关键词
theme1_keywords = TEXT_SCORING_RULES[1]["keywords"]

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT id, inscription_content, year, title, analysis_note,
           artwork_width_cm, artwork_height_cm, artist, period_phase
    FROM tubi_analyses
    WHERE artist = ?
    ORDER BY id
""", (ARTIST,))
rows = cur.fetchall()

# 统计
total = len(rows)
selfref_primary = []
selfref_trigger_sources = Counter()
keyword_trigger_counts = Counter()
score_distribution = Counter()
locking_cases = []

for row in rows:
    text = row["inscription_content"] or ""
    title = row["title"] or ""
    analysis_note = row["analysis_note"] or ""
    year = row["year"]
    width_cm = row["artwork_width_cm"]
    height_cm = row["artwork_height_cm"]
    artist = row["artist"]
    period_phase = row["period_phase"]

    # 运行分析
    result = classify_inscription_v4(
        text=text, year=year, title=title, analysis_note=analysis_note,
        inscription_content=text,
        width_cm=width_cm, height_cm=height_cm, artist=artist
    )

    themes = result.get("themes", [])
    primary = themes[0] if themes else None

    if primary and primary["code"] == 1:
        selfref_primary.append({
            "id": row["id"],
            "title": title[:20],
            "text": text[:40] if text else "",
            "score": primary["score"],
            "confidence": primary["confidence"],
            "signals": result.get("signals", {}),
            "special_rules": result.get("special_rules", []),
        })
        score_distribution[int(primary["score"])] += 1

        # 分析触发来源
        text_scores = result["signals"]["text"]["theme_scores"]
        painting = result["signals"]["painting"]
        size = result["signals"]["size"]

        # 文本关键词触发
        text_score_1 = float(text_scores.get("1", 0))
        if text_score_1 > 0:
            # 找出具体触发了哪些关键词
            matched_kws = []
            for kw, score in theme1_keywords.items():
                if kw in text:
                    matched_kws.append((kw, score))
                    keyword_trigger_counts[kw] += 1
            if matched_kws:
                selfref_trigger_sources["text_keywords"] += 1

        # 画作内容触发
        if painting:
            for p in painting:
                if p["theme_tendency"] == "身世自况":
                    selfref_trigger_sources["painting_material"] += 1

        # 尺寸触发
        size_boost = size.get("theme_boost", {})
        if "1" in size_boost or 1 in size_boost:
            selfref_trigger_sources["size_boost"] += 1

        # 特殊规则触发
        rules = result.get("special_rules", [])
        for r in rules:
            if "锁定身世自况" in r:
                selfref_trigger_sources["lock_rule"] += 1
                locking_cases.append({
                    "id": row["id"],
                    "title": title[:20],
                    "text": text[:50] if text else "",
                    "score": primary["score"],
                    "rules": rules,
                })
            elif "老夫+困顿词" in r:
                selfref_trigger_sources["laofu_hardship"] += 1
            elif "画家情感基线" in r:
                selfref_trigger_sources["artist_baseline"] += 1

print(f"=" * 70)
print(f"身世自况深度诊断 — 李鱓 {total} 幅作品")
print(f"=" * 70)
print(f"\n【一、身世自况作为第一主题的数量】")
print(f"  总数: {len(selfref_primary)} / {total} ({len(selfref_primary)/total*100:.1f}%)")

print(f"\n【二、触发来源统计】")
for src, cnt in selfref_trigger_sources.most_common():
    pct = cnt / len(selfref_primary) * 100 if selfref_primary else 0
    print(f"  {src:20s}: {cnt:3d} ({pct:5.1f}%)")

print(f"\n【三、身世自况得分分布（第一主题）】")
for score in sorted(score_distribution.keys()):
    cnt = score_distribution[score]
    print(f"  得分 {score:2d}: {cnt:3d} 幅")

print(f"\n【四、触发次数最高的身世自况关键词 Top 20】")
for kw, cnt in keyword_trigger_counts.most_common(20):
    score = theme1_keywords.get(kw, 0)
    print(f"  {kw:8s}(+{score}): {cnt:3d} 次")

print(f"\n【五、锁定规则触发案例（前10）】")
for case in locking_cases[:10]:
    print(f"  id={case['id']:<4d} | 得分={case['score']:.1f} | {case['title']}")
    print(f"    题跋: {case['text']}")
    print(f"    规则: {case['rules']}")

# 特别分析：复堂和懊道人的影响
futang_count = sum(1 for r in rows if "复堂" in (r["inscription_content"] or ""))
aodaoren_count = sum(1 for r in rows if "懊道人" in (r["inscription_content"] or ""))
print(f"\n【六、核心署名词出现频率】")
print(f"  复堂:   {futang_count:3d} 幅")
print(f"  懊道人: {aodaoren_count:3d} 幅")

# 分析：如果没有"复堂"+3分，有多少作品会脱离身世自况
would_escape = 0
for item in selfref_primary:
    text = item["text"]
    signals = item["signals"]
    text_scores = signals["text"]["theme_scores"]
    # 估算去掉"复堂"后的得分
    adjusted_text_score = float(text_scores.get("1", 0))
    if "复堂" in text:
        adjusted_text_score -= 3
    # 如果调整后得分<=咏物寄兴得分，则认为会脱离
    yongwu_score = float(text_scores.get("2", 0))
    if adjusted_text_score <= yongwu_score:
        would_escape += 1

print(f"\n【七、如果去掉'复堂'的+3分】")
print(f"  预计有 {would_escape} 幅作品会脱离身世自况第一主题")

conn.close()
