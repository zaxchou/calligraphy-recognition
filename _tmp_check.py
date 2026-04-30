import sqlite3
db = sqlite3.connect('backend/data/knowledge.db')
rows = db.execute("SELECT id, title, file_name FROM pdf_books").fetchall()
for r in rows:
    bid = r[0][:8] if r[0] else '?'
    name = r[1] or r[2] or '?'
    print(f"{bid}.. | {name}")
db.close()
