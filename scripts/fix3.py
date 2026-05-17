import sqlite3
conn = sqlite3.connect(r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db')
conn.execute("UPDATE artists SET hometown='' WHERE name='莫朴' AND hometown LIKE '%院长%'")
conn.commit()
print("Fixed 莫朴 hometown")
conn.close()
