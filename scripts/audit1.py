"""
全量审计艺术家数据：occupation异常/hometown异常/字段缺失/格式问题/疑似幻觉
"""
import sqlite3, json, re
from collections import Counter

DB = r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db'
conn = sqlite3.connect(DB)

print("=" * 60)
print("1. occupation 非标准值")
print("=" * 60)
occ_counts = Counter()
occ_rows = conn.execute(
    "SELECT name, occupation FROM artists WHERE occupation != '' AND occupation IS NOT NULL AND occupation NOT LIKE '%画家%' AND occupation NOT LIKE '%书法%' AND occupation NOT LIKE '%美术%' AND occupation NOT LIKE '%绘画%' AND occupation NOT LIKE '%书画%' AND occupation NOT LIKE '%篆刻%' AND occupation NOT LIKE '%艺术%' AND occupation NOT LIKE '%理论%' AND occupation NOT LIKE '%教授%' AND occupation NOT LIKE '%教师%' AND occupation NOT LIKE '%老师%' AND occupation NOT LIKE '%学者%' AND occupation NOT LIKE '%鉴定%'"
).fetchall()
for r in occ_rows:
    occ_counts[r[1]] += 1
    if len(occ_counts) <= 30:
        print(f'  {r[0]:10s}: {r[1][:50]}')
if len(occ_rows) > 30:
    print(f'  ... 共 {len(occ_rows)} 条')

print("\n" + "=" * 60)
print("2. hometown 含数字/异常字符")
print("=" * 60)
rx = re.compile(r'\d')
bad_hometowns = conn.execute(
    "SELECT name, hometown FROM artists WHERE hometown != '' AND hometown IS NOT NULL AND hometown GLOB '*[0-9]*'"
).fetchall()
for r in bad_hometowns:
    print(f'  {r[0]:10s}: {r[1][:60]}')

print("\n" + "=" * 60)
print("3. occupation 含数字")
print("=" * 60)
bad_occ = conn.execute(
    "SELECT name, occupation FROM artists WHERE occupation GLOB '*[0-9]*'"
).fetchall()
for r in bad_occ:
    print(f'  {r[0]:10s}: {r[1][:60]}')

print("\n" + "=" * 60)
print("4. dynasty 缺失/为空的")
print("=" * 60)
no_dynasty = conn.execute(
    "SELECT name, dynasty FROM artists WHERE (dynasty IS NULL OR dynasty = '') AND name != ''"
).fetchall()
for r in no_dynasty:
    print(f'  {r[0]:10s}')

print(f'  → 共 {len(no_dynasty)} 人')

print("\n" + "=" * 60)
print("5. 重复名字检查")
print("=" * 60)
dupes = conn.execute(
    "SELECT name, COUNT(*) as cnt FROM artists WHERE name != '' GROUP BY name HAVING cnt > 1"
).fetchall()
for r in dupes:
    rows = conn.execute("SELECT id, name, dynasty, birth_year, death_year FROM artists WHERE name=?", (r[0],)).fetchall()
    for r2 in rows:
        print(f'  id={r2[0]} {r2[1]:10s} [{r2[2]:8s}] {r2[3]}-{r2[4]}')
print(f'  → {len(dupes)} 组重复名')

print("\n" + "=" * 60)
print("6. avatar_url 仍为百度CDN的")
print("=" * 60)
cdn = conn.execute(
    "SELECT COUNT(*) FROM artists WHERE avatar_url LIKE '%bcebos.com%' OR avatar_url LIKE '%baidu.com%'"
).fetchone()
print(f'  → {cdn[0]} 人仍用CDN (应已全部本地化)')

print("\n" + "=" * 60)
print("7. 缺失关键字段统计")
print("=" * 60)
for col, label in [("biography","生平"), ("summary","概述"), ("art_school","画派"),
                     ("hometown","籍贯"), ("alias","字号")]:
    cnt = conn.execute(f"SELECT COUNT(*) FROM artists WHERE ({col} IS NULL OR {col} = '') AND name != ''").fetchone()[0]
    pct = cnt / 481 * 100
    print(f'  {label:4s}: {cnt:3d}人缺失 ({pct:.0f}%)')

print("\n" + "=" * 60)
print("8. photos 字段格式（应全部为对象数组）")
print("=" * 60)
photos_rows = conn.execute(
    "SELECT name, photos FROM artists WHERE photos != '[]' AND photos != '' AND photos IS NOT NULL LIMIT 10"
).fetchall()
for r in photos_rows:
    try:
        arr = json.loads(r[1])
        types = set()
        for p in arr:
            types.add(type(p).__name__)
        print(f'  {r[0]:8s}: {len(arr)}张, 类型={types}')
    except:
        print(f'  {r[0]:8s}: 解析失败 | {r[1][:60]}')

print("\n" + "=" * 60)
print("9. 总体统计")
print("=" * 60)
total = conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
with_bio = conn.execute("SELECT COUNT(*) FROM artists WHERE biography != '' AND biography IS NOT NULL").fetchone()[0]
with_years = conn.execute("SELECT COUNT(*) FROM artists WHERE (birth_year IS NOT NULL AND birth_year != 0) OR (death_year IS NOT NULL AND death_year != 0)").fetchone()[0]
with_alias = conn.execute("SELECT COUNT(*) FROM artists WHERE alias != '' AND alias IS NOT NULL").fetchone()[0]
with_dyn = conn.execute("SELECT COUNT(*) FROM artists WHERE dynasty != '' AND dynasty IS NOT NULL").fetchone()[0]
with_avatar = conn.execute("SELECT COUNT(*) FROM artists WHERE avatar_url != '' AND avatar_url IS NOT NULL").fetchone()[0]
with_photos = conn.execute("SELECT COUNT(*) FROM artists WHERE photos != '[]' AND photos != '' AND photos IS NOT NULL").fetchone()[0]

print(f'  总人数: {total}')
print(f'  有生平: {with_bio}/{total} ({with_bio/total*100:.0f}%)')
print(f'  有生卒年: {with_years}/{total} ({with_years/total*100:.0f}%)')
print(f'  有字号: {with_alias}/{total} ({with_alias/total*100:.0f}%)')
print(f'  有朝代: {with_dyn}/{total} ({with_dyn/total*100:.0f}%)')
print(f'  有头像: {with_avatar}/{total} ({with_avatar/total*100:.0f}%)')
print(f'  有照片: {with_photos}/{total} ({with_photos/total*100:.0f}%)')

conn.close()
