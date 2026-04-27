"""
迁移脚本：创建 artist_rules 表
运行方式: cd backend && python scripts/migrate_artist_rules.py
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "calligraphy.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS artist_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL UNIQUE,
    emotion_baseline REAL DEFAULT 0.0,
    life_stages TEXT DEFAULT '[]',
    sentiment_note TEXT DEFAULT '',
    theme_note TEXT DEFAULT '',
    theme_exceptions TEXT DEFAULT '{}',
    expected_theme_distribution TEXT DEFAULT '{}',
    expected_sentiment_distribution TEXT DEFAULT '{}',
    rules_version TEXT DEFAULT '5.4',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def migrate():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("[OK] artist_rules 表创建成功")
    except Exception as e:
        print(f"[ERR] 创建表失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
