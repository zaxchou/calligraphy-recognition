"""查看API返回的id和DB integer id的对应关系"""
import sqlite3, urllib.request, json

DB = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# 查 id=57-67 记录的 uuid
cur.execute("SELECT id, uuid, title, thumbnail_path FROM tubi_analyses WHERE id BETWEEN 57 AND 67")
print("=== DB记录 (id=57-67) ===")
for r in cur.fetchall():
    print(f"  int_id={r[0]} uuid={r[1]} title={r[2][:15]} thumb={r[3]}")

conn.close()

# 查API返回的skip=38的11条
url = "http://localhost:8001/api/v1/tubi/results?skip=38&limit=20"
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.load(resp)

print(f"\n=== API skip=38 返回 {len(data['data'])} 条 ===")
for item in data['data'][:12]:
    print(f"  api_id={item['id']} title={item.get('title','N/A')[:15]} thumb_url={item.get('thumbnail_url','MISSING')}")

conn = sqlite3.connect(DB)
cur = conn.cursor()
# 查这批记录的uuid
uuids = [item['id'] for item in data['data'][:12]]
placeholders = ','.join(['?' for _ in uuids])
cur.execute(f"SELECT id, uuid, title FROM tubi_analyses WHERE uuid IN ({placeholders})", uuids)
print(f"\n=== DB中这些UUID对应的int_id ===")
for r in cur.fetchall():
    print(f"  int_id={r[0]} uuid={r[1]} title={r[2][:15]}")
conn.close()