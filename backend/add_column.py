import sqlite3
conn = sqlite3.connect('data/calligraphy.db')
cursor = conn.cursor()
cursor.execute('ALTER TABLE tubi_jobs ADD COLUMN mode VARCHAR(30) DEFAULT "analyze"')
conn.commit()
print('Column added successfully')
conn.close()