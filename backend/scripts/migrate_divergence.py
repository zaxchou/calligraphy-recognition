"""
迁移脚本：创建 analysis_divergence 表
运行方式: cd backend && python scripts/migrate_divergence.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "calligraphy.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analysis_divergence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL,
    image_id TEXT,
    artist TEXT,
    inscription_content TEXT,
    v4_themes TEXT,
    v4_sentiment TEXT,
    v4_confidence REAL,
    llm_themes TEXT,
    llm_sentiment TEXT,
    divergence_type TEXT,
    divergence_detail TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
)
"""


def migrate():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("[OK] analysis_divergence 表创建成功")
    except Exception as e:
        print(f"[ERR] {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
