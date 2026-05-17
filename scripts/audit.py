import sqlite3, json, re
conn = sqlite3.connect(r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db')

# 1. Find potential non-artists - check occupation/bio for actor/entertainer keywords
print("=== 疑似非画家（演员/歌手等） ===")
for kw in ['演员', '歌手', '导演', '主持人', '编剧', '制片', '模特']:
    rows = conn.execute(f"SELECT name, occupation, substr(biography,1,80) FROM artists WHERE (occupation LIKE '%{kw}%' OR biography LIKE '%{kw}%') AND name!=''").fetchall()
    for r in rows:
        print(f'  [{kw}] {r[0]}: occ={r[1]}, bio={r[2][:60] if r[2] else "N/A"}')

# 2. Find specific suspicious names  
print("\n=== 特定名字检查（张萱、荆浩等） ===")
for name in ['张萱', '荆浩']:
    r = conn.execute("SELECT name, occupation, dynasty, birth_year, death_year, biography FROM artists WHERE name=?", (name,)).fetchone()
    if r: print(f'  {r[0]}: occ={r[1]}, dyn={r[2]}, {r[3]}-{r[4]}, bio={r[5][:80] if r[5] else "N/A"}')

# 3. Find all artists with missing birth_year AND death_year
print("\n=== 生卒年全部缺失（按朝代分组） ===")
rows = conn.execute("""
    SELECT dynasty, COUNT(*) as cnt FROM artists 
    WHERE (birth_year IS NULL OR birth_year = 0) AND (death_year IS NULL OR death_year = 0)
    AND name != '' GROUP BY dynasty ORDER BY cnt DESC
""").fetchall()
for r in rows: print(f'  {r[0]}: {r[1]}人')

# 4. Sample of those missing
print("\n=== 生卒年缺失样例（前30） ===")
rows = conn.execute("""
    SELECT name, dynasty, birth_year, death_year FROM artists 
    WHERE (birth_year IS NULL OR birth_year = 0) AND (death_year IS NULL OR death_year = 0)
    AND name != '' ORDER BY name LIMIT 30
""").fetchall()
for r in rows: print(f'  {r[0]:12s} [{r[1]:6s}] b={r[2]} d={r[3]}')

# 5. Check artwork_count for featured artists
print("\n=== 推荐画家的作品数 ===")
rows = conn.execute("""
    SELECT a.name, a.featured, 
    (SELECT COUNT(*) FROM artwork_libraries WHERE artist_name=a.name) as aw_cnt
    FROM artists a WHERE a.featured=1
""").fetchall()
for r in rows: print(f'  {r[0]:10s}: featured={r[1]}, artwork_count_db={r[2]}')

# 6. Check API artwork_count
print("\n=== API返回的作品数格式 ===")
rows = conn.execute("SELECT name, artwork_count FROM artists WHERE featured=1 LIMIT 5").fetchall()
for r in rows: print(f'  {r[0]}: artwork_count={r[1]}')

conn.close()
