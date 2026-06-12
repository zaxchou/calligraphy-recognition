#!/usr/bin/env python3
"""检查 knowledge.db 中的书籍映射"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge.db")

if not os.path.exists(db_path):
    print(f"错误: 数据库不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表结构
print("=== knowledge.db 表结构 ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"\n表: {table[0]}")
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")

# 检查 pdf_books 表
print("\n=== pdf_books 表内容 ===")
try:
    cursor.execute("SELECT id, title, file_name FROM pdf_books")
    books = cursor.fetchall()
    for book in books:
        print(f"  ID: {book[0]}")
        print(f"  Title: {book[1]}")
        print(f"  File: {book[2]}")
        print()
except Exception as e:
    print(f"查询失败: {e}")

conn.close()
