"""
批量校验474位艺术家：百度百科存在性 + AI幻觉检测 + 修复
"""
import sqlite3, json, re, time, urllib.request, urllib.parse, urllib.error
from bs4 import BeautifulSoup
from datetime import datetime
import os, sys

DB = os.environ.get('DB_PATH', '/opt/calligraphy-recognition/backend/data/calligraphy.db')
LOG = '/tmp/full_audit.log'

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
           'Accept': 'text/html', 'Accept-Language': 'zh-CN,zh;q=0.9'}

def log(msg):
    print(msg)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(msg + '\n')

def has_baike(name):
    """检查百度百科是否存在"""
    try:
        url = f"https://baike.baidu.com/item/{urllib.parse.quote(name)}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='replace')
            return len(html) > 5000 and name in html
    except:
        return False

def check_chronology_hallucinations(chron, name, birth, death):
    """检测年谱中的AI幻觉"""
    issues = []
    for i, e in enumerate(chron):
        y = e.get('year')
        try: yi = int(y) if y else None
        except: yi = None

        # 1. 去世后的事件
        if death and yi and yi > death:
            issues.append({'idx': i, 'type': 'after_death', 'entry': e})

        # 2. 不可能年龄（<2岁且非出生）
        if birth and yi and yi - birth < 2 and yi >= birth:
            ev = str(e.get('event',''))
            if '出生' not in ev and '诞' not in ev:
                issues.append({'idx': i, 'type': 'impossible_age', 'entry': e})

        # 3. 古人出国（1850年前出生）
        if birth and birth < 1850:
            combined = str(e.get('event','')) + str(e.get('description',''))
            for kw in ['赴日','赴欧','赴美','赴法','赴德','赴英','出国','欧洲考察','日本交流','美国展览']:
                if kw in combined:
                    issues.append({'idx': i, 'type': 'fake_abroad', 'entry': e})
                    break

    return issues

def clean_chronology(chron, issues):
    """根据检测结果清理年谱"""
    bad_indices = {i['idx'] for i in issues}
    return [e for idx, e in enumerate(chron) if idx not in bad_indices]

KNOWN_YEARS = {
    "王羲之":(303,361),"顾恺之":(348,409),"王献之":(344,386),"钟繇":(151,230),"陆机":(261,303),
    "颜真卿":(709,785),"柳公权":(778,865),"欧阳询":(557,641),"吴道子":(680,759),"张旭":(675,750),
    "怀素":(737,799),"阎立本":(601,673),"褚遂良":(596,658),"虞世南":(558,638),"王维":(701,761),
    "荆浩":(850,930),"董源":(934,962),"巨然":(910,980),"徐浩":(703,782),
    "苏轼":(1037,1101),"黄庭坚":(1045,1105),"米芾":(1051,1107),"蔡襄":(1012,1067),"赵佶":(1082,1135),
    "范宽":(950,1032),"郭熙":(1023,1085),"李公麟":(1049,1106),"马远":(1140,1225),"夏圭":(1180,1230),
    "李唐":(1066,1150),"张择端":(1085,1145),"赵孟坚":(1199,1264),"牧溪":(1210,1270),
    "赵孟頫":(1254,1322),"黄公望":(1269,1354),"倪瓒":(1301,1374),"王蒙":(1308,1385),"吴镇":(1280,1354),
    "钱选":(1239,1301),"王冕":(1287,1359),
    "沈周":(1427,1509),"文徵明":(1470,1559),"唐寅":(1470,1524),"仇英":(1494,1552),"董其昌":(1555,1636),
    "戴进":(1388,1462),"蓝瑛":(1585,1664),"陈洪绶":(1599,1652),"祝允明":(1461,1527),"王铎":(1592,1652),
    "王时敏":(1592,1680),"王鉴":(1598,1677),"王翚":(1632,1717),"王原祁":(1642,1715),"吴历":(1632,1718),
    "恽寿平":(1633,1690),"石涛":(1642,1707),"弘仁":(1610,1664),"髡残":(1612,1673),
    "金农":(1687,1763),"郑燮":(1693,1765),"李鱓":(1686,1756),"黄慎":(1687,1768),"罗聘":(1733,1799),
    "任伯年":(1840,1895),"虚谷":(1823,1896),"赵之谦":(1829,1884),"吴昌硕":(1844,1927),
    "齐白石":(1864,1957),"黄宾虹":(1865,1955),"徐悲鸿":(1895,1953),"张大千":(1899,1983),
    "傅抱石":(1904,1965),"李可染":(1907,1989),"林风眠":(1900,1991),"刘海粟":(1896,1994),
    "潘天寿":(1897,1971),"徐渭":(1521,1593),"朱耷":(1626,1705),"陈淳":(1483,1544),
    "关山月":(1912,2000),"黎雄才":(1910,2001),"陆俨少":(1909,1993),"石鲁":(1919,1982),
    "黄胄":(1925,1997),"程十发":(1921,2007),"谢稚柳":(1910,1997),"吴冠中":(1919,2010),
    "丰子恺":(1898,1975),"叶浅予":(1907,1995),"蒋兆和":(1904,1986),"李苦禅":(1899,1983),
    "王雪涛":(1903,1982),"于非闇":(1889,1959),"来楚生":(1903,1975),"陆维钊":(1899,1980),
    "沙孟海":(1900,1992),"赵望云":(1906,1977),"陈半丁":(1876,1970),
    "沈尹默":(1883,1971),"白蕉":(1907,1969),"林散之":(1898,1989),"启功":(1912,2005),
    "赵朴初":(1907,2000),"于右任":(1879,1964),
    "范曾":(1938,None),"何家英":(1957,None),"田黎明":(1955,None),"冯远":(1952,None),
    "黄永玉":(1924,2023),"韩美林":(1936,None),"刘国松":(1932,None),
}

def main():
    db = sqlite3.connect(DB)
    rows = db.execute('SELECT name, birth_year, death_year, art_chronology FROM artists ORDER BY name').fetchall()
    log(f'Total artists: {len(rows)}')

    deleted = 0  # 无百科被删除
    fixed = 0   # 修复了幻觉
    total_issues = 0

    for i, (name, birth, death, chron_raw) in enumerate(rows):
        if (i+1) % 50 == 0:
            log(f'Progress: {i+1}/{len(rows)} (deleted={deleted}, fixed={fixed})')

        # 1. 检查百度百科
        if not has_baike(name):
            # 确认非作品库艺术家
            libs = db.execute('SELECT COUNT(*) FROM artwork_libraries WHERE artist_name = ?', (name,)).fetchone()[0]
            if libs == 0:
                db.execute('DELETE FROM artists WHERE name = ?', (name,))
                deleted += 1
                log(f'  DELETE {name}: no Baidu Baike, no library')
                continue

        # 2. 检查年谱幻觉
        try:
            chron = json.loads(chron_raw) if chron_raw else []
        except:
            continue

        if not chron: continue

        issues = check_chronology_hallucinations(chron, name, birth, death)
        if issues:
            cleaned = clean_chronology(chron, issues)
            if len(cleaned) < len(chron):
                db.execute('UPDATE artists SET art_chronology = ? WHERE name = ?',
                           (json.dumps(cleaned, ensure_ascii=False), name))
                fixed += 1
                total_issues += len(issues)
                log(f'  FIX {name}: {len(chron)}->{len(cleaned)} ({len(issues)} issues)')

        time.sleep(0.3)  # 避免请求过快

    db.commit()
    remaining = db.execute('SELECT COUNT(*) FROM artists').fetchone()[0]
    log(f'\n{"="*50}')
    log(f'Complete!')
    log(f'  Deleted (no Baidu): {deleted}')
    log(f'  Fixed (hallucinations): {fixed}')
    log(f'  Total issues removed: {total_issues}')
    log(f'  Remaining artists: {remaining}')
    db.close()

if __name__ == '__main__':
    main()
