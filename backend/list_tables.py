#!/usr/bin/env python3
"""列出数据库中的所有表"""

import sys
import os

# 添加backend到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.core.database import SessionLocal

def list_tables():
    """列出所有表"""
    db = SessionLocal()
    try:
        # 查询所有表
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = result.fetchall()

        print("数据库中的表：")
        for table in tables:
            table_name = table[0]
            # 查询每个表的记录数
            count_result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = count_result.fetchone()[0]
            print(f"  - {table_name}: {count} 条记录")

    except Exception as e:
        print(f"查询失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_tables()
