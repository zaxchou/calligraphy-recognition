import sqlite3
db_path = 'data/calligraphy.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# id=102 是 p64 (1734), id=103 是 p122 (1740)
cur.execute("UPDATE tubi_analyses SET year = 1734 WHERE id = 102")
print(f"修复 id=102 (p64): {cur.rowcount} 条, year=1734")

cur.execute("UPDATE tubi_analyses SET year = 1740 WHERE id = 103")
print(f"修复 id=103 (p122): {cur.rowcount} 条, year=1740")

conn.commit()
conn.close()
