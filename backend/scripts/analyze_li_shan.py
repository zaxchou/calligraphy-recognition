#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
李鱓作品主题/情感/题材/时期分布分析脚本
运行: cd backend && python scripts/analyze_li_shan.py
"""

import sqlite3
import json
from collections import Counter, defaultdict

DB_PATH = "data/calligraphy.db"
ARTIST = "李鱓"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 基础数量
    cur.execute("""
        SELECT COUNT(*) FROM tubi_analyses
        WHERE artist = ? AND content_analysis IS NOT NULL
    """, (ARTIST,))
    total = cur.fetchone()[0]
    print(f"\n{'='*60}")
    print(f"李鱓作品分析 — 共 {total} 幅（含 content_analysis）")
    print(f"{'='*60}")

    # 1. 时期分布
    print(f"\n【一、时期分布】")
    cur.execute("""
        SELECT period, COUNT(*) as cnt
        FROM tubi_analyses
        WHERE artist = ?
        GROUP BY period
        ORDER BY cnt DESC
    """, (ARTIST,))
    period_rows = cur.fetchall()
    total_period = sum(r[1] for r in period_rows if r[0])
    for row in period_rows:
        p, c = row
        p = p or "未分期/年代不详"
        pct = c / total * 100 if total else 0
        print(f"  {p:12s}: {c:3d} 幅 ({pct:5.1f}%)")

    # 2. 主题分布（从 content_analysis JSON 解析）
    print(f"\n【二、主题分布（按主题名称统计，一幅可有多主题）】")
    cur.execute("""
        SELECT content_analysis FROM tubi_analyses
        WHERE artist = ? AND content_analysis IS NOT NULL
    """, (ARTIST,))
    theme_counter = Counter()
    theme_by_period = defaultdict(Counter)
    for row in cur.fetchall():
        try:
            data = json.loads(row[0])
            themes = data.get("themes", [])
            period = data.get("period") or "未分期"
            for t in themes:
                name = t.get("name", "未知")
                theme_counter[name] += 1
                theme_by_period[period][name] += 1
        except Exception:
            continue

    for name, cnt in theme_counter.most_common():
        pct = cnt / total * 100 if total else 0
        print(f"  {name:12s}: {cnt:3d} 次 ({pct:5.1f}%)")

    # 3. 情感 polarity 分布
    print(f"\n【三、情感 Polarity 分布】")
    cur.execute("""
        SELECT content_analysis FROM tubi_analyses
        WHERE artist = ? AND content_analysis IS NOT NULL
    """, (ARTIST,))
    polarity_counter = Counter()
    emotion_scores = []
    for row in cur.fetchall():
        try:
            data = json.loads(row[0])
            sent = data.get("sentiment", {})
            polarity = sent.get("polarity", "neutral")
            polarity_counter[polarity] += 1
            score = sent.get("emotion_score")
            if score is not None:
                emotion_scores.append(score)
        except Exception:
            continue

    for pol, cnt in polarity_counter.most_common():
        pct = cnt / total * 100 if total else 0
        print(f"  {pol:12s}: {cnt:3d} 幅 ({pct:5.1f}%)")

    # 4. 情感分数分段（对应 auto_tags 的5档）
    print(f"\n【四、情感分数分段（5档）】")
    if emotion_scores:
        ranges = [
            ("愤慨/压抑  ", -99, -2.0),
            ("恬淡悠然  ", -2.0, -0.5),
            ("平静      ", -0.5, 0.5),
            ("旷达      ", 0.5, 2.0),
            ("昂扬向上  ", 2.0, 99),
        ]
        for label, lo, hi in ranges:
            cnt = sum(1 for s in emotion_scores if lo < s <= hi)
            pct = cnt / len(emotion_scores) * 100
            print(f"  {label} ({lo:+.1f}~{hi:+.1f}]: {cnt:3d} 幅 ({pct:5.1f}%)")
        print(f"  分数范围: {min(emotion_scores):+.2f} ~ {max(emotion_scores):+.2f}, 均值: {sum(emotion_scores)/len(emotion_scores):+.2f}")

    # 5. 题材/画材分布（material_tags）
    print(f"\n【五、题材/画材分布（material_tags）】")
    cur.execute("""
        SELECT material_tags FROM tubi_analyses
        WHERE artist = ? AND material_tags IS NOT NULL AND material_tags != ''
    """, (ARTIST,))
    material_counter = Counter()
    for row in cur.fetchall():
        tags = row[0]
        if tags:
            for t in str(tags).split(","):
                t = t.strip()
                if t:
                    material_counter[t] += 1

    for tag, cnt in material_counter.most_common(20):
        print(f"  {tag:12s}: {cnt:3d} 次")

    # 6. 尺幅分布
    print(f"\n【六、尺幅分布（按平方尺阈值）】")
    cur.execute("""
        SELECT artwork_height_cm, artwork_width_cm
        FROM tubi_analyses
        WHERE artist = ?
          AND artwork_height_cm IS NOT NULL
          AND artwork_width_cm IS NOT NULL
    """, (ARTIST,))
    size_cats = Counter()
    for row in cur.fetchall():
        h, w = row
        area = (h * w) / 1089
        if area < 2:
            size_cats["小幅(<2)"] += 1
        elif area < 4:
            size_cats["四开/斗方(2-4)"] += 1
        elif area < 8:
            size_cats["四尺整纸(4-8)"] += 1
        elif area < 12:
            size_cats["五尺整纸(8-12)"] += 1
        elif area < 20:
            size_cats["六尺整纸(12-20)"] += 1
        elif area < 35:
            size_cats["八尺整纸(20-35)"] += 1
        else:
            size_cats["丈二以上(>35)"] += 1

    total_size = sum(size_cats.values())
    for cat, cnt in size_cats.most_common():
        pct = cnt / total_size * 100 if total_size else 0
        print(f"  {cat:20s}: {cnt:3d} 幅 ({pct:5.1f}%)")

    # 7. 各时期的主题交叉分布
    print(f"\n【七、各时期主题交叉分布】")
    period_order = ["早期", "中期", "晚期", "年代不详", "未分期"]
    for period in period_order:
        if period not in theme_by_period:
            continue
        print(f"\n  --- {period} ---")
        for name, cnt in theme_by_period[period].most_common():
            print(f"    {name:12s}: {cnt:3d} 次")

    conn.close()
    print(f"\n{'='*60}")
    print("分析完成")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
