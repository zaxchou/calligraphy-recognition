#!/usr/bin/env python3
"""Investigate extreme lexicon scores in the latest batch"""
import sys, json
sys.path.insert(0, r"Z:\molin-wiki\backend")
from app.core.database import get_db_connection

conn = get_db_connection()
conn.row_factory = __import__('sqlite3').Row
cur = conn.cursor()

for rid in [205, 210, 113, 275, 154, 121]:
    cur.execute('SELECT id, title, inscription_content, content_analysis FROM tubi_analyses WHERE id = ?', (rid,))
    row = cur.fetchone()
    if not row: continue
    ca = {}
    if row['content_analysis']:
        try: ca = json.loads(row['content_analysis'])
        except: pass

    # Get current lexicon signals from combined_sentiment
    cs = ca.get('combined_sentiment', {})
    dd = cs.get('dimension_details', {})
    signals = dd.get('text', {}).get('signals', [])

    text = row['inscription_content'] or ''
    print(f'=== ID={rid} | {row["title"]} ===')
    print(f'题跋: {text[:200]}')
    print(f'SIGNALS ({len(signals)}):')
    # Group by method
    multi = [s for s in signals if s.get('method') == 'multi_word']
    single = [s for s in signals if s.get('method') in ('single_char', 'matched')]
    if multi:
        total_m = sum(s.get('score',0) or 0 for s in multi)
        print(f'  MULTI-WORD ({len(multi)} items, total={total_m:+.0f}):')
        for s in multi[:15]:
            neg = ' (negated)' if s.get('negated') else ''
            print(f'    {s["word"]}: {s["score"]:+d}{neg}')
    if single:
        total_s = sum(s.get('score',0) or 0 for s in single)
        print(f'  SINGLE-CHAR ({len(single)} items, total={total_s:+.0f}):')
        for s in single[:20]:
            neg = ' (negated)' if s.get('negated') else ''
            print(f'    {s["word"]}: {s["score"]:+d}{neg}')

    # LLM info
    lj = ca.get('llm_judge') or {}
    if isinstance(lj, dict):
        jd = lj.get('dimension_scores', {})
        jc = lj.get('combined', {})
        print(f'  LLM text_raw={jd.get("text",{}).get("raw","?")} polarity={jc.get("polarity","?")}')
    print()
conn.close()
