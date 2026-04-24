import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Find the tubi table
for t in tables:
    if 'tubi' in t.lower() or 'inscription' in t.lower() or 'record' in t.lower():
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        print(f"\n{t} columns:")
        for c in cols:
            print(f"  {c[1]} {c[2]}")
