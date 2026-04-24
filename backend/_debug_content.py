import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("""
    SELECT id, title, content_analysis
    FROM tubi_analyses
    WHERE artist LIKE '%李鱓%'
      AND content_analysis IS NOT NULL
    LIMIT 5
""")
for row in cur.fetchall():
    print('ID:', row[0], '| title:', row[1])
    ca = row[2]
    print('  content_analysis (first 200 chars):', repr(ca[:200]))
    print()
conn.close()