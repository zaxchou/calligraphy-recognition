import sqlite3, json, re, math, sys, time
sys.stdout.reconfigure(line_buffering=True)
from app.services.qwen_llm_client import call_qwen_chat

SYSTEM_PROMPT = """你是一位中国古代书画研究者。请根据给出的事实性信息，独立判断题跋的情感。

对以下7个维度分别给出分数（-8到+8）和简短理由：text（文字情感）、period（时期心境）、theme（主题情感）、painting（画材情感）、spatial（空间情感）、seal（印章情感）、size（尺寸情感）。

评分参考：-8~-5强烈消极 | -5~-2明显消极 | -2~+2中性 | +2~+5明显积极 | +5~+8强烈积极

summary字段必须严格按以下三段式结构。引用题跋原文词句为证，结合画家生平、创作年代、画幅尺寸等元数据进行深度解读：
积极面：80-120字。提取正向情绪、自我肯定、坚持、美感、生命意志等。引用原文词句，说明其积极含义。
消极面：80-120字。指出孤独、被拒、命运不顺、苦涩、自嘲、幻灭等。引用原文词句，说明其消极含义。
综合判断：120-200字。给出总体定性（如：偏积极/偏消极/悲凉中的倔强/热烈下的虚无等），说明两面如何共存，结合画家此时期的心境、人生阶段、艺术风格做整体评价。这一段应当是最有深度的总结。

输出严格JSON，不要markdown包裹：
{"scores":{"text":{"score":0,"reasoning":"..."},...},"polarity":"neutral","summary":"积极面：（80-120字）...\\n消极面：（80-120字）...\\n综合判断：（120-200字，最有深度的总结）...","reasoning":"..."}"""


def analyze_one(text, year, period, seal, themes, size_info=None):
    theme_str = ', '.join(t.get('name', '') for t in (themes or [])[:3])
    year_str = '%d年（画家 %d 岁）' % (year, year - 1686) if year else '年代不详'
    period_str = period if period else '未分期'
    prompt = '画家：李鱓（1686-1762）\n创作年份：%s\n时期：%s\n主题：%s\n\n题跋全文：\n%s\n\n印章：%s' % (year_str, period_str, theme_str or '未分类', text, seal or '无')
    if size_info:
        prompt += '\n\n画幅尺寸：%s' % size_info

    resp = call_qwen_chat(
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ],
        temperature=0.1,
        max_tokens=2000,
    )
    if 'error' in resp:
        return None, resp['error']
    content = resp.get('choices', [{}])[0].get('message', {}).get('content', '')
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            return json.loads(json_match.group()), None
        except json.JSONDecodeError as e:
            return None, 'JSON parse error: %s' % str(e)[:50]
    return None, 'No JSON in response (len=%d)' % len(content)


conn = sqlite3.connect('data/calligraphy.db')
conn.row_factory = sqlite3.Row

rows = conn.execute('''
    SELECT id, title, year, period_phase, inscription_content, seal_content, content_analysis,
           artwork_width_cm, artwork_height_cm
    FROM tubi_analyses
    WHERE artist = '李鱓' AND inscription_content IS NOT NULL AND LENGTH(inscription_content) >= 1
      AND id != 28
    ORDER BY year
''').fetchall()

total = len(rows)
print('=== Batch reanalyze: %d works ===' % total, flush=True)

updated = 0
errors = 0
start_time = time.time()

for i, row in enumerate(rows):
    rid = row['id']
    old_ca = json.loads(row['content_analysis']) if row['content_analysis'] else {}
    themes = old_ca.get('themes', [])

    # 构建尺寸信息
    w = row['artwork_width_cm']
    h = row['artwork_height_cm']
    size_str = '%gcm × %gcm' % (h, w) if h and w else None

    t0 = time.time()
    print('[%d/%d] ID=%d "%s" ...' % (i+1, total, rid, (row['title'] or '')[:20]), end=' ', flush=True)

    try:
        result, err = analyze_one(
            row['inscription_content'] or '',
            row['year'],
            row['period_phase'] or '',
            row['seal_content'] or '',
            themes,
            size_info=size_str,
        )
        elapsed = time.time() - t0

        if result and 'scores' in result:
            scores_raw = result['scores']
            def get_score(v):
                return v.get('score', 0) if isinstance(v, dict) else (v or 0)
            def get_reasoning(v):
                return v.get('reasoning', '') if isinstance(v, dict) else ''
            scores = {k: get_score(v) for k, v in scores_raw.items()}

            # 加权平均
            weights = old_ca.get('combined_sentiment', {}).get('weights', {})
            default_w = {'text':0.40,'spatial':0.20,'painting':0.10,'size':0.05,'period':0.10,'seal':0.10,'theme':0.05,'brush_ink':0.0}
            dim_conf = old_ca.get('combined_sentiment', {}).get('dimension_confidence', {
                'text':1.0,'spatial':0.8,'painting':0.8,'size':0.8,
                'period':0.8,'seal':0.8,'theme':0.8,'brush_ink':0.0
            })
            weighted_sum = 0.0
            weight_total = 0.0
            for dim_key in ['text','spatial','painting','size','period','seal','theme','brush_ink']:
                ww = weights.get(dim_key, default_w.get(dim_key, 0))
                conf = dim_conf.get(dim_key, 0.8)
                s = scores.get(dim_key, 0)
                weighted_sum += ww * conf * s
                weight_total += ww * conf
            combined_raw = weighted_sum / weight_total if weight_total > 0 else 0
            vader_norm = combined_raw / math.sqrt(combined_raw ** 2 + 8.0) if combined_raw else 0

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
                'dimension_details': old_cs.get('dimension_details', {}),
                'dimension_polarities': old_cs.get('dimension_polarities', {}),
                'conflict_score': old_cs.get('conflict_score', 0),
                'has_data': old_cs.get('has_data', {}),
                'dimension_confidence': old_cs.get('dimension_confidence', {
                    'text':1.0,'spatial':0.8,'painting':0.8,'size':0.8,
                    'period':0.8,'seal':0.8,'theme':0.8,'brush_ink':0.0
                }),
                'weights': old_cs.get('weights', {}),
                'vader_alpha': old_cs.get('vader_alpha', 8.0),
                'brush_ink_score': old_cs.get('brush_ink_score', 0),
            }

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
            conn.commit()
            updated += 1
            print('OK %.1fs (vn=%.3f)' % (elapsed, vader_norm), flush=True)
        else:
            errors += 1
            print('FAIL %.1fs: %s' % (elapsed, err or 'parse error'), flush=True)
    except Exception as e:
        errors += 1
        print('ERROR: %s' % str(e)[:80], flush=True)

    # 每 50 条打印进度
    if (i + 1) % 50 == 0:
        total_elapsed = time.time() - start_time
        avg = total_elapsed / (i + 1)
        remaining = avg * (total - i - 1)
        print('--- Progress: %d/%d done, %d errors, %.0fs elapsed, ~%.0fs remaining ---' %
              (updated, total, errors, total_elapsed, remaining), flush=True)

conn.close()
total_elapsed = time.time() - start_time
print('=== Done: %d updated, %d errors, %.0fs total ===' % (updated, errors, total_elapsed), flush=True)
