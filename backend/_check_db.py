import sqlite3
import json
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 查看真正有 theme code=3 (讽喻社会与民生) 的记录
print("数据库中 theme code=3 (讽喻社会与民生) 的记录:\n")
cur.execute("SELECT id, content_analysis, inscription_content FROM tubi_analyses WHERE content_analysis IS NOT NULL")
rows = cur.fetchall()

found = []
for r in rows:
    try:
        data = json.loads(r[1]) if isinstance(r[1], str) else r[1]
        themes = data.get('themes', [])
        for t in themes:
            if t.get('code') == 3:
                sentiment = data.get('sentiment', {}).get('polarity', 'N/A')
                found.append({
                    'id': r[0],
                    'inscription': r[2][:80] if r[2] else '',
                    'theme_name': t.get('name'),
                    'confidence': t.get('confidence'),
                    'sentiment': sentiment
                })
                break
    except:
        pass

print("共 %d 条\n" % len(found))
for item in found:
    print("id=%s" % item['id'])
    print("  sentiment: %s" % item['sentiment'])
    print("  confidence: %s" % item['confidence'])
    print("  inscription: %s" % item['inscription'])
    print()

conn.close()