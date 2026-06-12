"""检查 SQLite 中的书籍列表"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询所有书籍
cursor.execute("SELECT id, file_name, title, status FROM pdf_books ORDER BY created_at DESC")
books = cursor.fetchall()

print("=== SQLite 中的书籍列表 ===\n")
for book in books:
    print(f"ID: {book[0]}")
    print(f"  file_name: {book[1]}")
    print(f"  title: {book[2]}")
    print(f"  status: {book[3]}")
    print()

conn.close()
