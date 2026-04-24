import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 回填 artist IS NULL 的最近记录
cur.execute("UPDATE tubi_analyses SET artist='李鱓' WHERE artist IS NULL")
conn.commit()
print(f'Updated {cur.rowcount} rows')

# Verify
cur.execute('SELECT id, image_id, filename, artist, status FROM tubi_analyses ORDER BY id DESC LIMIT 5')
for r in cur.fetchall():
    print(f'  id={r[0]} artist={r[3]} status={r[4]}')
conn.close()
