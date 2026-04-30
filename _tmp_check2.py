import sqlite3, os

db = sqlite3.connect('backend/data/knowledge.db')
active_ids = set(r[0] for r in db.execute("SELECT id FROM pdf_books").fetchall())
db.close()

img_dir = 'backend/data/knowledge/books/images'
if os.path.isdir(img_dir):
    for d in os.listdir(img_dir):
        path = os.path.join(img_dir, d)
        if os.path.isdir(path):
            fcount = sum(1 for _ in os.scandir(path) if _.is_file())
            fsize = sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)))
            status = "active" if d in active_ids else "ORPHANED"
            print(f"  {d[:8]}.. [{status}] {fsize/1024/1024:.1f} MB, {fcount} files")
