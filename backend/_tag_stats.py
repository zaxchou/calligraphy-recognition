# -*- coding: utf-8 -*-
import sqlite3, json
from collections import Counter

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

cur.execute("""
    SELECT material_tags
    FROM tubi_analyses
    WHERE (artist LIKE '%李鱓%')
      AND material_tags IS NOT NULL
      AND material_tags != ''
""")

all_tags = []
for row in cur.fetchall():
    tags = row[0].split(',')
    for t in tags:
        t = t.strip()
        if t:
            all_tags.append(t)

counter = Counter(all_tags)
print(f"总标签数: {len(all_tags)}, 去重后: {len(counter)}")
print("\n全部标签（按频次排序）：")
for tag, cnt in counter.most_common():
    print(f"  {tag}: {cnt}")