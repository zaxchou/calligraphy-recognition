
"""
重新计算情感分析 - 仅更新 content_analysis 中的情感部分
使用修复后的情感算法
"""
import sys
import os
import io
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from app.core.database import SessionLocal
from app.models.tubi_analysis import TubiAnalysis
from app.services.inscription_content_analyzer import classify_inscription_v4, analyze_tiba_content
from app.services.auto_tags import compute_tags


def recompute_one(record, dry_run=False):
    """重新计算单条记录的情感分析"""
    image_id = record.image_id
    
    # 读取现有content_analysis
    try:
        ca = json.loads(record.content_analysis) if isinstance(record.content_analysis, str) else record.content_analysis
        if not ca:
            return False, "无content_analysis数据"
    except Exception as e:
        return False, f"解析content_analysis失败: {e}"
    
    # 先保存旧的情感用于比较
    old_polarity = ca.get('sentiment', {}).get('polarity', 'unknown')
    
    # 获取必要参数
    text = record.inscription_content or ""
    year = record.year
    title = record.title or ""
    analysis_note = record.analysis_note or ""
    width_cm = record.artwork_width_cm
    height_cm = record.artwork_height_cm
    
    # 用修复后的算法重新计算
    try:
        v4_result = classify_inscription_v4(text, year, title, analysis_note, width_cm, height_cm)
    except Exception as e:
        return False, f"classify_inscription_v4失败: {e}"
    
    # 更新sentiment和相关部分
    ca['sentiment'] = v4_result['sentiment']
    ca['themes'] = v4_result['themes']
    
    # 更新feature_words中的信号
    if 'feature_words' not in ca:
        ca['feature_words'] = {}
    ca['feature_words']['v4_signals'] = v4_result['signals']
    ca['feature_words']['v4_special_rules'] = v4_result['special_rules']
    
    # 重新计算自动标签
    try:
        # 构建record字典给compute_tags
        record_dict = {
            "period_phase": record.period_phase,
            "artwork_height_cm": height_cm,
            "artwork_width_cm": width_cm,
            "content_analysis": ca,
            "material_tags": record.material_tags,
            "title": title,
        }
        auto_tags = compute_tags(record_dict)
    except Exception as e:
        auto_tags = []
        print(f"    计算标签失败: {e}")
    
    new_polarity = v4_result['sentiment']['polarity']
    changed = old_polarity != new_polarity
    
    if dry_run:
        return True, f"DRY RUN: {image_id} - {old_polarity} -> {new_polarity} {'(CHANGED!)' if changed else ''}"
    
    # 更新数据库
    try:
        record.content_analysis = json.dumps(ca, ensure_ascii=False)
        if auto_tags:
            # 合并自动标签和现有标签
            existing_tags = []
            if record.tags:
                try:
                    existing_tags = json.loads(record.tags) if isinstance(record.tags, str) else record.tags
                except:
                    existing_tags = []
            # 合并，去重
            merged_tags = list(set(existing_tags + auto_tags))
            record.tags = json.dumps(merged_tags, ensure_ascii=False)
        
        return True, f"OK: {image_id} - {old_polarity} -> {new_polarity} {'(CHANGED!)' if changed else ''}"
    except Exception as e:
        return False, f"更新数据库失败: {e}"


def main():
    parser = argparse.ArgumentParser(description="重新计算情感分析")
    parser.add_argument("--dry-run", action="store_true", help="仅预览变化，不更新数据库")
    parser.add_argument("--limit", type=int, default=None, help="限制处理数量")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        # 查询所有有content_analysis的记录
        query = db.query(TubiAnalysis).filter(TubiAnalysis.content_analysis != None)
        if args.limit:
            query = query.limit(args.limit)
        records = query.all()
        
        print(f"找到 {len(records)} 条记录")
        print("-" * 80)
        
        success_count = 0
        fail_count = 0
        changed_count = 0
        
        for i, record in enumerate(records):
            print(f"[{i+1}/{len(records)}] 处理 {record.image_id}...")
            
            # 实际处理
            ok, msg = recompute_one(record, dry_run=args.dry_run)
            if ok:
                success_count += 1
                print(f"  {msg}")
                if "CHANGED!" in msg:
                    changed_count += 1
            else:
                fail_count += 1
                print(f"  失败: {msg}")
            
            if (i + 1) % 10 == 0 and not args.dry_run:
                db.commit()
                print(f"  已提交 {i+1} 条")
        
        if not args.dry_run:
            db.commit()
            print("最终提交完成")
        
        print("-" * 80)
        print(f"总计: {len(records)} 条")
        print(f"成功: {success_count} 条")
        print(f"失败: {fail_count} 条")
        print(f"情感变化: {changed_count} 条")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
