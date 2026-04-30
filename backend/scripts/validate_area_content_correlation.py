"""内容×面积联动分析验证 — 4 个假设逐项用真实数据检验
输出：每个假设的统计显著性 + 效应量 + 是否值得做产品
"""
import sqlite3, json, statistics
from collections import defaultdict

DB = "data/calligraphy.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT inscription_percent, painting_percent, blank_percent,
           content_analysis, year, period_phase, word_count, char_count,
           artwork_width_cm, artwork_height_cm,
           theme_tags
    FROM tubi_analyses
    WHERE artist = '李鱓'
      AND inscription_percent IS NOT NULL
      AND content_analysis IS NOT NULL
      AND content_analysis != ''
""").fetchall()

print(f"李鱓 有效样本: {len(rows)} 幅\n{'='*70}")

# 解析数据
records = []
for row in rows:
    ca = json.loads(row["content_analysis"]) if row["content_analysis"] else {}
    main_theme = ca.get("themes", [])[0].get("name", "") if ca.get("themes") else ""
    polarity = ca.get("sentiment", {}).get("polarity", "neutral")
    emotion_score = ca.get("sentiment", {}).get("emotion_score", 0) or 0
    confidence = ca.get("v4_confidence", 0) or 0
    special_rules = ca.get("special_rules", [])
    llm_fixed = any("LLM采纳" in r for r in (special_rules or [])) if special_rules else False
    records.append({
        "inscription_pct": row["inscription_percent"],
        "painting_pct": row["painting_percent"],
        "blank_pct": row["blank_percent"],
        "word_count": row["word_count"] or 0,
        "year": row["year"],
        "period": row["period_phase"] or "",
        "main_theme": main_theme,
        "polarity": polarity,
        "emotion_score": emotion_score,
        "confidence": confidence,
        "llm_fixed": llm_fixed,
        "width_cm": row["artwork_width_cm"],
        "height_cm": row["artwork_height_cm"],
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# H1: 主题 × 题跋面积 — 不同主题的题跋面积是否有显著差异？
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("H1: 不同主题的题跋面积是否有显著差异？")
print("-" * 50)

theme_data = defaultdict(list)
for r in records:
    if r["main_theme"]:
        theme_data[r["main_theme"]].append(r)

for theme, items in sorted(theme_data.items(), key=lambda x: -len(x[1])):
    areas = [i["inscription_pct"] for i in items]
    words = [i["word_count"] for i in items]
    avg_area = statistics.mean(areas)
    med_area = statistics.median(areas)
    avg_words = statistics.mean(words) if words else 0
    sd = statistics.stdev(areas) if len(areas) > 1 else 0
    print(f"  {theme:6s}  n={len(items):3d}  avg_area={avg_area:5.1f}%  median={med_area:5.1f}%  avg_words={avg_words:5.1f}  sd={sd:4.1f}")

# 找出差异最大的两组
all_themes = list(theme_data.keys())
if len(all_themes) >= 2:
    max_gap = 0
    gap_pair = ("", "")
    for i in range(len(all_themes)):
        for j in range(i+1, len(all_themes)):
            a1 = statistics.mean([x["inscription_pct"] for x in theme_data[all_themes[i]]])
            a2 = statistics.mean([x["inscription_pct"] for x in theme_data[all_themes[j]]])
            gap = abs(a1 - a2)
            if gap > max_gap and len(theme_data[all_themes[i]]) >= 3 and len(theme_data[all_themes[j]]) >= 3:
                max_gap = gap
                gap_pair = (all_themes[i], all_themes[j])

    from math import sqrt
    items1 = theme_data[gap_pair[0]]
    items2 = theme_data[gap_pair[1]]
    a1 = statistics.mean([x["inscription_pct"] for x in items1])
    a2 = statistics.mean([x["inscription_pct"] for x in items2])
    s1 = statistics.stdev([x["inscription_pct"] for x in items1]) if len(items1) > 1 else 0
    s2 = statistics.stdev([x["inscription_pct"] for x in items2]) if len(items2) > 1 else 0
    n1, n2 = len(items1), len(items2)
    pooled_se = sqrt(s1*s1/n1 + s2*s2/n2) if s1 and s2 else 0
    t_stat = (a1 - a2) / pooled_se if pooled_se > 0 else 0
    print(f"\n  最大差异: {gap_pair[0]} vs {gap_pair[1]} — gap={max_gap:.1f}pp  t≈{abs(t_stat):.1f}")
    if abs(t_stat) > 2:
        print(f"  → 结论/洞察: 两组差异显著(t≈{abs(t_stat):.1f})，可作为产品洞察展示")
    else:
        print(f"  → 结论/洞察: 差异不够显著(t≈{abs(t_stat):.1f})，宜列为弱洞察")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# H2: 情感 × 题跋面积 — 负面情绪是否与更大的题跋面积相关？
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'='*70}")
print("H2: 负面情绪作品题跋面积是否更大？")
print("-" * 50)

polarity_data = defaultdict(list)
for r in records:
    polarity_data[r["polarity"]].append(r["inscription_pct"])

for pol in ["positive", "negative", "neutral"]:
    vals = polarity_data[pol]
    if vals:
        print(f"  {pol:8s}  n={len(vals):3d}  avg_area={statistics.mean(vals):5.1f}%  median={statistics.median(vals):5.1f}%")

# correlation emotion_score vs area
emotions = [r["emotion_score"] for r in records]
areas = [r["inscription_pct"] for r in records]
n = len(emotions)
if n > 2:
    mx_emotion = statistics.mean(emotions)
    mx_area = statistics.mean(areas)
    cov = sum((emotions[i] - mx_emotion) * (areas[i] - mx_area) for i in range(n)) / n
    sx = statistics.stdev(emotions)
    sy = statistics.stdev(areas)
    r = cov / (sx * sy) if sx and sy else 0
    neg_area = statistics.mean(polarity_data["negative"]) if polarity_data["negative"] else 0
    pos_area = statistics.mean(polarity_data["positive"]) if polarity_data["positive"] else 0
    print(f"\n  emotion_score 与 inscription_percent 相关系数 r = {r:+.3f}")
    print(f"  negative 均值={neg_area:.1f}%  positive 均值={pos_area:.1f}%  差值={neg_area-pos_area:+.1f}pp")
    if abs(r) > 0.15 and (neg_area - pos_area > 1):
        print(f"  → 结论/洞察: 负面情绪确实与更大的题跋面积弱相关(r={r:+.2f})，值得作为洞察展示")
    elif neg_area > pos_area:
        print(f"  → 结论/洞察: 负面情绪均值高于正面但差值仅{neg_area-pos_area:+.1f}pp，算弱信号(r={r:+.2f})")
    else:
        print(f"  → 结论/洞察: 无明显相关性(r={r:+.2f})，不宜作为产品洞察")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# H3: 分期 × 题跋面积 — 越到晚年题跋越占画面？
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'='*70}")
print("H3: 晚年题跋是否侵占画面更大？")
print("-" * 50)

period_data = defaultdict(list)
for r in records:
    period = r["period"] or "未分期"
    period_data[period].append(r["inscription_pct"])

for period in ["早期", "中期", "晚期", "未分期"]:
    if period_data[period]:
        vals = period_data[period]
        print(f"  {period:4s}  n={len(vals):3d}  avg_area={statistics.mean(vals):5.1f}%  median={statistics.median(vals):5.1f}%")

early = period_data.get("早期", [])
late = period_data.get("晚期", [])
mid = period_data.get("中期", [])
if early and late:
    e_avg = statistics.mean(early)
    l_avg = statistics.mean(late)
    m_avg = statistics.mean(mid) if mid else 0
    print(f"\n  早期→中期→晚期:  {e_avg:.1f}% → {m_avg:.1f}% → {l_avg:.1f}%")
    if l_avg > e_avg and m_avg > e_avg:
        print(f"  → 结论/洞察: 趋势明确上升({e_avg:.1f}→{l_avg:.1f})，'晚年题跋侵占画面'假设成立，可做核心洞察")
    elif l_avg > e_avg:
        print(f"  → 结论/洞察: 晚期>早期但中期不一定是线性增长，可做弱洞察")
    else:
        print(f"  → 结论/洞察: 无上升趋势，这个假设不成立")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# H4: 可信度 × 面积 — LLM修正的作品是否集中在某些面积区间？
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'='*70}")
print("H4: LLM修正的作品在面积分布上是否有聚集特征？")
print("-" * 50)

llm_fixed_areas = [r["inscription_pct"] for r in records if r["llm_fixed"]]
all_areas = [r["inscription_pct"] for r in records]

if len(llm_fixed_areas) >= 5:
    avg_llm = statistics.mean(llm_fixed_areas)
    avg_all = statistics.mean(all_areas)

    # 按面积分桶
    bins = [(0,5), (5,10), (10,15), (15,20), (20,30), (30,100)]
    for lo, hi in bins:
        total_in = sum(1 for a in all_areas if lo <= a < hi)
        llm_in = sum(1 for a in llm_fixed_areas if lo <= a < hi)
        llm_rate = llm_in / total_in * 100 if total_in else 0
        if total_in > 0:
            bar = "█" * int(llm_rate / 5)
            print(f"  面积 [{lo:2d}%-{hi:3d}%)  n={total_in:3d}  LLM修正={llm_in:3d} ({llm_rate:4.0f}%) {bar}")

    print(f"\n  LLM修正均值={avg_llm:.1f}%  全量均值={avg_all:.1f}%  差值={avg_llm-avg_all:+.1f}pp")
    if abs(avg_llm - avg_all) > 1.5:
        direction = "高" if avg_llm > avg_all else "低"
        print(f"  → 结论/洞察: LLM修正作品面积偏{direction}({avg_llm:.1f}% vs {avg_all:.1f}%)，系统偏差存在")
    else:
        print(f"  → 结论/洞察: LLM修正作品面积分布均匀，无系统偏差")
else:
    print(f"  → LLM修正样本不足({len(llm_fixed_areas)}幅)，跳过")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 总结
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print(f"\n{'='*70}")
print("总结")
print("=" * 70)
print("强洞察(直接做):")
print("弱洞察(可选做):")
print("无洞察(不做):")

conn.close()
