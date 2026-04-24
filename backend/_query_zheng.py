import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("SELECT id, artist, title, year FROM tubi_analyses WHERE artist LIKE ?", ("%郑%",))
rows = cur.fetchall()
print(f"郑燮记录数: {len(rows)}")
for r in rows:
    print(r)
conn.close()