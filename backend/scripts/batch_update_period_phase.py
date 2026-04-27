#!/usr/bin/env python3
"""
批量更新分期数据（period_phase）
为所有有年份（year）但没有分期（period_phase）的记录自动计算分期
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.tubi_analysis import TubiAnalysis
from app.services.inscription_content_analyzer import get_period_phase

def batch_update_period_phase():
    """批量更新分期数据"""
    db = SessionLocal()
    try:
        # 查询所有有 year 但没有 period_phase 的记录
        records = db.query(TubiAnalysis).filter(
            TubiAnalysis.year.isnot(None),
            (TubiAnalysis.period_phase == None) | (TubiAnalysis.period_phase == '')
        ).all()
        
        print(f"找到 {len(records)} 条需要更新分期的记录")
        
        updated_count = 0
        for record in records:
            # 自动计算分期
            period_phase = get_period_phase(record.year, record.artist)
            
            if period_phase and period_phase != record.period_phase:
                print(f"  更新 ID={record.id}, 标题={record.title}, year={record.year}, artist={record.artist} -> period_phase={period_phase}")
                record.period_phase = period_phase
                updated_count += 1
        
        # 提交更改
        db.commit()
        print(f"\n批量更新完成，共更新 {updated_count} 条记录")
        
    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def update_all_records():
    """更新所有有年份的记录（强制重新计算）"""
    db = SessionLocal()
    try:
        # 查询所有有 year 的记录
        records = db.query(TubiAnalysis).filter(
            TubiAnalysis.year.isnot(None)
        ).all()
        
        print(f"找到 {len(records)} 条有年份的记录")
        
        updated_count = 0
        for record in records:
            # 重新计算分期
            period_phase = get_period_phase(record.year, record.artist)
            
            if period_phase != record.period_phase:
                print(f"  更新 ID={record.id}, 标题={record.title}, year={record.year}, artist={record.artist} -> period_phase={period_phase}")
                record.period_phase = period_phase
                updated_count += 1
        
        # 提交更改
        db.commit()
        print(f"\n批量更新完成，共更新 {updated_count} 条记录")
        
    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='批量更新分期数据（period_phase）')
    parser.add_argument('--all', action='store_true', help='更新所有有年份的记录（强制重新计算）')
    args = parser.parse_args()
    
    if args.all:
        print("模式: 更新所有有年份的记录")
        update_all_records()
    else:
        print("模式: 只更新缺少分期的记录")
        batch_update_period_phase()
