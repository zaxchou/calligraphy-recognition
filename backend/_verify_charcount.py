import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM tubi_analyses WHERE char_count IS NULL OR char_count = 0")
print("char_count为空或0的记录:", cur.fetchone()[0])
conn.close()