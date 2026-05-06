import sqlite3, json, re

conn = sqlite3.connect('/opt/calligraphy-recognition/backend/data/calligraphy.db')
c = conn.cursor()

# Search for 应酬送人 or 雅交 in content_analysis or theme_tags
c.execute("""
    SELECT image_id, title, artist, theme_tags, content_analysis
    FROM tubi_analyses
    WHERE content_analysis LIKE '%应酬送人%'
       OR content_analysis LIKE '%雅交%'
       OR theme_tags LIKE '%应酬%'
       OR theme_tags LIKE '%雅交%'
    LIMIT 20
""")
rows = c.fetchall()
print(f"Found {len(rows)} records with old tags")

for r in rows:
    image_id = r[0]
    title = r[1]
    artist = r[2]
    ca_str = r[4] or ''

    # Try to parse content_analysis JSON
    try:
        ca = json.loads(ca_str)
        themes = ca.get('themes', [])
        sentiment = ca.get('sentiment', {})
        print(f"\n{image_id}: {title} ({artist})")
        for t in themes:
            print(f"  theme: code={t.get('code')} name={t.get('name')} confidence={t.get('confidence')}")
    except:
        # If not JSON, show raw
        matches = re.findall(r'应酬送人|雅交|闲居遣兴|感时言志|酬唱赠答', ca_str or '')
        if matches:
            print(f"\n{image_id}: {title} ({artist})")
            print(f"  raw matched: {matches}")
            print(f"  ca preview: {ca_str[:200]}")

# Also check: how many records have confidence < 0.5 in themes?
c.execute("""
    SELECT COUNT(*) FROM tubi_analyses
    WHERE content_analysis IS NOT NULL
    AND content_analysis != ''
""")
total_with_ca = c.fetchone()[0]
print(f"\n\nTotal records with content_analysis: {total_with_ca}")

conn.close()
