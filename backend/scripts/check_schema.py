import sqlite3

conn = sqlite3.connect("data/calligraphy.db")
c = conn.cursor()
c.execute("PRAGMA table_info(tubi_analyses)")
rows = c.fetchall()
print("tubi_analyses 表字段：")
for r in rows:
    print("  %s: %s" % (r[1], r[2]))
conn.close()
