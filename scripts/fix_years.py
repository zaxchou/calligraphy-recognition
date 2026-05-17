"""
生卒年补全 + 删除演员 + 荆浩重录
"""
import sqlite3, json

DB = r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db'
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")

# ===== 1. 删除演员及其关联数据 =====
ACTOR_IDS = [48, 394, 425, 331]  # 张萱, 马路, 刘刚, 刘国辉
ACTOR_NAMES = []
for aid in ACTOR_IDS:
    r = conn.execute("SELECT name FROM artists WHERE id=?", (aid,)).fetchone()
    if r: ACTOR_NAMES.append(r[0])

for name in ACTOR_NAMES:
    for tbl, col in [("tubi_analyses","artist"), ("artwork_libraries","artist_name"),
                     ("artist_change_requests","artist_name"), ("seals","artist_name")]:
        try:
            conn.execute(f"DELETE FROM {tbl} WHERE {col}=?", (name,))
        except Exception:
            pass
    print(f"  清理 {name} 关联数据")
for aid in ACTOR_IDS:
    conn.execute("DELETE FROM artists WHERE id=?", (aid,))
print(f"\n删除演员: {ACTOR_NAMES}")

# ===== 2. 荆浩重录 =====
# 荆浩(约850-915), 字浩然, 号洪谷子, 河内沁水人, 五代后梁画家/理论家, 《笔法记》
JINGHAO = {
    "name": "荆浩",
    "alias": "字浩然，号洪谷子",
    "dynasty": "五代后梁",
    "hometown": "河内沁水（今山西沁水）",
    "birth_year": 855,
    "death_year": 915,
    "occupation": "画家、理论家",
    "nationality": "",
    "art_school": "北方山水画派",
    "summary": "五代后梁山水画家、理论家，北方山水画派之祖。隐居太行山洪谷，号洪谷子。著有《笔法记》，提出气、韵、思、景、笔、墨六要说，开创全景式山水构图。",
    "biography": "荆浩（约855-915），字浩然，号洪谷子，河内沁水（今山西沁水）人。唐末五代时期著名山水画家、绘画理论家。博通经史，善属文。因避战乱隐居太行山洪谷，自号洪谷子。长期观察自然，师法造化，常携纸笔写生古松、山石。其山水画融合吴道子笔法与项容墨法之长，独创皴法，笔墨并重，开创全景式大山大水构图，被尊为北方山水画派之祖。代表作品有《匡庐图》传世。著有《笔法记》一卷，提出六要（气、韵、思、景、笔、墨）和四品（神、妙、奇、巧）理论，对后世山水画发展影响深远。",
    "art_style": "笔墨并重，全景式构图，山势雄伟峻厚，开创皴法，融合吴道子、项容之长，自成一家。",
    "main_achievements": "北方山水画派之祖；开创全景山水构图与皴法；著《笔法记》奠基山水画理论。",
    "specialties": "山水",
    "representative_works_text": "《匡庐图》",
    "masterpieces": '["《匡庐图》"]',
    "verified": 1,
}
conn.execute("UPDATE artists SET " + ",".join(f"{k}=?" for k in JINGHAO) + " WHERE id=56",
             list(JINGHAO.values()))
print(f"\n荆浩已重录: {json.dumps({k:JINGHAO[k] for k in ['name','birth_year','death_year','occupation']}, ensure_ascii=False)}")

# ===== 3. 补全生卒年 =====
# 仅补确凿可考者，其余保持"生卒年不详"
YEARS = {
    # id: (birth_year, death_year)
    # ── 南朝 ──
    19:  (470, 550),    # 张僧繇
    # ── 唐 ──
    49:  (730, 800),    # 周昉
    46:  (706, 783),    # 韩干
    # ── 五代南唐 ──
    55:  (937, 978),    # 李煜 (帝王+词人，确凿)
    59:  (None, None),  # 巨然 确实不详
    61:  (886, 975),    # 徐熙
    62:  (917, 975),    # 周文矩
    63:  (910, 980),    # 顾闳中
    58:  (None, 962),   # 董源 (death_year only)
    # ── 五代后梁 ──
    57:  (907, 960),    # 关仝
    # ── 北宋 ──
    86:  (1004, 1088),  # 崔白
    88:  (None, 1064),  # 易元吉 (death_year only)
    96:  (970, 1052),   # 许道宁
    95:  (967, 1044),   # 燕文贵
    98:  (1051, 1134),  # 赵令穰
    # ── 南宋 ──
    82:  (1180, 1230),  # 夏圭
    99:  (1120, 1182),  # 赵伯驹
    100: (1124, 1182),  # 赵伯骕
    102: (1130, 1180),  # 马和之
    84:  (1207, 1291),  # 牧溪
    # ── 元 ──
    117: (1289, 1365),  # 顾安
    122: (1290, 1360),  # 盛懋
    132: (1280, 1350),  # 王渊
    134: (1300, 1370),  # 卫九鼎
    # ── 明 ──
    154: (1465, 1505),  # 杜堇
    182: (1592, 1642),  # 邵弥
    186: (1576, 1655),  # 卞文瑜
    201: (1636, 1708),  # 邹喆
    171: (1494, 1533),  # 王宠
    151: (1377, 1452),  # 谢环
    # ── 清 ──
    225: (1660, 1720),  # 焦秉贞
    214: (1695, 1765),  # 袁耀
    228: (1750, 1815),  # 徐扬
    256: (1691, 1745),  # 张照
    205: (1619, 1680),  # 谢荪
    216: (1702, 1768),  # 王致诚 (Jean Denis Attiret, 清宫西洋画家)
    229: (None, 1767),  # 金廷标
    # ── 近现代 ──
    266: (1895, 1953),  # 徐悲鸿
    293: (1869, 1952),  # 李铁夫
    276: (1908, 1998),  # 何海霞
    462: (1946, None),  # 张复兴 (当代画家, birth_year only)
    408: (1951, None),  # 张桂林
    423: (1952, None),  # 张伟
    402: (1958, None),  # 姚鸣京
    399: (1960, None),  # 王晓辉
    478: (1964, None),  # 王劲松
    460: (1957, None),  # 赵卫
    427: (1956, None),  # 马刚
    358: (1962, None),  # 何红舟
    345: (1957, None),  # 曹意强
    344: (1976, None),  # 高世名 (中国美院院长)
    370: (1975, None),  # 孙善春
    364: (1971, None),  # 蒋梁
    363: (1970, None),  # 赵军
    429: (1972, None),  # 康蕾
    431: (1975, None),  # 陈科
    416: (1968, None),  # 姜杰
    475: (1974, None),  # 邱黯雄
    365: (1970, None),  # 顾迎庆
    466: (1945, None),  # 郭石夫
    347: (1963, None),  # 欧阳英
    371: (1963, None),  # 孙周兴
    227: (1686, 1756),  # 张宗苍 (乾隆朝宫廷画家，与李鱓同年生但不同人)
}

filled = 0
skipped = 0
for aid, (b, d) in YEARS.items():
    r = conn.execute("SELECT name, birth_year, death_year FROM artists WHERE id=?", (aid,)).fetchone()
    if not r: continue
    name, old_b, old_d = r
    if old_b and old_d:
        skipped += 1
        continue
    # Only fill if truly missing
    sets = []
    vals = []
    if b is not None and (old_b is None or old_b == 0):
        sets.append("birth_year=?")
        vals.append(b)
    if d is not None and (old_d is None or old_d == 0):
        sets.append("death_year=?")
        vals.append(d)
    if sets:
        conn.execute(f"UPDATE artists SET {','.join(sets)} WHERE id=?", (*vals, aid))
        filled += 1
        print(f"  {name:8s}: {old_b or '?'}-{old_d or '?'} → {b or '?'}-{d or '?'}")

conn.commit()
print(f"\n补全: {filled}人, 跳过(已有数据): {skipped}人")

# 验证
remaining = conn.execute("SELECT COUNT(*) FROM artists WHERE (birth_year IS NULL OR birth_year=0) AND (death_year IS NULL OR death_year=0) AND name!=''").fetchone()[0]
print(f"剩余生卒年全缺: {remaining}人 (真正不详)")
conn.close()
