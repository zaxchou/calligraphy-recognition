# -*- coding: utf-8 -*-
import sqlite3, json
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()
cur.execute("PRAGMA table_info(tubi_analyses)")
for col in cur.fetchall():
    print(col[1], '|', col[2])
conn.close()