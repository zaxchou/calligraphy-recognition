#!/usr/bin/env python3
"""批量回填 material_tags 字段"""
import sqlite3
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.inscription_content_analyzer import extract_material_tags

DB_PATH = "data/calligraphy.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 查询所有有 title 或 analysis_note 的记录
    cursor.execute("""
        SELECT id, title, analysis_note 
        FROM tubi_analyses 
        WHERE (title IS NOT NULL AND title != '') 
           OR (analysis_note IS NOT NULL AND analysis_note != '')
    """)
    
    rows = cursor.fetchall()
    print(f"找到 {len(rows)} 条需要处理的记录")
    
    updated = 0
    for row in rows:
        record_id = row['id']
        title = row['title'] or ''
        analysis_note = row['analysis_note'] or ''
        
        # 提取画材标签
        tags = extract_material_tags(title, analysis_note)
        
        if tags:
            tags_str = ','.join(tags)
            cursor.execute(
                "UPDATE tubi_analyses SET material_tags = ? WHERE id = ?",
                (tags_str, record_id)
            )
            updated += 1
            print(f"  ID={record_id}: {tags_str}")
    
    conn.commit()
    print(f"\n完成：更新了 {updated} 条记录")
    
    # 统计标签分布
    cursor.execute("SELECT material_tags FROM tubi_analyses WHERE material_tags IS NOT NULL AND material_tags != ''")
    all_tags = []
    for row in cursor.fetchall():
        all_tags.extend(row['material_tags'].split(','))
    
    from collections import Counter
    tag_counts = Counter(all_tags)
    print(f"\n标签分布（共 {len(tag_counts)} 种标签）：")
    for tag, count in tag_counts.most_common(20):
        print(f"  {tag}: {count}次")
    
    conn.close()

if __name__ == "__main__":
    main()