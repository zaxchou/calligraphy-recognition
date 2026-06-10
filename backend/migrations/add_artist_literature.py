"""画家专属文献库 — 数据库迁移脚本
运行方式：python migrations/add_artist_literature.py

注意：项目使用两个 SQLite 数据库：
- knowledge.db: pdf_books, text_chunks, extracted_images, knowledge_tasks 等
- calligraphy.db: chat_sessions, chat_messages, artists 等
"""
import sqlite3
import os

BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
KNOWLEDGE_DB = os.path.join(BASE_DIR, 'knowledge.db')
CALLIGRAPHY_DB = os.path.join(BASE_DIR, 'calligraphy.db')


def _add_col(conn, table, col, dtype, default=None):
    """安全添加列（已存在则跳过）"""
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
    if col not in cols:
        sql = f'ALTER TABLE {table} ADD COLUMN {col} {dtype}'
        if default is not None:
            sql += f' DEFAULT "{default}"'
        conn.execute(sql)
        print(f'  + {table}.{col}')
        return True
    return False


def migrate():
    # === knowledge.db ===
    print(f'Migrating {KNOWLEDGE_DB}...')
    conn = sqlite3.connect(KNOWLEDGE_DB)
    changed = False
    changed |= _add_col(conn, 'pdf_books', 'artist_id', 'INTEGER')
    changed |= _add_col(conn, 'pdf_books', 'document_type', 'TEXT', 'book')
    changed |= _add_col(conn, 'pdf_books', 'journal', 'TEXT')
    changed |= _add_col(conn, 'pdf_books', 'publish_year', 'INTEGER')
    changed |= _add_col(conn, 'pdf_books', 'doi', 'TEXT')
    changed |= _add_col(conn, 'pdf_books', 'abstract', 'TEXT')
    changed |= _add_col(conn, 'pdf_books', 'keywords', 'TEXT')
    if changed:
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pdf_books_artist ON pdf_books(artist_id)')
    conn.commit()
    conn.close()
    print('  Done.' if changed else '  Already up to date.')

    # === calligraphy.db ===
    print(f'Migrating {CALLIGRAPHY_DB}...')
    conn = sqlite3.connect(CALLIGRAPHY_DB)
    changed = False
    changed |= _add_col(conn, 'chat_sessions', 'session_type', 'TEXT', 'global')
    changed |= _add_col(conn, 'chat_sessions', 'artist_id', 'INTEGER')
    if changed:
        conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_sessions_artist ON chat_sessions(artist_id)')
    conn.commit()
    conn.close()
    print('  Done.' if changed else '  Already up to date.')


if __name__ == '__main__':
    migrate()
