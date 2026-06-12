#!/usr/bin/env python3
"""检查知识库数据库中的书籍记录"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 获取所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("=== 知识库表 ===")
for t in tables:
    print(t[0])

# 查看 pdf_books 表结构
print("\n=== pdf_books 表结构 ===")
cursor.execute("PRAGMA table_info(pdf_books)")
for col in cursor.fetchall():
    print(f"  {col[1]} ({col[2]})")

# 查看所有书籍
print("\n=== 书籍列表 ===")
cursor.execute("SELECT id, title, file_name, stored_path FROM pdf_books")
for row in cursor.fetchall():
    print(f"ID: {row[0]}")
    print(f"  标题: {row[1]}")
    print(f"  文件名: {row[2]}")
    print(f"  存储路径: {row[3]}")
    print()

conn.close()