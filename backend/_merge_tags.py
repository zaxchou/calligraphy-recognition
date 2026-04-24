# -*- coding: utf-8 -*-
"""合并/清理 material_tags 字段"""
import sqlite3, re

conn = sqlite3.connect('data/calligraphy.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 先看当前含"岁寒三友"的记录
cur.execute("""
    SELECT id, title, material_tags
    FROM tubi_analyses
    WHERE (artist LIKE '%李鱓%')
      AND material_tags IS NOT NULL
      AND material_tags LIKE '%岁寒三友%'
""")
print("含岁寒三友的记录：")
for row in cur.fetchall():
    print(f"  id={row['id']} {row['title']}: {row['material_tags']}")

conn.close()

# 合并规则：被合并→合并后
MERGE_MAP = {
    '柏':   '松',
    '富贵': '牡丹',
    '长寿': '桃',
    '莲':   '荷花',
    '藤':   '紫藤',
}

def apply_merge(tags_str):
    tags = [t.strip() for t in tags_str.split(',')]
    merged = []
    for t in tags:
        if t in MERGE_MAP:
            merged.append(MERGE_MAP[t])
        elif t == '岁寒三友':
            pass  # 删除
        else:
            merged.append(t)
    # 去重保持顺序
    seen = set()
    result = []
    for t in merged:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return ','.join(result)

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

cur.execute("""
    SELECT id, material_tags
    FROM tubi_analyses
    WHERE (artist LIKE '%李鱓%')
      AND material_tags IS NOT NULL
      AND material_tags != ''
""")

updated = 0
for row in cur.fetchall():
    new_tags = apply_merge(row[1])
    if new_tags != row[1]:
        cur.execute("UPDATE tubi_analyses SET material_tags = ? WHERE id = ?", (new_tags, row[0]))
        updated += 1
        print(f"  id={row[0]}: {row[1]} -> {new_tags}")

conn.commit()
print(f"\n更新了 {updated} 条记录")

# 验证合并结果
cur.execute("""
    SELECT material_tags
    FROM tubi_analyses
    WHERE (artist LIKE '%李鱓%')
      AND material_tags IS NOT NULL
      AND material_tags != ''
""")
from collections import Counter
all_tags = []
for row in cur.fetchall():
    for t in row[0].split(','):
        t = t.strip()
        if t:
            all_tags.append(t)
counter = Counter(all_tags)
print(f"\n合并后总标签数: {len(all_tags)}, 去重后: {len(counter)}")
for tag, cnt in counter.most_common():
    print(f"  {tag}: {cnt}")