#!/usr/bin/env python3
"""检查 MinerU 解析结果"""
import sqlite3
import os
import zipfile
import json

DB_PATH = "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/knowledge.db"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 获取书籍
c.execute("SELECT id, stored_path, title FROM pdf_books")
books = c.fetchall()

for book_id, stored_path, title in books:
    print(f"\n=== {title or stored_path} ===")
    print(f"  stored_path: {stored_path}")
    print(f"  文件存在: {os.path.exists(stored_path)}")
    
    # 检查 MinerU 输出目录
    pdf_dir = os.path.dirname(stored_path)
    print(f"  PDF 目录: {pdf_dir}")
    
    # 列出目录内容
    if os.path.exists(pdf_dir):
        files = os.listdir(pdf_dir)
        print(f"  目录内容: {files[:10]}...")
        
        # 查找 zip 文件
        for f in files:
            if f.endswith('.zip'):
                zip_path = os.path.join(pdf_dir, f)
                print(f"\n  找到 ZIP: {zip_path}")
                try:
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        names = z.namelist()
                        print(f"  ZIP 内容: {names[:15]}...")
                        
                        # 检查是否有 full.md
                        for name in names:
                            if 'full.md' in name.lower() or name.endswith('.md'):
                                content = z.read(name).decode('utf-8')
                                print(f"  找到 MD 文件: {name} ({len(content)} 字符)")
                                print(f"  前 200 字符: {content[:200]}")
                except Exception as e:
                    print(f"  读取 ZIP 失败: {e}")

conn.close()
