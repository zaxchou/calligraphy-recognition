import sqlite3, json
DB = 'Z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/knowledge.db'
db = sqlite3.connect(DB)

cur = db.execute("SELECT id, substr(content,1,80), associated_images FROM text_chunks WHERE content LIKE ?", ('%如图一山水画%',))
for r in cur.fetchall():
    assoc = json.loads(r[2]) if isinstance(r[2], str) else (r[2] or [])
    print('Chunk:', r[0][:20], 'assoc_count:', len(assoc))
    for a in assoc[:5]:
        # Check image
        img = db.execute("SELECT file_name, page FROM extracted_images WHERE id = ?", (a,)).fetchone()
        print('  img:', a[:20], img)

print()

# What's chunk associated_images for page 14?
cur2 = db.execute("SELECT id, file_name, page FROM extracted_images WHERE book_id = ? ORDER BY page", ('eeb30146-cb9a-43a1-b05b-8747756c9046',))
for r in cur2.fetchall():
    print('img:', r[0][:20], r[1], 'p.', r[2])

print()
print('Image 6f31b5b6:')
cur3 = db.execute("SELECT id, file_name, page, stored_url FROM extracted_images WHERE id LIKE ?", ('6f31b5b6%',))
for r in cur3.fetchall():
    print(r)

db.close()
