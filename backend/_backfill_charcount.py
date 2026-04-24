"""
回填 char_count 为 NULL 的记录
"""
import sqlite3
import json

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 查询有 inscription_content 但 char_count 为空的记录
cur.execute("""
    SELECT id, inscription_content, char_count, content_analysis
    FROM tubi_analyses
    WHERE inscription_content IS NOT NULL
    AND LENGTH(inscription_content) > 0
    AND (char_count = 0 OR char_count IS NULL)
""")
rows = cur.fetchall()

print(f"需要回填的记录数: {len(rows)}")

# 分两类：1) 有 content_analysis 可以提取  2) 需要直接计算
updated_from_ca = 0
updated_from_content = 0

for id, content, char_count, ca in rows:
    new_char_count = None

    # 优先从 content_analysis 提取
    if ca:
        try:
            ca_json = json.loads(ca)
            new_char_count = ca_json.get('char_count')
        except:
            pass

    # 如果没有，从 inscription_content 直接计算
    if new_char_count is None:
        new_char_count = len(content.strip())

    # 更新
    cur.execute("UPDATE tubi_analyses SET char_count = ? WHERE id = ?", (new_char_count, id))
    print(f"id={id}: char_count = {new_char_count}")

conn.commit()
print(f"\n完成！回填了 {len(rows)} 条记录")

conn.close()