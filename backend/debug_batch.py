import requests
import json

# First, let's check the settings/config to see if QWEN_API_KEY is configured
url = "http://localhost:8001/api/v1/content-analysis/stats?artist=李鱓"
resp = requests.get(url)
print(f"Stats API status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Total count from API: {data.get('total_count')}")
    sentiment_dist = data.get('sentiment_distribution', [])
    print(f"Sentiment distribution: {json.dumps(sentiment_dist, ensure_ascii=False)}")

# Now test single record analysis to see what the dual channel returns
print("\n" + "="*60)
print("Testing single record dual-channel analysis")
print("="*60)

# Get first record content
import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("""
    SELECT id, inscription_content FROM tubi_analyses
    WHERE artist LIKE '%李鱓%' AND inscription_content IS NOT NULL
    LIMIT 1
""")
row = cur.fetchone()
conn.close()

if row:
    record_id, content = row
    print(f"Record ID: {record_id}")
    print(f"Content: {content[:100]}...")

# Check if we can call the batch API with use_llm=true and see the actual response
import time
url = "http://localhost:8001/api/v1/content-analysis/batch"
params = {
    "artist": "李鱓",
    "force_reanalyze": "true",
    "use_llm": "true"
}
print(f"\nCalling batch API with: {params}")
start = time.time()
resp = requests.post(url, params=params, timeout=120)
elapsed = time.time() - start
print(f"Response: {resp.text[:500]}")
print(f"Time: {elapsed:.1f}s")

# Now check the updated content_analysis for record 1
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("SELECT id, title, content_analysis FROM tubi_analyses WHERE id = 1")
row = cur.fetchone()
if row:
    analysis = json.loads(row[2])
    print(f"\nRecord 1 sentiment structure:")
    print(json.dumps(analysis.get('sentiment', {}), indent=2, ensure_ascii=False))
conn.close()