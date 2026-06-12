#!/usr/bin/env python3
"""检查 MinerU 入库结果"""
import sqlite3

DB_PATH = "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/knowledge.db"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 所有表
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]
print(f"数据库表: {tables}\n")

# 书籍
c.execute("SELECT id, file_name, title, full_md IS NOT NULL, outline IS NOT NULL FROM pdf_books")
books = c.fetchall()
for b in books:
    print(f"书籍: {b[2] or b[1]}")
    print(f"  ID: {b[0]}")
    print(f"  has_full_md: {b[3]}")
    print(f"  has_outline: {b[4]}")
    
    book_id = b[0]
    
    # 文本块
    c.execute("SELECT COUNT(*) FROM text_chunks WHERE book_id=?", (book_id,))
    tc = c.fetchone()[0]
    print(f"  文本块: {tc}")
    
    # 图像
    c.execute("SELECT COUNT(*) FROM extracted_images WHERE book_id=?", (book_id,))
    ic = c.fetchone()[0]
    print(f"  图像: {ic}")
    
    # 检查 associated_chunks
    c.execute("SELECT COUNT(*) FROM extracted_images WHERE book_id=? AND associated_chunks IS NOT NULL AND associated_chunks != '[]'", (book_id,))
    ac = c.fetchone()[0]
    print(f"  有关联文本块的图像: {ac}")
    
    # 检查 full_md 实际内容
    c.execute("SELECT full_md FROM pdf_books WHERE id=?", (book_id,))
    fmd = c.fetchone()[0]
    if fmd:
        print(f"  full_md 长度: {len(fmd)} 字符")
    else:
        print(f"  full_md: NULL")
    
    # 检查 outline 实际内容
    c.execute("SELECT outline FROM pdf_books WHERE id=?", (book_id,))
    ol = c.fetchone()[0]
    if ol:
        print(f"  outline: {ol[:200]}")
    else:
        print(f"  outline: NULL")
    
    print()

conn.close()
