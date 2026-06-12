"""检查 SQLite 中的书籍数据"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge.db")
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 列出所有书籍
cursor = conn.cursor()
cursor.execute("SELECT id, title, created_at FROM pdf_books ORDER BY created_at")
books = cursor.fetchall()
print(f"共 {len(books)} 本书:")
for b in books:
    print(f"  id={b['id'][:12]}...  title='{b['title']}'  created={b['created_at']}")

# 检查是否有 UUID 前缀的书名
print("\n检查 UUID 前缀:")
for b in books:
    title = b["title"]
    if "_" in title:
        parts = title.split("_", 1)
        if len(parts[0]) == 36:  # UUID 长度
            print(f"  发现 UUID 前缀: '{title}'")

conn.close()
