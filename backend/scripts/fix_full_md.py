#!/usr/bin/env python3
"""手动更新 full_md 到数据库"""
import sys
import os
import sqlite3

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.pantianshou_composition.mineru_client import parse_pdf_with_mineru

# PDF 文件路径
pdf_path = "Z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/uploads/9727e677-93eb-44f1-a20c-cbb090415721_潘天寿《关于构图问题》.pdf"
DB_PATH = "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/knowledge.db"

print("=== 修复 full_md ===\n")

# 1. 获取 full_md
print("1. 调用 MinerU API 获取 full_md...")
result = parse_pdf_with_mineru(pdf_path)

if not result.success:
    print(f"失败: {result.error}")
    sys.exit(1)

full_md = result.full_md
print(f"   获取到 full_md: {len(full_md or '')} 字符")

# 2. 更新数据库
print("\n2. 更新数据库...")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 获取书籍 ID
c.execute("SELECT id, title FROM pdf_books")
books = c.fetchall()

for book_id, title in books:
    print(f"   更新书籍: {title} (ID: {book_id})")
    c.execute("UPDATE pdf_books SET full_md = ? WHERE id = ?", (full_md, book_id))

conn.commit()
conn.close()

print("\n3. 验证更新...")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT id, title, full_md IS NOT NULL, LENGTH(full_md) FROM pdf_books")
for row in c.fetchall():
    print(f"   {row[1]}: has_full_md={row[2]}, length={row[3]}")
conn.close()

print("\n完成！")
