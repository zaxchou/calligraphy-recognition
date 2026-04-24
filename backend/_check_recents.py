"""检查API返回的UUID对应哪些DB记录"""
import sqlite3, urllib.request, json

DB = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# 查所有记录的 id, filename, created_at
cur.execute("SELECT id, filename, title, thumbnail_path, created_at FROM tubi_analyses ORDER BY created_at DESC LIMIT 20")
rows = cur.fetchall()
print("=== 最近20条记录 (按created_at倒序) ===")
for r in rows:
    print(f"  int_id={r[0]:3d} filename={r[1][:30] if r[1] else 'None'} title={r[2][:12] if r[2] else 'None'} thumb={r[3]}")
conn.close()

# 同时调API看前11条的UUID
url = "http://localhost:8001/api/v1/tubi/results?skip=0&limit=11"
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.load(resp)
print(f"\n=== API 前11条 (skip=0) ===")
for item in data['data'][:11]:
    print(f"  uuid={item['id']} title={item.get('title','N/A')[:12]} thumb={item.get('thumbnail_url','MISSING')}")