"""
修复审计发现的问题：
1. hometown/occupation 数字尾巴污染
2. 非标准occupation清理
3. dynasty缺失补全
4. 删除确认为非艺术家的幻觉数据
"""
import sqlite3, re

DB = r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db'
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")

# ===== 0. 删除确认为非艺术家的幻觉数据 =====
print("=" * 50)
print("0. 删除非艺术家幻觉数据")
print("=" * 50)
DELETE_NAMES = [
    "林良",     # id=149, 1924作家(厦门), 非明代画家林良
    "吴彬",     # id=156, 1937武术副主席, 非明代画家吴彬
    "王赞",     # id=336, 西晋文学家, 非画家
    "欧阳英",   # id=347, 武林盟主幻觉
    "李洋",     # id=403, 纪检监察干部
    "沈浩",     # id=353, 公务员村官
    "孙为民",   # id=388, 企业家
]
for name in DELETE_NAMES:
    r = conn.execute("SELECT id FROM artists WHERE name=?", (name,)).fetchone()
    if not r: continue
    aid = r[0]
    for tbl, col in [("tubi_analyses","artist"), ("artwork_libraries","artist_name")]:
        try:
            conn.execute(f"DELETE FROM {tbl} WHERE {col}=?", (name,))
        except: pass
    conn.execute("DELETE FROM artists WHERE id=?", (aid,))
    print(f"  已删除: {name} (id={aid})")

# ===== 1. 清理hometown尾随数字 =====
print("=" * 50)
print("1. 清理hometown尾随数字")
print("=" * 50)
rows = conn.execute(
    "SELECT id, name, hometown FROM artists WHERE hometown GLOB '*[0-9]*'"
).fetchall()
for r in rows:
    cleaned = re.sub(r'\d+\s*$', '', r[2]).strip()
    if cleaned != r[2]:
        conn.execute("UPDATE artists SET hometown=? WHERE id=?", (cleaned, r[0]))
        print(f'  {r[1]:8s}: "{r[2][:40]}" → "{cleaned[:40]}"')

# ===== 2. 清理occupation尾随数字 =====
print("\n" + "=" * 50)
print("2. 清理occupation尾随数字")
print("=" * 50)
rows = conn.execute(
    "SELECT id, name, occupation FROM artists WHERE occupation GLOB '*[0-9]*'"
).fetchall()
for r in rows:
    cleaned = re.sub(r'\d+\s*$', '', r[2]).strip()
    if cleaned != r[2]:
        conn.execute("UPDATE artists SET occupation=? WHERE id=?", (cleaned, r[0]))
        print(f'  {r[1]:8s}: "{r[2][:40]}" → "{cleaned[:40]}"')

# ===== 3. 修复非标准occupation =====
print("\n" + "=" * 50)
print("3. 修复非画家occupation")
print("=" * 50)

FIX_OCC = {
    # name -> new_occupation  (这些都是美术/书法相关，需纠正)
    "吕品昌": "雕塑家、陶艺家",
    "王少军": "雕塑家",
    "张晓刚": "",
    "刘炜": "",
    "王广义": "",
    "岳敏君": "",
    "杨福东": "",
    "宋冬": "",
    "蔡国强": "当代艺术家",
    "袁运生": "",
    "杜牧": "诗人、书法家",
    "朱熹": "理学家、书法家",
    "吴宏": "画家",
    "叶欣": "画家",
}
for name, occ in FIX_OCC.items():
    if occ:
        conn.execute("UPDATE artists SET occupation=? WHERE name=?", (occ, name))
        print(f'  {name}: → "{occ}"')
    else:
        conn.execute("UPDATE artists SET occupation='' WHERE name=?", (name,))
        print(f'  {name}: → 已清空')

# ===== 4. 补全dynasty =====
print("\n" + "=" * 50)
print("4. 补全缺失的dynasty")
print("=" * 50)

FIX_DYN = {
    "李煜": "五代南唐",
    "徐悲鸿": "现代",
    "高世名": "当代",
    "赵军": "当代",
    "蒋梁": "当代",
    "孙周兴": "当代",
    "陈科": "当代",
    "岳敏君": "当代",
    "刘炜": "当代",
    "王广义": "当代",
    "郭石夫": "当代",
    "袁运生": "当代",
    "蔡国强": "当代",
    "杨福东": "当代",
    "宋冬": "当代",
}
for name, dyn in FIX_DYN.items():
    conn.execute("UPDATE artists SET dynasty=? WHERE name=?", (dyn, name))
    print(f'  {name}: → {dyn}')

# ===== 5. 清理alice=无 / hometown=无 =====
print("\n" + "=" * 50)
print("5. 清理 alias='无'")
print("=" * 50)
alias_none = conn.execute(
    "SELECT id, name FROM artists WHERE alias='无'"
).fetchall()
for r in alias_none:
    conn.execute("UPDATE artists SET alias='' WHERE id=?", (r[0],))
    print(f'  {r[1]}: alias=无 → 清空')

# ===== 6. 清理hometown='无' =====
print("\n" + "=" * 50)
print("6. 清理 hometown='无'")
print("=" * 50)
ht_none = conn.execute(
    "SELECT id, name FROM artists WHERE hometown='无'"
).fetchall()
for r in ht_none:
    conn.execute("UPDATE artists SET hometown='' WHERE id=?", (r[0],))
    print(f'  {r[1]}: hometown=无 → 清空')

conn.commit()

# ===== 验证 =====
print("\n" + "=" * 50)
print("7. 验证修复结果")
print("=" * 50)
tail_num = conn.execute("SELECT COUNT(*) FROM artists WHERE hometown GLOB '*[0-9]' OR occupation GLOB '*[0-9]*'").fetchone()[0]
no_dyn = conn.execute("SELECT COUNT(*) FROM artists WHERE (dynasty IS NULL OR dynasty='') AND name!=''").fetchone()[0]
no_occ = conn.execute(
    "SELECT COUNT(*) FROM artists WHERE occupation != '' AND occupation NOT LIKE '%画家%' AND occupation NOT LIKE '%书法%' AND occupation NOT LIKE '%美术%' AND occupation NOT LIKE '%绘画%' AND occupation NOT LIKE '%书画%' AND occupation NOT LIKE '%篆刻%' AND occupation NOT LIKE '%艺术%' AND occupation NOT LIKE '%理论%' AND occupation NOT LIKE '%教授%' AND occupation NOT LIKE '%教师%' AND occupation NOT LIKE '%雕塑%' AND occupation NOT LIKE '%陶艺%' AND occupation NOT LIKE '%文人%'"
).fetchone()[0]

print(f'  尾随数字: {tail_num} (应为0)')
print(f'  dynasty缺失: {no_dyn} (应为0)')
print(f'  非标准occ: {no_occ}')

conn.close()
print("\n修复完成")
