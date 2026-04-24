import sqlite3, json
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("""
    SELECT id, title, content_analysis
    FROM tubi_analyses
    WHERE artist LIKE '%李鱓%'
      AND content_analysis IS NOT NULL
      AND LENGTH(content_analysis) > 10
""")
unclassified = []
for row in cur.fetchall():
    try:
        ca = json.loads(row[1])
        themes = ca.get('themes', [])
        uncat = [t for t in themes if t.get('name') in ('未分类', '未知', None, '')]
        if uncat:
            unclassified.append({'id': row[0], 'title': row[1], 'themes': themes, 'content': ca.get('inscription_content', '')[:80]})
    except Exception as e:
        print('Error for ID', row[0], ':', e)
print('未分类/未知主题记录数:', len(unclassified))
for r in unclassified:
    print('ID:', r['id'], '| title:', r['title'])
    print('  content:', r['content'])
    print('  themes:', r['themes'])
conn.close()