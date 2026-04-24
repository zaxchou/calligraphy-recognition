# -*- coding: utf-8 -*-
import sqlite3, json

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 看有content_analysis的记录有哪些字段
cur.execute("""
    SELECT id, title, year, period_phase, inscription_content, inscription_modern,
           seal_content, content_analysis, position_analysis,
           inscription_percent, painting_percent, blank_percent
    FROM tubi_analyses
    WHERE (artist LIKE '%李鱓%')
      AND content_analysis IS NOT NULL
    LIMIT 3
""")

for row in cur.fetchall():
    print("=== record", row[0], "===")
    print("title:", row[1])
    print("year:", row[2])
    print("period_phase:", row[3])
    print("inscription_content:", (row[4] or '')[:60])
    print("inscription_modern:", (row[5] or '')[:60])
    print("seal_content:", row[6])
    print("inscription_percent:", row[9])
    print("painting_percent:", row[10])
    print("blank_percent:", row[11])
    if row[7]:
        ca = json.loads(row[7])
        print("content_analysis:", json.dumps(ca, ensure_ascii=False)[:200])
    if row[8]:
        pa = json.loads(row[8])
        print("position_analysis:", json.dumps(pa, ensure_ascii=False)[:200])
    print()

conn.close()