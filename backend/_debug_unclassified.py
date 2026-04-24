import sqlite3, json
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("""
    SELECT id, title, content_analysis
    FROM tubi_analyses
    WHERE artist LIKE '%李鱓%'
      AND content_analysis IS NOT NULL
""")
for row in cur.fetchall():
    try:
        ca = json.loads(row[1])
        themes = ca.get('themes', [])
        if any(t.get('name') == '未分类' for t in themes):
            print('ID:', row[0], '| title:', row[1])
            print('  content:', ca.get('inscription_content', '')[:100])
            print('  themes:', themes)
    except Exception as e:
        pass
conn.close()