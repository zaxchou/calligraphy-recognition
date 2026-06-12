# -*- coding: utf-8 -*-
"""精确诊断：只看第一主题的分布"""
import sqlite3
import json
from collections import Counter

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 只看李鱓的第一主题
cur.execute("""
    SELECT content_analysis FROM tubi_analyses
    WHERE artist = '李鱓' AND content_analysis IS NOT NULL
""")
rows = cur.fetchall()
total = len(rows)

# 第一主题分布
primary_themes = Counter()
all_themes = Counter()
polarities = Counter()

for row in rows:
    try:
        data = json.loads(row[0])
        themes = data.get("themes", [])
        if themes:
            primary_themes[themes[0].get("name", "?")] += 1
        for t in themes:
            all_themes[t.get("name", "?")] += 1
        sent = data.get("sentiment", {})
        polarities[sent.get("polarity", "neutral")] += 1
    except:
        pass

print("=" * 60)
print(f"李鱓 {total} 幅 -- 第一主题分布")
print("=" * 60)
for name, cnt in primary_themes.most_common():
    pct = cnt / total * 100
    print(f"  {name:12s}: {cnt:3d} ({pct:5.1f}%)")

print(f"\n所有主题（含2nd/3rd）分布:")
for name, cnt in all_themes.most_common():
    pct = cnt / total * 100
    print(f"  {name:12s}: {cnt:3d} ({pct:5.1f}%)")

print(f"\n情感分布:")
for pol, cnt in polarities.most_common():
    pct = cnt / total * 100
    print(f"  {pol:12s}: {cnt:3d} ({pct:5.1f}%)")

conn.close()
