"""
更新数据库中现有记录的period字段为年龄格式
李鱓生卒年：1686年—1756年
年龄 = 作画年份 - 1686
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.tubi_analysis import TubiAnalysis

LI_SHAN_BIRTH_YEAR = 1686

def update_period_to_age():
    db = SessionLocal()
    try:
        # 获取所有记录
        analyses = db.query(TubiAnalysis).all()
        updated_count = 0

        for analysis in analyses:
            year = analysis.year

            # 只要有year就更新period为年龄
            if year:
                try:
                    year_int = int(year)
                    age = year_int - LI_SHAN_BIRTH_YEAR
                    # 如果年龄不在合理范围(0-100)，可能是测试数据，跳过
                    if -50 <= age <= 150:
                        analysis.period = f"{age}岁"
                        updated_count += 1
                        print(f"更新: {analysis.title} - {year}年 -> {age}岁")
                except (ValueError, TypeError):
                    print(f"跳过: {analysis.title} - 年份格式错误: {year}")

        db.commit()
        print(f"\n共更新 {updated_count} 条记录")

    except Exception as e:
        print(f"更新失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_period_to_age()
