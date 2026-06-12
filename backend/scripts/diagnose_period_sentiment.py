# -*- coding: utf-8 -*-
"""分时期情感趋势诊断"""
import sqlite3
import json
from collections import Counter, defaultdict

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

cur.execute("""
    SELECT year, content_analysis, period_phase
    FROM tubi_analyses
    WHERE artist = '李鱓' AND content_analysis IS NOT NULL
""")

period_stats = defaultdict(lambda: {"total": 0, "neg": 0, "pos": 0, "neu": 0, "scores": []})

for row in cur.fetchall():
    year, ca_json, period = row
    try:
        data = json.loads(ca_json)
        sent = data.get("sentiment", {})
        pol = sent.get("polarity", "neutral")
        score = sent.get("emotion_score")

        # 确定时期
        if period and period != "年代不详":
            p = period
        elif year:
            if year <= 1722:
                p = "早期"
            elif year <= 1740:
                p = "中期"
            else:
                p = "晚期"
        else:
            p = "年代不详"

        period_stats[p]["total"] += 1
        period_stats[p]["neg" if pol == "negative" else "pos" if pol == "positive" else "neu"] += 1
        if score is not None:
            period_stats[p]["scores"].append(score)
    except:
        pass

print("=" * 60)
print("李鱓分时期情感分布")
print("=" * 60)

for period in ["早期", "中期", "晚期", "年代不详"]:
    s = period_stats[period]
    if s["total"] == 0:
        continue
    total = s["total"]
    neg_pct = s["neg"] / total * 100
    pos_pct = s["pos"] / total * 100
    neu_pct = s["neu"] / total * 100
    avg_score = sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0
    print(f"\n{period}（{total}幅）:")
    print(f"  negative: {s['neg']:3d} ({neg_pct:5.1f}%)")
    print(f"  positive: {s['pos']:3d} ({pos_pct:5.1f}%)")
    print(f"  neutral:  {s['neu']:3d} ({neu_pct:5.1f}%)")
    print(f"  平均emotion_score: {avg_score:+.2f}")

conn.close()
