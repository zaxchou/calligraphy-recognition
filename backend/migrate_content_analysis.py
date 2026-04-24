"""
数据库迁移脚本：为 tubi_analyses 表新增学术分析相关字段
运行方式：cd backend && python migrate_content_analysis.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "calligraphy.db")

NEW_COLUMNS = [
    ("period_phase", "VARCHAR(10)"),
    ("char_count", "INTEGER"),
    ("word_count", "INTEGER"),
    ("theme_tags", "VARCHAR(200)"),
    ("content_analysis", "TEXT"),  # SQLite 用 TEXT 存储 JSON
    ("inscription_verified", "INTEGER DEFAULT 0"),  # SQLite BOOLEAN 用 INTEGER
    ("inscription_verified_at", "DATETIME"),
]


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 获取已有列名
    cur.execute("PRAGMA table_info(tubi_analyses)")
    existing_cols = {row[1] for row in cur.fetchall()}

    added = 0
    for col_name, col_type in NEW_COLUMNS:
        if col_name in existing_cols:
            print(f"  SKIP: {col_name} already exists")
        else:
            sql = f"ALTER TABLE tubi_analyses ADD COLUMN {col_name} {col_type}"
            try:
                cur.execute(sql)
                print(f"  ADD:  {col_name} ({col_type})")
                added += 1
            except Exception as e:
                print(f"  FAIL: {col_name} - {e}")

    conn.commit()

    # 验证
    cur.execute("PRAGMA table_info(tubi_analyses)")
    final_cols = [row[1] for row in cur.fetchall()]
    print(f"\nDone. Added {added} columns. Total: {len(final_cols)} columns")
    print(f"Columns: {final_cols}")

    conn.close()


if __name__ == "__main__":
    print(f"Migrating database: {DB_PATH}")
    migrate()
