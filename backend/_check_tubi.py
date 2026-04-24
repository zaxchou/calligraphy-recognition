import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# Check analysis_note content samples
cur.execute("""
SELECT id, filename, analysis_note, title
FROM tubi_analyses
WHERE analysis_note IS NOT NULL AND analysis_note != ''
ORDER BY LENGTH(analysis_note) DESC
LIMIT 10
""")
rows = cur.fetchall()
print("=== analysis_note 样本（最长10条）===")
for r in rows:
    print(f"\nid={r[0]} | {r[1]}")
    print(f"  title: {r[3]}")
    note = r[2][:200] if r[2] else ""
    print(f"  analysis_note: {note}...")

# Count records with analysis_note
cur.execute("SELECT COUNT(*) FROM tubi_analyses WHERE analysis_note IS NOT NULL AND analysis_note != ''")
print(f"\n有 analysis_note 的记录: {cur.fetchone()[0]}")

# Check PAINTING_MATERIAL_RULES - look for existing material keywords
print("\n=== 从 analysis_note 中提取常见画材关键词 ===")
import re
keywords = ['竹', '兰', '梅', '菊', '松', '牡丹', '荷花', '莲', '石', '藤', '紫藤',
            '芭蕉', '桃', '柳', '芙蓉', '水仙', '玉兰', '海棠', '鸡', '鸟', '鱼',
            '蝶', '蝉', '蟹', '白菜', '萝卜', '葱', '蒜', '葡萄', '葫芦',
            '鹰', '鹤', '鸳鸯', '马', '牛', '山水', '云', '月']

cur.execute("SELECT analysis_note FROM tubi_analyses WHERE analysis_note IS NOT NULL AND analysis_note != ''")
notes = [r[0] for r in cur.fetchall()]
print(f"共 {len(notes)} 条 analysis_note")

from collections import Counter
freq = Counter()
for note in notes:
    for kw in keywords:
        if kw in note:
            freq[kw] += 1

print("\n画材关键词频次（前20）:")
for kw, cnt in freq.most_common(20):
    print(f"  {kw}: {cnt}次")

conn.close()
