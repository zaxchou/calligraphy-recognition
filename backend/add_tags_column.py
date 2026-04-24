"""
为 tubi_analyses 表添加 tags 字段
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "calligraphy.db")


def add_tags_column():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(tubi_analyses)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "tags" in columns:
            print("tags 字段已存在，无需添加")
            return
        
        # 添加 tags 字段（SQLite 不支持 COMMENT 语法）
        cursor.execute("""
            ALTER TABLE tubi_analyses 
            ADD COLUMN tags TEXT
        """)
        conn.commit()
        print("成功添加 tags 字段")
        
    except Exception as e:
        print(f"添加字段失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    add_tags_column()
