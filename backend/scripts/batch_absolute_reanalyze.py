import sqlite3, json, asyncio, re, math, sys
sys.stdout.reconfigure(line_buffering=True)
from app.services.qwen_llm_client import call_qwen_chat_async

SYSTEM_PROMPT = """你是一位中国古代书画研究者。请根据给出的事实性信息，独立判断题跋的情感。

## 评分维度（-8 到 +8，独立打分）

1. text — 题跋文字本身表达的情绪
2. period — 基于画家年龄，此画创作时可能的心境
3. theme — 题题本身的情感倾向
4. painting — 画材/题材的情感含义
5. spatial — 题跋布局传达的情绪
6. seal — 印章文字的情感
7. size — 画幅暗示的创作心态

评分参考：
- -8 ~ -5：强烈消极
- -5 ~ -2：明显消极
- -2 ~ +2：中性或复杂
- +2 ~ +5：明显积极
- +5 ~ +8：强烈积极

## 综合分析（至少 150 字）

像书画鉴赏家一样解读：
1. 表层——题跋在说什么
2. 深层——真正在表达什么情绪
3. 有没有矛盾的信号
4. 整体情感倾向

输出严格 JSON：
{
  "scores": {"text": <float>, "period": <float>, "theme": <float>, "painting": <float>, "spatial": <float>, "seal": <float>, "size": <float>},
  "polarity": "positive|negative|neutral|complex",
  "summary": "<150字以上的鉴赏分析>",
  "reasoning": "<50字判断依据>"
}"""


async def analyze_one(text, year, period, seal, themes):
    theme_str = ', '.join(t.get('name', '') for t in (themes or [])[:3])
    year_str = '%d年（画家 %d 岁）' % (year, year - 1686) if year else '年代不详'
    period_str = period if period else '未分期'
    prompt = 'Artist: Li Shan (1686-1762)\nYear: %s\nPeriod: %s\nThemes: %s\n\nInscription:\n%s\n\nSeals: %s' % (year_str, period_str, theme_str or 'none', text, seal or 'none')

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
            scores = {k: get_score(v) for k, v in scores_raw.items()}
            combined_raw = sum(scores.values()) / len(scores) if scores else 0
            vader_norm = combined_raw / math.sqrt(combined_raw ** 2 + 8.0) if combined_raw else 0

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
            }

            old_ca['combined_sentiment'] = new_cs
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
