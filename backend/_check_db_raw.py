"""直接查DB的thumbnail_path和filepath字段 for new records"""
import sqlite3

DB = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("PRAGMA table_info(tubi_analyses)")
cols = [r[1] for r in cur.fetchall()]
print("Columns:", cols)

cur.execute("""
    SELECT id, title, filepath, thumbnail_path, annotated_image_path, image_id, status
    FROM tubi_analyses
    WHERE id BETWEEN 57 AND 67
    ORDER BY id
""")
print("\nid | filepath | thumbnail_path | image_id | status")
for r in cur.fetchall():
    print(f"{r[0]:3d} | {r[2][:25] if r[2] else 'None'} | {r[3][:35] if r[3] else 'None'} | {r[5][:20] if r[5] else 'None'} | {r[6]}")

conn.close()