import sqlite3

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

cur.execute("""
    SELECT inscription_content, inscription_modern
    FROM tubi_analyses
    WHERE image_id = 'fb963d12-f312-4782-8f58-62baf422da7a'
""")
row = cur.fetchone()
orig = row[0]
modern = row[1]

print(f"原文长度: {len(orig)} 字")
print(f"译文长度: {len(modern)} 字")

# 逐段对比：原文有多少段，译文有多少段
import re
orig_parts = [p.strip() for p in re.split(r'\n(?=第[一二三四五六七八九十]+处|（?[一二三四五六七八九十]+）)', orig) if p.strip()]
modern_parts = [p.strip() for p in modern.split('\n\n') if p.strip()]

print(f"\n原文分段数: {len(orig_parts)}")
print(f"译文分段数: {len(modern_parts)}")

# 检查译文是否以原文开头（判断是否翻译成功）
first_orig_line = orig.split('\n')[0][:20]
first_modern_line = modern.split('\n')[0][:20]
print(f"\n原文首句: {first_orig_line}")
print(f"译文首句: {first_modern_line}")
print(f"是否相同(原文输出了): {first_orig_line in first_modern_line or first_orig_line == first_modern_line}")

# 检查最后一段（题画诗）是否翻译了
print("\n=== 最后一段（题画诗）对比 ===")
last_orig = orig_parts[-1] if orig_parts else ""
print(f"最后一段原文: {last_orig[:200]}")
last_modern = modern_parts[-1] if modern_parts else ""
print(f"最后一段译文: {last_modern[:200]}")

conn.close()
