import sqlite3
import json

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 查"讽喻社会与民生"标签的作品
cur.execute("""
SELECT id, title, artist, theme_tags, content_analysis
FROM tubi_analyses
WHERE theme_tags LIKE '%讽喻社会与民生%'
""")
rows = cur.fetchall()
print(f'=== 讽喻社会与民生 作品数: {len(rows)} ===')
for r in rows:
    ca = json.loads(r[4]) if r[4] else {}
    themes = ca.get('themes', [])
    print(f'  id={r[0]} title={r[1]} | themes: {[t["name"] for t in themes]}')

print()

# 反过来：查"世俗祈愿与谐趣"的作品
cur.execute("""
SELECT id, title, artist, theme_tags, content_analysis
FROM tubi_analyses
WHERE theme_tags LIKE '%世俗祈愿与谐趣%'
""")
rows2 = cur.fetchall()
print(f'=== 世俗祈愿与谐趣 作品数: {len(rows2)} ===')
for r in rows2[:5]:
    ca = json.loads(r[4]) if r[4] else {}
    themes = ca.get('themes', [])
    print(f'  id={r[0]} title={r[1]} | themes: {[t["name"] for t in themes]}')

# 统计所有主题标签出现次数
cur.execute("SELECT theme_tags FROM tubi_analyses WHERE theme_tags IS NOT NULL AND theme_tags != ''")
from collections import Counter
all_tags = Counter()
for r in cur.fetchall():
    tags = r[0].split(',')
    for t in tags:
        t = t.strip()
        if t:
            all_tags[t] += 1
print('\n=== 所有主题标签分布 ===')
for tag, cnt in all_tags.most_common():
    print(f'  {tag}: {cnt}')

conn.close()
