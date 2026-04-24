#!/usr/bin/env python3
"""清空数据库中的所有数据"""

import sys
import os

# 添加backend到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.core.database import SessionLocal

def clear_all_data():
    """清空所有数据表"""
    db = SessionLocal()
    try:
        # 清空题跋分析结果
        try:
            result1 = db.execute(text("DELETE FROM tubi_analyses"))
            print(f"已清空 tubi_analyses 表，删除了 {result1.rowcount} 条记录")
        except Exception as e:
            print(f"tubi_analyses 表不存在或已清空: {e}")

        # 清空识别日志
        try:
            result2 = db.execute(text("DELETE FROM recognition_logs"))
            print(f"已清空 recognition_logs 表，删除了 {result2.rowcount} 条记录")
        except Exception as e:
            print(f"recognition_logs 表不存在或已清空: {e}")

        # 清空碑帖表
        try:
            result3 = db.execute(text("DELETE FROM steles"))
            print(f"已清空 steles 表，删除了 {result3.rowcount} 条记录")
        except Exception as e:
            print(f"steles 表不存在或已清空: {e}")

        # 清空字符表
        try:
            result4 = db.execute(text("DELETE FROM characters"))
            print(f"已清空 characters 表，删除了 {result4.rowcount} 条记录")
        except Exception as e:
            print(f"characters 表不存在或已清空: {e}")

        db.commit()
        print("\n✅ 所有数据已清空！")

    except Exception as e:
        db.rollback()
        print(f"❌ 清空数据失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_data()
