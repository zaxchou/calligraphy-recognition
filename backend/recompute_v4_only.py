
"""
纯v4规则重新计算情感 - 不调用LLM
直接用我修复后的 classify_inscription_v4 函数
"""
import sys
import os
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.inscription_content_analyzer import classify_inscription_v4

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# 查询所有有题跋的记录
cur.execute("""
    SELECT id, image_id, inscription_content, year, title, analysis_note,
           artwork_width_cm, artwork_height_cm, content_analysis
    FROM tubi_analyses
    WHERE inscription_content IS NOT NULL
      AND LENGTH(inscription_content) > 0
""")
rows = cur.fetchall()

print(f'找到 {len(rows)} 条记录\n')

updated = 0
satire_before = 0
satire_after = 0
sentiment_before = {'positive': 0, 'negative': 0, 'neutral': 0}
sentiment_after = {'positive': 0, 'negative': 0, 'neutral': 0}

for record_id, image_id, content, year, title, analysis_note, width_cm, height_cm, old_ca in rows:
    try:
        # 解析旧数据
        old_data = json.loads(old_ca) if old_ca else {}
        
        # 统计旧数据
        old_themes = old_data.get('themes', [])
        old_sentiment = old_data.get('sentiment', {}).get('polarity', 'neutral')
        if old_themes and old_themes[0].get('name') == '讽喻社会与民生':
            satire_before += 1
        sentiment_before[old_sentiment] = sentiment_before.get(old_sentiment, 0) + 1
        
        # 用修复后的v4规则重新计算
        v4_result = classify_inscription_v4(
            content.strip(), 
            year=year, 
            title=title, 
            analysis_note=analysis_note,
            width_cm=width_cm, 
            height_cm=height_cm
        )
        
        # 更新数据（只更新sentiment和themes，保留其他字段）
        old_data['themes'] = v4_result['themes']
        old_data['sentiment'] = v4_result['sentiment']
        old_data['feature_words'] = old_data.get('feature_words', {})
        old_data['feature_words']['v4_signals'] = v4_result['signals']
        old_data['feature_words']['v4_special_rules'] = v4_result['special_rules']
        
        # 统计新数据
        new_themes = v4_result['themes']
        new_sentiment = v4_result['sentiment']['polarity']
        if new_themes and new_themes[0].get('name') == '讽喻社会与民生':
            satire_after += 1
        sentiment_after[new_sentiment] = sentiment_after.get(new_sentiment, 0) + 1
        
        # 保存到数据库
        cur.execute("""
            UPDATE tubi_analyses
            SET content_analysis = ?, updated_at = ?
            WHERE id = ?
        """, (json.dumps(old_data, ensure_ascii=False), datetime.now(), record_id))
        
        updated += 1
        if updated % 20 == 0:
            print(f'已处理 {updated}/{len(rows)} 条...')
            
    except Exception as e:
        print(f'Error {image_id}: {e}')
        import traceback
        traceback.print_exc()
        continue

conn.commit()
conn.close()

print(f'\n=== 完成！共更新 {updated} 条记录 ===\n')
print('旧数据统计:')
print(f'  讽喻社会作品数: {satire_before}')
print(f'  情感分布: {sentiment_before}')
print('\n新数据统计:')
print(f'  讽喻社会作品数: {satire_after}')
print(f'  情感分布: {sentiment_after}')
