import sqlite3, json, sys

# Fix Windows console encoding issue
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r'z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

for img_id in ['7ee7d955-0588-4f93-a1de-f430e3cb35e5', '84a454dd-7b6f-48f0-ba27-6332d40874dc']:
    cur.execute('SELECT id, title, analysis_note, content_analysis, inscription_content FROM tubi_analyses WHERE image_id = ?', (img_id,))
    r = cur.fetchone()
    if r:
        print(f'=== ID: {r["id"]} ===')
        print(f'title: {r["title"]}')
        # Safely print analysis_note
        an = (r['analysis_note'] or '')[:300]
        print(f'analysis_note: {an}')
        # Check if inscription_content contains keywords
        ic = (r['inscription_content'] or '')[:200]
        print(f'inscription_content: {ic}')
        if r['content_analysis']:
            ca = json.loads(r['content_analysis']) if isinstance(r['content_analysis'], str) else r['content_analysis']
            signals = ca.get('signals', {})
            painting = signals.get('painting', 'MISSING')
            print(f'signals.painting: {painting}')
            sentiment = ca.get('sentiment', {})
            print(f'sentiment: {sentiment}')
        print()
    else:
        print(f'Not found: {img_id}')

conn.close()
print('done')
