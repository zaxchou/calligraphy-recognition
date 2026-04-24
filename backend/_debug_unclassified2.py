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
        content = ca.get('inscription_content', '')
        if not themes or len(themes) == 0:
            print('NO THEME - ID:', row[0], '| title:', row[1])
            print('  content:', content[:80])
    except Exception as e:
        print('ERROR parsing ID:', row[0], e)
conn.close()
print('DONE')