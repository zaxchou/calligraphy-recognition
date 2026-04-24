import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("SELECT id, title, LENGTH(content_analysis), SUBSTR(content_analysis, 1, 100) FROM tubi_analyses WHERE artist LIKE '%李鱓%' AND id IN (1,2,3,4,5)")
for row in cur.fetchall():
    print('ID:', row[0], '| title:', row[1], '| len:', row[2], '| first100:', repr(row[3]))
conn.close()