import sqlite3, json

import os
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend/data/calligraphy.db")
if not os.path.exists(db_path):
    # Running on server
    db_path = "/opt/calligraphy-recognition/backend/data/calligraphy.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Find the old record
c.execute("SELECT image_id, content_analysis FROM tubi_analyses WHERE image_id='0f58e831-1104-47c9-8bc5-7e5f6536ce1a'")
row = c.fetchone()
if not row:
    print("Record not found")
    exit()

print(f"Found: {row[0]}")
ca = json.loads(row[1])

# Update old theme names to new ones
name_map = {
    "应酬送人与雅交": "交游赠答",
    "世俗祈愿与谐趣": "吉语祥瑞",
    "记录创作信息": "身世自况",
}

for t in ca.get("themes", []):
    old_name = t.get("name", "")
    if old_name in name_map:
        t["name"] = name_map[old_name]
        print(f"  Updated: '{old_name}' -> '{name_map[old_name]}'")

# Update the database
updated = json.dumps(ca, ensure_ascii=False)
c.execute("UPDATE tubi_analyses SET content_analysis=? WHERE image_id=?", (updated, row[0]))
conn.commit()

print(f"\nAfter: {json.dumps(ca, ensure_ascii=False, indent=2)}")
print("\nDone")
conn.close()
