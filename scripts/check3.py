import sqlite3
conn = sqlite3.connect(r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db')
print("=== 缺生平 ===")
rows = conn.execute("SELECT name,dynasty FROM artists WHERE (biography IS NULL OR biography='') AND name!='' ORDER BY dynasty,name").fetchall()
for r in rows: print(f"  {r[0]:10s} [{r[1]:10s}]")

print("\n=== hometown异常 ===")
rows = conn.execute("SELECT name,hometown FROM artists WHERE hometown LIKE '%院长%' OR hometown LIKE '%主席%' OR hometown LIKE '%书记%'").fetchall()
for r in rows: print(f"  {r[0]}: {r[1]}")

conn.close()
