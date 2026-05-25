# rebuild_v4.py — 最终版，结构化提取百度百科全部内容
import urllib.request, urllib.parse, urllib.error
from bs4 import BeautifulSoup
import re, json, time, os, sys, sqlite3
from datetime import datetime

DB = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'calligraphy.db'))

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
           'Accept': 'text/html', 'Accept-Language': 'zh-CN,zh;q=0.9'}

ARTISTS = [
    "王羲之","顾恺之","王献之","钟繇","陆机","宗炳",
    "颜真卿","柳公权","欧阳询","吴道子","张旭","怀素",
    "阎立本","周昉","韩干","韩滉","孙过庭","褚遂良","虞世南",
    "李思训","王维","张萱","荆浩","董源","巨然","徐浩",
    "苏轼","黄庭坚","米芾","蔡襄","赵佶","范宽","李成",
    "郭熙","李公麟","马远","夏圭","梁楷","刘松年","李唐",
    "文同","赵孟坚","牧溪","崔白","李迪","张择端","赵伯骕",
    "米友仁","王诜","李嵩","苏汉臣","林椿","赵昌","易元吉",
    "赵孟頫","黄公望","倪瓒","王蒙","吴镇","钱选","高克恭",
    "柯九思","李衎","王冕","朱德润","曹知白","方从义","张雨",
    "沈周","文徵明","唐寅","仇英","董其昌","周臣",
    "戴进","吴伟","蓝瑛","陈洪绶","崔子忠","杜堇",
    "边景昭","林良","吕纪","王绂","夏昶","祝允明","王宠",
    "文彭","陆治","周之冕","谢时臣","项圣谟","张宏","曾鲸","王铎","孙隆",
    "王时敏","王鉴","王翚","王原祁","吴历","恽寿平",
    "石涛","弘仁","髡残","黄慎","汪士慎","高翔","罗聘","华嵒","高凤翰","边寿民",
    "袁江","袁耀","任伯年","任熊","任薰","虚谷","赵之谦",
    "蒲华","吴昌硕","改琦","费丹旭","郎世宁","焦秉贞","冷枚","梅清","樊圻",
    "齐白石","黄宾虹","徐悲鸿","张大千","傅抱石",
    "李可染","林风眠","刘海粟","吴作人","关山月","黎雄才",
    "陆俨少","钱松岩","石鲁","黄胄","程十发","谢稚柳",
    "吴冠中","朱屺瞻","丰子恺","叶浅予","蒋兆和","李苦禅",
    "王雪涛","于非闇","来楚生","陆维钊","沙孟海",
    "赵望云","何海霞","陈半丁",
    "沈尹默","白蕉","林散之","启功","赵朴初",
    "邓散木","于右任","谢无量",
    "范曾","何家英","田黎明","冯远","贾又福",
    "黄永玉","韩美林","刘国松",
]
EXISTING = {'李鱓','刘海勇','郑燮','金农','徐渭','潘天寿','朱耷','陈淳'}

KNOWN_YEARS = {
    "王羲之":(303,361),"顾恺之":(348,409),"王献之":(344,386),"钟繇":(151,230),"陆机":(261,303),"宗炳":(375,443),
    "颜真卿":(709,785),"柳公权":(778,865),"欧阳询":(557,641),"吴道子":(680,759),"张旭":(675,750),"怀素":(737,799),
    "阎立本":(601,673),"周昉":(730,800),"韩干":(706,783),"韩滉":(723,787),"孙过庭":(646,691),"褚遂良":(596,658),
    "虞世南":(558,638),"李思训":(651,716),"王维":(701,761),"张萱":(713,755),
    "荆浩":(850,930),"董源":(934,962),"巨然":(910,980),"徐浩":(703,782),
    "苏轼":(1037,1101),"黄庭坚":(1045,1105),"米芾":(1051,1107),"蔡襄":(1012,1067),"赵佶":(1082,1135),
    "范宽":(950,1032),"李成":(919,967),"郭熙":(1023,1085),"李公麟":(1049,1106),"马远":(1140,1225),
    "夏圭":(1180,1230),"梁楷":(1150,1220),"刘松年":(1155,1218),"李唐":(1066,1150),"文同":(1018,1079),
    "赵孟坚":(1199,1264),"牧溪":(1210,1270),"崔白":(1004,1088),"李迪":(1100,1197),"张择端":(1085,1145),
    "赵伯骕":(1124,1182),"米友仁":(1074,1153),"王诜":(1048,1104),"李嵩":(1166,1243),"苏汉臣":(1094,1172),
    "林椿":(1130,1190),"赵昌":(959,1016),"易元吉":(1000,1064),
    "赵孟頫":(1254,1322),"黄公望":(1269,1354),"倪瓒":(1301,1374),"王蒙":(1308,1385),"吴镇":(1280,1354),
    "钱选":(1239,1301),"高克恭":(1248,1310),"柯九思":(1290,1343),"李衎":(1245,1320),"王冕":(1287,1359),
    "朱德润":(1294,1365),"曹知白":(1272,1355),"方从义":(1302,1393),"张雨":(1283,1350),
    "沈周":(1427,1509),"文徵明":(1470,1559),"唐寅":(1470,1524),"仇英":(1494,1552),"董其昌":(1555,1636),
    "周臣":(1460,1535),"戴进":(1388,1462),"吴伟":(1459,1508),"蓝瑛":(1585,1664),"陈洪绶":(1599,1652),
    "崔子忠":(1574,1644),"杜堇":(1465,1505),"边景昭":(1356,1428),"林良":(1428,1494),"吕纪":(1477,1510),
    "王绂":(1362,1416),"夏昶":(1388,1470),"祝允明":(1461,1527),"王宠":(1494,1533),"文彭":(1498,1573),
    "陆治":(1496,1576),"周之冕":(1521,1591),"谢时臣":(1488,1567),"项圣谟":(1597,1658),"张宏":(1577,1652),
    "曾鲸":(1564,1647),"王铎":(1592,1652),"孙隆":(1430,1490),
    "王时敏":(1592,1680),"王鉴":(1598,1677),"王翚":(1632,1717),"王原祁":(1642,1715),"吴历":(1632,1718),
    "恽寿平":(1633,1690),"石涛":(1642,1707),"弘仁":(1610,1664),"髡残":(1612,1673),
    "黄慎":(1687,1768),"汪士慎":(1686,1759),"高翔":(1688,1753),"罗聘":(1733,1799),"华嵒":(1682,1756),
    "高凤翰":(1683,1749),"边寿民":(1684,1752),"袁江":(1662,1735),"袁耀":(1700,1778),"任伯年":(1840,1895),
    "任熊":(1823,1857),"任薰":(1835,1893),"虚谷":(1823,1896),"赵之谦":(1829,1884),"蒲华":(1832,1911),
    "吴昌硕":(1844,1927),"改琦":(1773,1828),"费丹旭":(1802,1850),"郎世宁":(1688,1766),"焦秉贞":(1653,1712),
    "冷枚":(1669,1742),"梅清":(1623,1697),"樊圻":(1616,1694),
    "齐白石":(1864,1957),"黄宾虹":(1865,1955),"徐悲鸿":(1895,1953),"张大千":(1899,1983),"傅抱石":(1904,1965),
    "李可染":(1907,1989),"林风眠":(1900,1991),"刘海粟":(1896,1994),"吴作人":(1908,1997),"关山月":(1912,2000),
    "黎雄才":(1910,2001),"陆俨少":(1909,1993),"钱松岩":(1899,1985),"石鲁":(1919,1982),"黄胄":(1925,1997),
    "程十发":(1921,2007),"谢稚柳":(1910,1997),"吴冠中":(1919,2010),"朱屺瞻":(1892,1996),"丰子恺":(1898,1975),
    "叶浅予":(1907,1995),"蒋兆和":(1904,1986),"李苦禅":(1899,1983),"王雪涛":(1903,1982),"于非闇":(1889,1959),
    "来楚生":(1903,1975),"陆维钊":(1899,1980),"沙孟海":(1900,1992),"赵望云":(1906,1977),"何海霞":(1908,1998),
    "陈半丁":(1876,1970),"沈尹默":(1883,1971),"白蕉":(1907,1969),"林散之":(1898,1989),"启功":(1912,2005),
    "赵朴初":(1907,2000),"邓散木":(1898,1963),"于右任":(1879,1964),"谢无量":(1884,1964),
    "范曾":(1938,None),"何家英":(1957,None),"田黎明":(1955,None),"冯远":(1952,None),"贾又福":(1942,None),
    "黄永玉":(1924,2023),"韩美林":(1936,None),"刘国松":(1932,None),
}

def clean(text):
    t = re.sub(r'\[\d+(?:[-,/]\d+)*\]', '', text)
    t = re.sub(r'[  ]+', ' ', t)
    return t.replace('　', ' ').strip()

def fetch(name):
    for url in [f"https://baike.baidu.com/item/{urllib.parse.quote(name)}",
                f"https://baike.baidu.com/item/{urllib.parse.quote(name)}/1"]:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    h = r.read().decode('utf-8', errors='replace')
                    if len(h) > 5000 and name in h:
                        return BeautifulSoup(h, 'lxml')
        except: pass
    return None

def parse(name):
    soup = fetch(name)
    if not soup: return None
    info = {}

    # BasicInfo
    raw = {}
    c = soup.select_one('[class*="J-basic-info"]')
    if c:
        for dt in c.select('dt'):
            k = dt.get_text(strip=True).replace('\xa0',' ').replace('\xa0',' ')
            if not k: continue
            dd = dt.find_next('dd')
            if dd: raw[k] = dd.get_text(strip=True).replace('\xa0',' ')

    # Alias
    alias = []
    for k in ['字','号','别号','自号','别名','本名']:
        v = raw.get(k,'').strip()
        if v: alias.append(f'{k}:{v}')
    if not alias:
        sp = soup.select('.J-summary [class*="para_"]') or soup.select('[class*="summary"] [class*="para_"]')
        txt = ''
        for p in (sp or [])[:2]:
            t = p.get_text(strip=True)
            if len(t) > 20: txt += t
        zm = re.search(r'字([一-鿿]{1,6})[，,\s]*(?:又字|更字|后改名.*?字|号)', txt)
        if zm: alias.append(f'字:{zm.group(1)}')
        hm = re.search(r'号([一-鿿]{2,12}(?:山人|居士|道人|老人|主人|先生|散人|翁|子|客)?)', txt)
        if hm: alias.append(f'号:{hm.group(1)}')
        ym = re.search(r'原名([一-鿿]{2,6})', txt)
        if ym: alias.append(f'原名:{ym.group(1)}')
    info['alias'] = '; '.join(alias)[:200]

    # Dynasty
    for k in ['所处时代','朝代','时代']:
        if raw.get(k): info['dynasty'] = raw[k][:20]; break
    if 'dynasty' not in info: info['dynasty'] = ''

    # Hometown
    for k in ['出生地','籍贯','出生地点']:
        if raw.get(k): info['hometown'] = raw[k][:100]; break
    if 'hometown' not in info: info['hometown'] = ''

    # Birth/Death
    bs = ''; ds = ''
    for k in ['出生日期','出生时间','生年','出生']:
        if raw.get(k): bs = raw[k]; break
    for k in ['逝世日期','去世时间','卒年','逝世']:
        if raw.get(k): ds = raw[k]; break
    info['birth_year'] = int(m.group(1)) if (m := re.search(r'(\d{4})', bs)) else None
    info['death_year'] = int(m.group(1)) if (m := re.search(r'(\d{4})', ds)) else None
    if info['birth_year'] is None and name in KNOWN_YEARS: info['birth_year'] = KNOWN_YEARS[name][0]
    if info['death_year'] is None and name in KNOWN_YEARS: info['death_year'] = KNOWN_YEARS[name][1]

    # Dynasty fallback
    if not info['dynasty'] and info.get('birth_year'):
        by = info['birth_year']
        if by >= 1949: info['dynasty'] = '当代'
        elif by >= 1912: info['dynasty'] = '近现代'
        elif by >= 1840: info['dynasty'] = '近代'
        elif by >= 1644: info['dynasty'] = '清代'
        elif by >= 1368: info['dynasty'] = '明代'
        elif by >= 1271: info['dynasty'] = '元代'
        elif by >= 960: info['dynasty'] = '宋代'
        elif by >= 618: info['dynasty'] = '唐代'
        elif by >= 420: info['dynasty'] = '晋代'
        elif by >= 220: info['dynasty'] = '汉代'
        else: info['dynasty'] = '秦汉以前'

    # Other fields
    info['nationality'] = raw.get('国籍', raw.get('国    籍',''))[:20] or '中国'
    info['occupation'] = raw.get('职业', raw.get('职    业',''))[:100]
    info['main_achievements'] = raw.get('主要成就', raw.get('主要成就/荣誉',''))[:500]
    ws = raw.get('代表作品', raw.get('代表作', raw.get('主要作品','')))
    if ws:
        wl = [w.strip() for w in re.split(r'[、，,《》\s]+', ws) if len(w.strip()) > 1 and w.strip() != '等']
        info['masterpieces'] = json.dumps(wl[:10], ensure_ascii=False)
    else: info['masterpieces'] = '[]'

    # Summary
    sp_els = soup.select('.J-summary [class*="para_"]') or soup.select('[class*="summary"] [class*="para_"]')
    st = ''
    for p in sp_els:
        t = clean(p.get_text(strip=True))
        if len(t) > 15: st += t + '\n'
    info['summary'] = st[:500]

    # Biography
    all_p = soup.select('[class*="para_"]')
    bt = ''
    for p in all_p:
        parent = p.parent
        pc = ' '.join(parent.get('class',[])).lower() if parent else ''
        if 'summary' in pc or 'table' in pc: continue
        t = clean(p.get_text(strip=True))
        if len(t) > 15 and not re.match(r'^\d{4}年.{0,20}$', t):
            bt += t + '\n'
    info['biography'] = bt[:3000]

    # Chronology
    chron = _table_chron(soup, info.get('birth_year'), info.get('death_year'))
    if len(chron) < 5:
        te = _text_chron(st + '\n' + bt, info.get('birth_year'), info.get('death_year'))
        seen = {e['year'] for e in chron}
        for e in te:
            if e['year'] not in seen:
                chron.append(e); seen.add(e['year'])
    chron.sort(key=lambda e: e.get('year',0))
    # Strip _dedup
    for e in chron: e.pop('_dedup', None)
    info['art_chronology'] = json.dumps(chron, ensure_ascii=False)

    return info

def _table_chron(soup, birth, death):
    events = []
    for row in soup.select('table tr, [class*="table"] tr'):
        cells = row.select('td, th')
        if len(cells) < 2: continue
        fc = clean(cells[0].get_text())
        ym = re.search(r'(\d{4})', fc)
        if not ym: continue
        y = int(ym.group(1))
        if birth and y < birth - 5: continue
        if death and y > death + 2: continue
        et = clean(cells[1].get_text()) if len(cells) > 1 else ''
        desc = ' '.join(clean(c.get_text()) for c in cells[1:])
        key = f'{y}_{et[:20]}'
        if any(e.get('_dedup') == key for e in events): continue
        events.append({'year':y, 'event':et[:40] or fc, 'location':'', 'description':desc[:250], '_dedup':key})
    return events

def _text_chron(text, birth, death):
    events = []; seen = set()
    for m in re.finditer(r'(?:(?:^|\n|。|；)\s*)?(\d{4})年[，,\s]*([^。；\n]{15,250}?)(?=[。；\n]|$)', text):
        y = int(m.group(1)); content = m.group(2).strip()
        if y in seen: continue
        if birth and y < birth - 5: continue
        if death and y > death + 2: continue
        seen.add(y)
        loc = ''
        lm = re.search(r'(?:在|于|至|赴|到|居|任|迁|移)([一-鿿]{2,6}(?:市|县|府|州|镇|村|乡)?)', content)
        if lm: loc = lm.group(1)
        events.append({'year':y, 'event':clean(content[:40]), 'location':loc, 'description':clean(content[:250])})
    for m in re.finditer(r'[（(]公元\s*(\d{4})年[)）]', text):
        y = int(m.group(1))
        if y not in seen:
            seen.add(y); events.append({'year':y, 'event':'', 'location':'', 'description':''})
    return events

def save(db, name, info):
    now = datetime.now().isoformat()
    fields = {k: info.get(k, '') for k in ['alias','dynasty','hometown','birth_year','death_year','biography','summary','nationality','occupation','main_achievements','masterpieces','art_chronology']}
    ex = db.execute('SELECT id, travel_notes FROM artists WHERE name = ?', (name,)).fetchone()
    if ex:
        vals = list(fields.values()) + [now, name]
        db.execute(f'UPDATE artists SET {", ".join(f"{k}=?" for k in fields)}, updated_at=?, verified=1 WHERE name=?', vals)
        return 'updated'
    else:
        cols = ['name'] + list(fields.keys()) + ['created_at','updated_at','verified','enabled','featured']
        vals = [name] + list(fields.values()) + [now, now, 1, 1, 0]
        db.execute(f'INSERT INTO artists ({",".join(cols)}) VALUES ({",".join("?"*len(vals))})', vals)
        return 'inserted'

def main():
    todel = [n for n in ARTISTS if n not in EXISTING]
    print(f'{len(EXISTING)} existing + {len(todel)} new')

    db = sqlite3.connect(DB)
    ins = upd = fail = 0
    for i, name in enumerate(todel):
        try:
            info = parse(name)
            if not info: fail += 1; continue
            chron = json.loads(info.get('art_chronology','[]'))
            r = save(db, name, info)
            if r == 'inserted': ins += 1
            else: upd += 1
            db.commit()
            print(f'[{i+1}/{len(todel)}] {name} {info.get("birth_year","?")}-{info.get("death_year","?")} '
                  f'[{info.get("dynasty","?")[:10]}] alias={info.get("alias","")[:30] or "-"} '
                  f'chron={len(chron)} summary={len(info.get("summary",""))} bio={len(info.get("biography",""))}')
        except Exception as e:
            print(f'[{i+1}/{len(todel)}] {name} FAIL: {e}')
            fail += 1
        time.sleep(1.5)
    db.close()
    print(f'\nDone: {ins} new + {upd} updated + {fail} failed = {ins+upd+len(EXISTING)} total')

if __name__ == '__main__':
    main()
