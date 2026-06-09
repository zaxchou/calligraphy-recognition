"""画家专属文献库 — 数据库迁移脚本
运行方式：python migrations/add_artist_literature.py
"""
import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge.db')

def migrate(db_path=None):
    db = db_path or DB_PATH
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    # 检查是否已迁移
    cursor.execute("PRAGMA table_info(pdf_books)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'artist_id' in cols:
        print("Already migrated, skipping.")
        conn.close()
        return

    print("Running artist_literature migration...")

    # PdfBook 新列
    conn.execute('ALTER TABLE pdf_books ADD COLUMN artist_id INTEGER')
    conn.execute('ALTER TABLE pdf_books ADD COLUMN document_type TEXT DEFAULT "book" NOT NULL')
    conn.execute('ALTER TABLE pdf_books ADD COLUMN journal TEXT')
    conn.execute('ALTER TABLE pdf_books ADD COLUMN publish_year INTEGER')
    conn.execute('ALTER TABLE pdf_books ADD COLUMN doi TEXT')

    # ChatSession 新列
    conn.execute('ALTER TABLE chat_sessions ADD COLUMN session_type TEXT DEFAULT "global" NOT NULL')
    conn.execute('ALTER TABLE chat_sessions ADD COLUMN artist_id INTEGER')

    # 索引
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pdf_books_artist ON pdf_books(artist_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_sessions_artist ON chat_sessions(artist_id)')

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
