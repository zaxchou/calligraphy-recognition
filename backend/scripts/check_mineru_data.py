"""检查 MinerU content_list 中是否有页码信息"""
import sqlite3
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

# 检查 pdf_books 表是否有 content_list 字段
cursor.execute("PRAGMA table_info(pdf_books)")
columns = [row[1] for row in cursor.fetchall()]
print(f'pdf_books columns: {columns}')

# 检查是否有 MinerU 原始数据存储
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f'\nAll tables: {tables}')

# 检查 books 目录下是否有 MinerU 输出文件
import os
books_dir = os.path.join('data', 'knowledge', 'books')
if os.path.exists(books_dir):
    print(f'\nBooks directory contents:')
    for item in os.listdir(books_dir):
        full = os.path.join(books_dir, item)
        if os.path.isdir(full):
            print(f'  {item}/')
            for sub in os.listdir(full):
                print(f'    {sub}')
        else:
            print(f'  {item}')

conn.close()
