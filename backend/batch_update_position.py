"""
批量更新脚本：为已有数据计算题跋位置分析
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.tubi_analysis import TubiAnalysis
from app.services.inscription_position_analyzer import analyze_inscription_position

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "calligraphy.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

def update_position_analysis():
    """为所有已有分析数据计算位置分析"""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # 获取所有已分析的数据（有regions但没有position_analysis或position_analysis为空的）
        analyses = db.query(TubiAnalysis).filter(
            TubiAnalysis.status == "analyzed",
            TubiAnalysis.regions.isnot(None)
        ).all()

        print(f"找到 {len(analyses)} 条需要更新的记录")

        updated_count = 0
        for analysis in analyses:
            try:
                regions = analysis.regions
                if not regions:
                    print(f"  跳过 {analysis.image_id}: 无区域数据")
                    continue

                width = analysis.image_width or 0
                height = analysis.image_height or 0

                if width == 0 or height == 0:
                    print(f"  跳过 {analysis.image_id}: 无有效尺寸")
                    continue

                # 计算位置分析
                position_analysis = analyze_inscription_position(regions, width, height)

                # 更新数据库
                analysis.position_analysis = position_analysis
                db.commit()

                updated_count += 1
                layout_type = position_analysis.get("layout_type", "未知")
                position = position_analysis.get("position", "未知")
                print(f"  ✓ 更新 {analysis.image_id}: {layout_type} ({position})")

            except Exception as e:
                print(f"  ✗ 更新 {analysis.image_id} 失败: {e}")
                db.rollback()
                continue

        print(f"\n完成！成功更新 {updated_count}/{len(analyses)} 条记录")

    except Exception as e:
        print(f"错误: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_position_analysis()
