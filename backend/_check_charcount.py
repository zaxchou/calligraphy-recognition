import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 查询总记录数
cur.execute("SELECT COUNT(*) FROM tubi_analyses")
total = cur.fetchone()[0]

# 查询有 inscription_content 的记录数
cur.execute("SELECT COUNT(*) FROM tubi_analyses WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0")
with_content = cur.fetchone()[0]

# 查询 char_count = 0 或为空的记录
cur.execute("SELECT COUNT(*) FROM tubi_analyses WHERE char_count = 0 OR char_count IS NULL")
zero_char = cur.fetchone()[0]

# 查询有内容但 char_count = 0 的记录
cur.execute("""
    SELECT COUNT(*) FROM tubi_analyses
    WHERE inscription_content IS NOT NULL
    AND LENGTH(inscription_content) > 0
    AND (char_count = 0 OR char_count IS NULL)
""")
content_but_zero = cur.fetchone()[0]

print(f"总记录数: {total}")
print(f"有 inscription_content 的记录: {with_content}")
print(f"char_count = 0 或为空的: {zero_char}")
print(f"有内容但字数=0的: {content_but_zero}")

# 查看一些有内容但字数=0的例子
print("\n--- 有内容但字数=0的例子 ---")
cur.execute("""
    SELECT id, artist, title, LENGTH(inscription_content) as len, char_count
    FROM tubi_analyses
    WHERE inscription_content IS NOT NULL
    AND LENGTH(inscription_content) > 0
    AND (char_count = 0 OR char_count IS NULL)
    LIMIT 10
""")
for r in cur.fetchall():
    print(r)

conn.close()