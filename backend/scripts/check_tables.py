import sqlite3
conn = sqlite3.connect('data/knowledge.db')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
for row in cursor:
    print(row[0])
conn.close()
