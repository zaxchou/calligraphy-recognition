import sqlite3

db_path = "data/calligraphy.db"
target_ids = [477, 478, 479]

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

for rid in target_ids:
    c.execute("SELECT id, title, period_phase, content_analysis, theme_tags, inscription_verified FROM tubi_analyses WHERE id = ?", (rid,))
    row = c.fetchone()
    if not row:
        print("ID %s 不存在，跳过" % rid)
        continue

    print("处理: ID=%s, 标题=%s" % (row["id"], row["title"]))
    print("  当前分期: %s" % (row["period_phase"] or "无"))
    print("  当前分析数据: %s" % ("有(%s字节)" % len(row["content_analysis"]) if row["content_analysis"] else "无"))
    print("  当前主题标签: %s" % (row["theme_tags"] or "无"))
    print("  已校对: %s" % row["inscription_verified"])

    # 清空分析相关字段，恢复为未分析状态
    c.execute("""
        UPDATE tubi_analyses
        SET content_analysis = NULL,
            period_phase = NULL,
            theme_tags = NULL,
            inscription_verified = 0
        WHERE id = ?
    """, (rid,))
    print("  -> 已重置为未分析状态")

conn.commit()
print("\n全部完成，共处理 %s 条记录" % len(target_ids))
conn.close()
