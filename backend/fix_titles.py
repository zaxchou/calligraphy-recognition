import sqlite3
db_path = 'data/calligraphy.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 获取所有需要编号的记录
cur.execute("""SELECT id, title FROM tubi_analyses
    WHERE title IN ('花鸟草虫图册', '花卉十二开', '兰竹图册')
    ORDER BY id""")
rows = cur.fetchall()

print("原始数据:")
for r in rows:
    print(f"  id={r[0]}: {r[1]}")

# 按标题分组编号
from collections import defaultdict
groups = defaultdict(list)
for r in rows:
    groups[r[1]].append(r[0])

updates = []
for title, ids in groups.items():
    for i, db_id in enumerate(sorted(ids), 1):
        new_title = f"{title}{i}"
        updates.append((new_title, db_id))
        print(f"  id={db_id}: {title} -> {new_title}")

print(f"\n共 {len(updates)} 条需要更新")
cur.executemany("UPDATE tubi_analyses SET title = ? WHERE id = ?", updates)
conn.commit()
print("已完成更新")
conn.close()
