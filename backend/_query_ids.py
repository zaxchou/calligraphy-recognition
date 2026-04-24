import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 查询 id=9, 10, 56 的记录
for id in [9, 10, 56]:
    cur.execute("SELECT id, artist, title, year FROM tubi_analyses WHERE id = ?", (id,))
    row = cur.fetchone()
    print(f"id={id}: {row}")

# 搜索所有包含"郑"字的记录
cur.execute("SELECT id, artist, title, year FROM tubi_analyses WHERE artist LIKE ?", ("%郑%",))
rows = cur.fetchall()
print(f"\n包含'郑'字的记录: {len(rows)}")
for r in rows:
    print(r)

conn.close()