# -*- coding: utf-8 -*-
import sqlite3
import json
from collections import Counter

conn = sqlite3.connect('data/calligraphy.db')
c = conn.cursor()

print('=== period字段异常值样例 ===')
c.execute("""
    SELECT period, filepath, title
    FROM tubi_analyses
    WHERE artist = '李鱓' AND period = '66'
    LIMIT 5
""")
for r in c.fetchall():
    print(f'  period={r[0]}, title={r[2]}')

print('\n=== content_analysis中period字段分布 ===')
c.execute("""
    SELECT json_extract(content_analysis, '$.period') as p, COUNT(*) as cnt
    FROM tubi_analyses
    WHERE artist = '李鱓' AND content_analysis IS NOT NULL
    GROUP BY p
    ORDER BY cnt DESC
""")
for r in c.fetchall():
    p = r[0] or '(null/缺失)'
    print(f'  {p:15s}: {r[1]:3d}')

print('\n=== sentiment结构样例（前3条有emotion_score的）===')
c.execute("""
    SELECT json_extract(content_analysis, '$.sentiment') as s
    FROM tubi_analyses
    WHERE artist = '李鱓' AND content_analysis IS NOT NULL
      AND json_extract(content_analysis, '$.sentiment.emotion_score') IS NOT NULL
    LIMIT 3
""")
for r in c.fetchall():
    print(f'  {r[0]}')

print('\n=== 有emotion_score vs 无emotion_score ===')
c.execute("""
    SELECT 
        COUNT(CASE WHEN json_extract(content_analysis, '$.sentiment.emotion_score') IS NOT NULL THEN 1 END) as has_score,
        COUNT(CASE WHEN json_extract(content_analysis, '$.sentiment.emotion_score') IS NULL THEN 1 END) as no_score
    FROM tubi_analyses
    WHERE artist = '李鱓' AND content_analysis IS NOT NULL
""")
r = c.fetchone()
print(f'  有emotion_score: {r[0]}')
print(f'  无emotion_score: {r[1]}')

print('\n=== 题跋关键词抽查（懊、道人、落拓、罢、官）===')
keywords = ['懊', '道人', '落拓', '罢', '官']
for kw in keywords:
    c.execute(f"""
        SELECT COUNT(*) FROM tubi_analyses
        WHERE artist = '李鱓' AND content_analysis IS NOT NULL
          AND (json_extract(content_analysis, '$.translated_text') LIKE '%{kw}%'
               OR json_extract(content_analysis, '$.analysis_note') LIKE '%{kw}%'
               OR title LIKE '%{kw}%')
    """)
    print(f'  含"{kw}": {c.fetchone()[0]} 幅')

conn.close()
