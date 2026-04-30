"""检查大纲详细信息"""
import requests
import json
import sqlite3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

book_id = "b250300e-8ae4-486d-a73b-854708c048d3"

# 获取 PDF 总页数
conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()
cursor.execute("SELECT total_pages FROM pdf_books WHERE id = ?", (book_id,))
row = cursor.fetchone()
total_pages = row[0] if row else 0
conn.close()
print(f"PDF total pages: {total_pages}")

# 获取大纲
r = requests.get(f'http://localhost:8001/api/v1/knowledge/books/{book_id}/outline')
data = r.json()
outline = data.get('outline', [])

# 找出有页码的项
print("\n=== Items with explicit page numbers ===")
for i, item in enumerate(outline):
    page = item.get('page', 0)
    title = item.get('title', '')
    # 检查标题中是否包含页码（如 "...009"）
    import re
    page_match = re.search(r'[…\s]+(\d{1,3})$', title)
    if page_match:
        print(f"  {i:3d}. page={page:3d}, title={title[:60]}")

# 检查前10项
print("\n=== First 10 items ===")
for i, item in enumerate(outline[:10]):
    print(f"  {i:3d}. page={item.get('page', 0):3d}, title={item.get('title', '')[:60]}")

# 检查第100-110项
print("\n=== Items 100-110 ===")
for i in range(100, min(111, len(outline))):
    item = outline[i]
    print(f"  {i:3d}. page={item.get('page', 0):3d}, title={item.get('title', '')[:60]}")
