import sqlite3

DB_PATH = "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/calligraphy.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 修复 period_phase='None' 的4条记录（year=1750 -> 晚期）
cur.execute(
    "UPDATE tubi_analyses SET period_phase = '晚期' "
    "WHERE period_phase IS NULL"
)
updated = cur.rowcount
conn.commit()

# 验证
cur.execute("SELECT id, title, year, period_phase FROM tubi_analyses WHERE id IN (192,193,194,195)")
for r in cur.fetchall():
    print(f"  ID={r[0]} | year={r[2]} | phase='{r[3]}' | {r[1][:40]}")

conn.close()
print(f"\nFixed {updated} records -> period_phase set to '晚期'")
