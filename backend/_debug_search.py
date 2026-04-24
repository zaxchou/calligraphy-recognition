import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
# 搜索 content_analysis 中包含"未分类"的记录
cur.execute("SELECT id, title, LENGTH(content_analysis) FROM tubi_analyses WHERE artist LIKE '%李鱓%' AND content_analysis LIKE '%未分类%'")
rows = cur.fetchall()
print('含有未分类的记录:', len(rows))
for row in rows:
    print('ID:', row[0], '| title:', row[1], '| len:', row[2])

# 也搜索包含"未知"的
cur.execute("SELECT id, title, LENGTH(content_analysis) FROM tubi_analyses WHERE artist LIKE '%李鱓%' AND content_analysis LIKE '%未知%'")
rows2 = cur.fetchall()
print('含有未知的记录:', len(rows2))
conn.close()