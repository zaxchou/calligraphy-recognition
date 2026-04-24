"""
数据库迁移脚本：添加 position_analysis 字段
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "calligraphy.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查列是否已存在
    cursor.execute("PRAGMA table_info(tubi_analyses)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "position_analysis" not in columns:
        print("添加 position_analysis 列...")
        cursor.execute("ALTER TABLE tubi_analyses ADD COLUMN position_analysis TEXT DEFAULT '{}';")
        conn.commit()
        print("✓ 列添加成功")
    else:
        print("✓ position_analysis 列已存在")
    
    conn.close()
    print("数据库迁移完成")

if __name__ == "__main__":
    migrate()
