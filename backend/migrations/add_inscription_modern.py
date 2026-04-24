"""
数据库迁移脚本：添加 inscription_modern 字段
运行：python backend/migrations/add_inscription_modern.py
"""

import os
import sys
import sqlite3

# 确保能导入backend模块
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

DB_PATH = os.path.join(backend_dir, "data", "calligraphy.db")


def migrate():
    """执行迁移"""
    if not os.path.exists(DB_PATH):
        print(f"数据库文件不存在: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 检查字段是否已存在
    cur.execute("PRAGMA table_info(tubi_analyses)")
    columns = [row[1] for row in cur.fetchall()]

    if "inscription_modern" in columns:
        print("字段 inscription_modern 已存在，跳过迁移")
        conn.close()
        return True

    # 添加字段
    try:
        cur.execute("""
            ALTER TABLE tubi_analyses
            ADD COLUMN inscription_modern TEXT
        """)
        conn.commit()
        print("成功添加字段: inscription_modern")
    except Exception as e:
        print(f"添加字段失败: {e}")
        conn.close()
        return False

    # 验证
    cur.execute("PRAGMA table_info(tubi_analyses)")
    columns = [row[1] for row in cur.fetchall()]
    if "inscription_modern" in columns:
        print("迁移验证成功")
    else:
        print("迁移验证失败")
        conn.close()
        return False

    conn.close()
    return True


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
