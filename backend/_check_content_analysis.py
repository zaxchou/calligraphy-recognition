import sqlite3
import json
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 查询有内容但 char_count = NULL 的记录
cur.execute("""
    SELECT id, artist, title, inscription_content, char_count, content_analysis
    FROM tubi_analyses
    WHERE inscription_content IS NOT NULL
    AND LENGTH(inscription_content) > 0
    AND (char_count = 0 OR char_count IS NULL)
""")
rows = cur.fetchall()

print(f"有内容但 char_count 为空的记录: {len(rows)}")

for r in rows:
    id, artist, title, content, char_count, ca = r
    print(f"\nid={id}, {artist}, {title}")
    print(f"  inscription_content: {content[:50]}..." if len(content) > 50 else f"  inscription_content: {content}")
    print(f"  char_count: {char_count}")
    if ca:
        try:
            ca_json = json.loads(ca)
            ca_char_count = ca_json.get('char_count', 'N/A')
            print(f"  content_analysis.char_count: {ca_char_count}")
        except:
            print(f"  content_analysis: 解析失败")
    else:
        print(f"  content_analysis: NULL")

conn.close()