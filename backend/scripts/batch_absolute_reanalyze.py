import sqlite3, json, asyncio, re, math, sys
sys.stdout.reconfigure(line_buffering=True)
from app.services.qwen_llm_client import call_qwen_chat_async

SYSTEM_PROMPT = """你是一位中国古代书画研究者。请根据给出的事实性信息，独立判断题跋的情感。

对以下7个维度分别给出分数（-8到+8）和简短理由：text（文字情感）、period（时期心境）、theme（主题情感）、painting（画材情感）、spatial（空间情感）、seal（印章情感）、size（尺寸情感）。

评分参考：-8~-5强烈消极 | -5~-2明显消极 | -2~+2中性 | +2~+5明显积极 | +5~+8强烈积极

summary字段必须用以下三段式结构（每段至少50字）：
正面：找出题跋中所有积极的信号
负面：找出题跋中所有消极的信号
综合：给出整体判断

输出严格JSON，不要markdown包裹：
{"scores":{"text":{"score":0,"reasoning":"..."},"period":{"score":0,"reasoning":"..."},"theme":{"score":0,"reasoning":"..."},"painting":{"score":0,"reasoning":"..."},"spatial":{"score":0,"reasoning":"..."},"seal":{"score":0,"reasoning":"..."},"size":{"score":0,"reasoning":"..."}},"polarity":"neutral","summary":"正面：...\\n负面：...\\n综合：...","reasoning":"..."}"""


async def analyze_one(text, year, period, seal, themes):
    theme_str = ', '.join(t.get('name', '') for t in (themes or [])[:3])
    year_str = '%d年（画家 %d 岁）' % (year, year - 1686) if year else '年代不详'
    period_str = period if period else '未分期'
    prompt = '画家：李鱓（1686-1762）\n创作年份：%s\n时期：%s\n主题：%s\n\n题跋全文：\n%s\n\n印章：%s' % (year_str, period_str, theme_str or '未分类', text, seal or '无')

    resp = await call_qwen_chat_async(
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ],
        temperature=0.1,
        max_tokens=800,
    )
    content = resp.get('choices', [{}])[0].get('message', {}).get('content', '')
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        return json.loads(json_match.group())
    return None


conn = sqlite3.connect('/app/data/calligraphy.db')
conn.row_factory = sqlite3.Row

rows = conn.execute('''
    SELECT id, title, year, period_phase, inscription_content, seal_content, content_analysis
    FROM tubi_analyses
    WHERE artist = '李鱓' AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 2
      AND (content_analysis IS NULL OR json_extract(content_analysis, '$.analysis_method') != 'llm_independent')
    ORDER BY year
''').fetchall()

total = len(rows)
print('To reprocess: %d works (skipping already done)' % total, flush=True)

updated = 0
errors = 0

for i, row in enumerate(rows):
    rid = row['id']
    old_ca = json.loads(row['content_analysis']) if row['content_analysis'] else {}
    themes = old_ca.get('themes', [])

    try:
        result = asyncio.run(analyze_one(
            row['inscription_content'] or '',
            row['year'],
            row['period_phase'] or '',
            row['seal_content'] or '',
            themes,
        ))
        if result and 'scores' in result:
            scores_raw = result['scores']
            # 支持 {score, reasoning} 字典格式和纯数字格式
            def get_score(v):
                return v.get('score', 0) if isinstance(v, dict) else (v or 0)
            def get_reasoning(v):
                return v.get('reasoning', '') if isinstance(v, dict) else ''
            scores = {k: get_score(v) for k, v in scores_raw.items()}
            combined_raw = sum(scores.values()) / len(scores) if scores else 0
            vader_norm = combined_raw / math.sqrt(combined_raw ** 2 + 8.0) if combined_raw else 0

            # combined_sentiment：最终分数（引擎读这个）
            old_cs = old_ca.get('combined_sentiment', {})
            new_cs = {
                'polarity': result.get('polarity', 'neutral'),
                'reasoning': result.get('reasoning', ''),
                'summary': result.get('summary', ''),
                'text_score': round(scores.get('text', 0), 2),
                'time_score': round(scores.get('period', 0), 2),
                'painting_score': round(scores.get('painting', 0), 2),
                'theme_score': round(scores.get('theme', 0), 2),
                'seal_score': round(scores.get('seal', 0), 2),
                'spatial_score': round(scores.get('spatial', 0), 2),
                'size_score': round(scores.get('size', 0), 2),
                'combined_score': round(combined_raw, 2),
                'vader_normalized': round(vader_norm, 3),
                'method': 'llm_independent',
                # 保留旧格式的引擎元数据
                'dimension_details': old_cs.get('dimension_details', {}),
                'dimension_polarities': old_cs.get('dimension_polarities', {}),
                'conflict_score': old_cs.get('conflict_score', 0),
                'has_data': old_cs.get('has_data', {}),
                'weights': old_cs.get('weights', {}),
                'vader_alpha': old_cs.get('vader_alpha', 8.0),
                'brush_ink_score': old_cs.get('brush_ink_score', 0),
            }

            # llm_analysis：前端详情页读这个
            corrections = {}
            for dim in ['text', 'spatial', 'painting', 'size', 'period', 'seal', 'theme', 'brush_ink']:
                entry = scores_raw.get(dim, {})
                corrections[dim] = {
                    'delta': 0,
                    'confidence': 0.8 if dim != 'brush_ink' else 0,
                    'reasoning': get_reasoning(entry),
                }

            old_ca['combined_sentiment'] = new_cs
            old_ca['llm_analysis'] = {
                'dimension_scores': {},
                'corrections': corrections,
                'combined': {
                    'polarity': result.get('polarity', 'neutral'),
                    'summary': result.get('summary', ''),
                    'reasoning': result.get('reasoning', ''),
                },
                'meta': {'model': 'deepseek-v4-flash', 'method': 'llm_independent'},
            }
            old_ca['analysis_method'] = 'llm_independent'
            conn.execute('UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?',
                         (json.dumps(old_ca, ensure_ascii=False), rid))
            updated += 1

            if updated % 20 == 0:
                conn.commit()
                print('Progress: %d/%d' % (updated, total), flush=True)
        else:
            errors += 1
            print('Parse error ID=%d' % rid, flush=True)
    except Exception as e:
        errors += 1
        print('Error ID=%d: %s' % (rid, str(e)[:60]), flush=True)

conn.commit()
conn.close()
print('Done: %d updated, %d errors' % (updated, errors), flush=True)
