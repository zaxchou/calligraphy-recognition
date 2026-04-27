"""删除刘海勇的错误规则记录"""
import sqlite3, os
db_path = os.path.join(os.path.dirname(__file__), "..", "data", "calligraphy.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT id, artist_name, life_stages FROM artist_rules WHERE artist_name = ?", ("刘海勇",)).fetchone()
if row:
    print("当前刘海勇规则 id=", row["id"], " life_stages=", row["life_stages"])
    conn.execute("DELETE FROM artist_rules WHERE artist_name = ?", ("刘海勇",))
    conn.commit()
    print("已删除，等重启后端后重新用 AI 发现生成（会读取其 1976 年出生年份）")
else:
    print("刘海勇无规则记录")
conn.close()

# 验证 artists 表有出生年份
conn2 = sqlite3.connect(db_path)
r = conn2.execute("SELECT name, birth_year FROM artists WHERE name = ?", ("刘海勇",)).fetchone()
if r:
    print(f"artists 表确认: {r[0]}, 出生年份={r[1]}")
else:
    print("⚠️ artists 表中没有刘海勇的记录，请先在管理后台创建")
conn2.close()
