import sqlite3, requests, json, os

DB = 'Z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/knowledge.db'
db = sqlite3.connect(DB)

# Find books
cur = db.execute("SELECT id, title, status FROM pdf_books ORDER BY created_at")
books = cur.fetchall()
for b in books:
    print('Book: %s %s %s' % (b[0][:12], b[2], b[1][:40]))

# Get 构图问题 book id (潘天寿)
cur2 = db.execute("SELECT id, title FROM pdf_books WHERE title LIKE ?", ('%构图%',))
goutu = cur2.fetchone()
print()

if goutu:
    bid = goutu[0]
    print('构图 book:', bid, goutu[1])
    
    # Check images
    imgs = db.execute("SELECT id[:20], stored_url, file_name FROM extracted_images WHERE book_id = ? LIMIT 5", (bid,)).fetchall()
    print('Sample images:')
    for im in imgs:
        url = im[1]
        print('  id:', im[0], 'file:', im[2])
        print('  stored_url:', url)
        # Check if file exists on disk
        base = r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\knowledge\books\images'
        path = os.path.join(base, bid, im[2])
        print('  on_disk:', os.path.exists(path))

# Compare with 写意花鸟
cur3 = db.execute("SELECT id, title FROM pdf_books WHERE title LIKE ?", ('%写意花鸟%',))
huanniao = cur3.fetchone()
if huanniao:
    bid2 = huanniao[0]
    print()
    print('写意花鸟 book:', bid2, huanniao[1])
    imgs2 = db.execute("SELECT id[:20], stored_url, file_name FROM extracted_images WHERE book_id = ? LIMIT 3", (bid2,)).fetchall()
    for im in imgs2:
        print('  stored_url:', im[1][:100])

# Search test
print()
r = requests.post('http://localhost:8001/api/v1/knowledge/search',
    json={'query': '起承转合', 'limit': 5}, timeout=15)
d = r.json()
for i, res in enumerate(d.get('results', [])):
    book_title = res.get('book_title','')
    print('result[%d] book=%s' % (i, book_title[:40]))
    assoc = res.get('associated_images', [])
    if assoc:
        print('  img url:', assoc[0].get('url','')[:100])
        print('  img stored_url:', assoc[0].get('stored_url','')[:100])
    else:
        print('  NO associated_images')

db.close()
