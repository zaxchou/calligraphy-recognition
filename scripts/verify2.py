import sqlite3
conn = sqlite3.connect(r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db')
print('=== 剩余生卒年全缺 (真正不详) ===')
rows = conn.execute("SELECT name, dynasty FROM artists WHERE (birth_year IS NULL OR birth_year=0) AND (death_year IS NULL OR death_year=0) AND name!='' ORDER BY dynasty, name").fetchall()
for r in rows:
    print(f'  {r[0]:10s} [{r[1]:10s}]')
total = conn.execute('SELECT COUNT(*) FROM artists').fetchone()[0]
print(f'\n总艺术家: {total}')
r = conn.execute('SELECT name, birth_year, death_year, occupation, dynasty, alias FROM artists WHERE name="荆浩"').fetchone()
print(f'\n荆浩: {r}')
for n in ['张萱','马路','刘刚','刘国辉']:
    r = conn.execute('SELECT COUNT(*) FROM artists WHERE name=?',(n,)).fetchone()
    print(f'{n}: {"残留" if r[0] else "已删除"}')
conn.close()
