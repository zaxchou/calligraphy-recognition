import sqlite3

db_path = "data/calligraphy.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
    SELECT id, title, year, created_at, period_phase, inscription_verified, content_analysis
    FROM tubi_analyses
    ORDER BY created_at DESC
    LIMIT 5
""")

rows = c.fetchall()
print("最近上传的5条记录：")
print("-" * 80)
for r in rows:
    has_period = "[有]" if r["period_phase"] else "[无]"
    has_analysis = "[有]" if r["content_analysis"] else "[无]"
    print("ID: %s" % r["id"])
    print("  标题: %s" % (r["title"] or "无标题"))
    print("  年份: %s" % (r["year"] or "未知"))
    print("  上传时间: %s" % r["created_at"])
    print("  分期: %s %s" % ((r["period_phase"] or "无"), has_period))
    print("  已分析: %s | 已校对: %s" % (has_analysis, r["inscription_verified"]))
    print()
conn.close()
