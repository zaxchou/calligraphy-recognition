import sqlite3

conn = sqlite3.connect('data/calligraphy.db')
c = conn.cursor()

# Clean up test data - clear album_name, album_index, tags where album_name starts with 'test'
c.execute("UPDATE tubi_analyses SET album_name=NULL, album_index=NULL, tags=NULL WHERE album_name LIKE 'test%'")
conn.commit()
print(f"Cleaned {c.rowcount} records")

# Verify
c.execute("SELECT COUNT(*) FROM tubi_analyses WHERE album_name IS NOT NULL")
print(f"Remaining album records: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM tubi_analyses WHERE tags IS NOT NULL")
print(f"Remaining tagged records: {c.fetchone()[0]}")
conn.close()
