"""
baike_skill.py — 灵活的百度百科解析器
自动识别章节结构，映射到数据库字段，适用于任意艺术家
"""
from bs4 import BeautifulSoup
import urllib.request, urllib.parse, urllib.error
import re, json

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
           'Accept': 'text/html', 'Accept-Language': 'zh-CN,zh;q=0.9'}

# 百科章节标题 → DB字段 映射表
SECTION_MAP = [
    (['人物生平','生平','传记','早年经历','仕途','为官','晚年','归隐'], 'biography_sections'),
    (['艺术年表','艺术分期','年表','创作历程'], 'chronology_sections'),
    (['主要作品','代表作品','作品','绘画作品','木雕作品','书法作品'], 'works_sections'),
    (['创作特点','绘画艺术','绘画风格','篆刻书法','篆刻','书法艺术','艺术特色','艺术风格','风格','笔墨','技法'], 'art_style_sections'),
    (['人物评价','历史评价','评价','艺术成就'], 'evaluation_sections'),
    (['人际关系','师徒','人物交往','院校任教','社会关系','师承','师生'], 'relations_sections'),
    (['轶事典故','典故','轶事','趣闻','逸事'], 'anecdotes_sections'),
    (['获奖记录','获奖','荣誉','奖项','获奖记录'], 'awards_sections'),
    (['后世影响','影响','地位','贡献','纪念','邮票纪念','纪念活动','故居展示','人物故居'], 'influence_sections'),
    (['出版著作','著作','著述','文集','画册','专著','出版物'], 'publications_sections'),
    (['作品拍卖','拍卖','市场'], 'auction_sections'),
    (['家庭生活','家庭','家族','婚姻'], 'family_sections'),
]

def clean(text):
    """清理百科文本"""
    t = re.sub(r'\[\d+(?:[-,/]\d+)*\]', '', text)
    t = re.sub(r']', '', t)
    t = t.replace('　', ' ').strip()
    t = re.sub(r'  +', ' ', t)
    return t

def fetch(name):
    """获取百度百科页面"""
    for url in [f"https://baike.baidu.com/item/{urllib.parse.quote(name)}",
                f"https://baike.baidu.com/item/{urllib.parse.quote(name)}/1"]:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    html = r.read().decode('utf-8', errors='replace')
                    if len(html) > 5000 and name in html:
                        return BeautifulSoup(html, 'lxml')
        except: pass
    return None

def parse_basic_info(soup):
    """解析基本信息栏"""
    raw = {}
    c = soup.select_one('[class*="J-basic-info"]')
    if c:
        for dt in c.select('dt'):
            k = dt.get_text(strip=True).replace('\xa0',' ').replace('\xa0',' ')
            if not k: continue
            dd = dt.find_next('dd')
            if dd: raw[k] = dd.get_text(strip=True).replace('\xa0',' ')
    return raw

def parse_sections(soup):
    """按章节结构解析百科正文, 子章节归入父章节"""
    sections = []
    current = {'title': '概述', 'level': 'h2', 'content': []}
    parent_h2 = None  # 当前 h2 父章节

    for el in soup.select('[class*="paraTitle"], [class*="para_"]'):
        cls = ' '.join(el.get('class', []))

        if 'paraTitle' in cls and 'level' in cls:
            level = 'h2' if 'level-1' in cls else 'h3'
            title = el.get_text(strip=True).replace('播音','').replace('编辑','').strip()

            if level == 'h2':
                if current['content']:
                    sections.append(current)
                current = {'title': title, 'level': 'h2', 'content': []}
                parent_h2 = title
            else:
                # h3: 也作为独立章节，但标记父章节
                if current['content']:
                    sections.append(current)
                current = {'title': title, 'level': 'h3', 'content': [], 'parent': parent_h2}
        elif 'para_' in cls:
            text = clean(el.get_text(strip=True))
            if text and len(text) > 10:
                current['content'].append({'type': 'text', 'text': text})

    if current['content']:
        sections.append(current)
    return sections

def map_section(title, content_texts):
    """将百科章节映射到数据库字段"""
    for keywords, db_field in SECTION_MAP:
        if any(kw in title for kw in keywords):
            return db_field
    return None

def extract_life_chronology(sections, birth, death):
    """从人物生平章节提取人生年谱"""
    events = []
    bio_text = ''
    for sec in sections:
        if any(kw in sec['title'] for kw in ['人物生平','生平']):
            for item in sec['content']:
                if item['type'] == 'text' and len(item['text']) > 20:
                    bio_text += item['text'] + '\n'
            break

    seen = set()
    for m in re.finditer(r'(?:(?:^|\n|。|；)\s*)?(\d{4})年[，,\s]*([^。；\n]{15,200}?)(?=[。；\n]|$)', bio_text):
        y = int(m.group(1)); content = m.group(2).strip()
        if y in seen: continue
        if birth and y < birth - 5: continue
        if death and y > death + 2: continue
        seen.add(y)
        loc = ''
        lm = re.search(r'(?:在|于|至|赴|到|居|任|迁|移)([一-鿿]{2,6}(?:市|县|府|州|镇|村|乡)?)', content)
        if lm: loc = lm.group(1)
        events.append({'year':y,'event':clean(content[:40]),'location':loc,'description':clean(content[:250])})

    if birth and not any(e['year']==birth for e in events):
        events.append({'year':birth,'event':'出生','location':'','description':''})
    if death and not any(e['year']==death for e in events):
        events.append({'year':death,'event':'逝世','location':'','description':''})
    events.sort(key=lambda e: e['year'])
    return events

def extract_art_chronology(soup, sections, birth, death):
    """从表格和艺术年表章节提取作品年谱"""
    events = []
    seen = set()

    # 从表格提取
    for table in soup.select('table, [class*="table"]'):
        for row in table.select('tr'):
            cells = row.select('td, th')
            if len(cells) < 2: continue
            fc = clean(cells[0].get_text())
            ym = re.search(r'(\d{4})', fc)
            if not ym: continue
            y = int(ym.group(1))
            if birth and y < birth - 5: continue
            if death and y > death + 2: continue
            et = clean(cells[1].get_text()) if len(cells) > 1 else ''
            key = f'{y}_{et[:20]}'
            if key in seen: continue
            seen.add(key)
            desc = ' '.join(clean(c.get_text()) for c in cells[1:4])
            events.append({'year':y,'event':et[:50] or fc,'location':'','description':desc[:250]})

    # 从艺术年表章节补充
    for sec in sections:
        if any(kw in sec['title'] for kw in ['艺术年表','艺术分期']):
            for item in sec['content']:
                if item['type'] == 'text':
                    for m in re.finditer(r'(\d{4})年[^。；]{10,200}', item['text']):
                        y = int(m.group(1))
                        key = f'{y}_text'
                        if key not in seen:
                            seen.add(key)
                            events.append({'year':y,'event':clean(m.group(0)[:40]),'location':'','description':clean(m.group(0)[:250])})

    events.sort(key=lambda e: e['year'])
    return events

def extract_character_relations(sections):
    """从人际关系章节及其子章节提取人物关系"""
    relations = []
    for sec in sections:
        title = sec['title']
        # 匹配人际关系章节（h2）及其子章节（h3）
        mapped = map_section(title, [])
        if mapped != 'relations_sections':
            continue
        for item in sec['content']:
            if item['type'] != 'text':
                continue
            text = item['text']
            # 按句号拆分
            for sent in re.split(r'[。；]', text):
                sent = sent.strip()
                if len(sent) < 10: continue
                # 提取第一个人名作为关系主体
                names = re.findall(r'([一-鿿]{2,4})', sent[:50])
                if names:
                    relations.append({
                        'name': names[0],
                        'relationship': title,
                        'description': clean(sent[:200])
                    })
    return relations[:30]

def extract_anecdotes(sections):
    """从轶事典故章节提取"""
    anecdotes = []
    for sec in sections:
        if not any(kw in sec['title'] for kw in ['轶事','典故','轶事典故']):
            continue
        for item in sec['content']:
            if item['type'] == 'text' and len(item['text']) > 30:
                anecdotes.append({
                    'title': item['text'][:30],
                    'content': clean(item['text'][:500])
                })
    return anecdotes

def get_summary(soup):
    """提取概述（跳过密集年表的段落）"""
    paras = soup.select('.J-summary [class*="para_"]')
    if not paras: return ''
    parts = []
    for i, p in enumerate(paras):
        t = clean(p.get_text(strip=True))
        if len(t) < 15: continue
        # 检测年表段落
        if i >= 2 and len(t) > 100:
            years = len(re.findall(r'\d{4}年', t[:300]))
            if years >= 5: break
        parts.append(t)
        if len(''.join(parts)) > 1200: break
    return '\n'.join(parts)[:1500]

def get_alias(raw, soup):
    """提取字号"""
    alias = []
    for k in ['字','号','别号','自号','别名','本名']:
        v = raw.get(k,'').strip()
        if v: alias.append(f'{k}:{v}')
    if not alias:
        txt = ''
        for p in (soup.select('.J-summary [class*="para_"]') or [])[:2]:
            t = p.get_text(strip=True)
            if len(t) > 20: txt += t
        zm = re.search(r'字([一-鿿]{1,6})[，,\s]*(?:又字|更字|后改名.*?字|号)', txt)
        if zm: alias.append(f'字:{zm.group(1)}')
        hm = re.search(r'号([一-鿿]{2,12}(?:山人|居士|道人|老人|主人|先生|散人|翁|子|客)?)', txt)
        if hm: alias.append(f'号:{hm.group(1)}')
    return '; '.join(alias)[:200]

def get_dynasty(raw, birth):
    """获取朝代"""
    for k in ['所处时代','朝代','时代']:
        if raw.get(k): return raw[k][:20]
    # 按生年推断
    if birth:
        if birth >= 1949: return '当代'
        if birth >= 1912: return '近现代'
        if birth >= 1840: return '近代'
        if birth >= 1644: return '清代'
        if birth >= 1368: return '明代'
        if birth >= 1271: return '元代'
        if birth >= 960: return '宋代'
        if birth >= 618: return '唐代'
        if birth >= 420: return '晋代'
        if birth >= 220: return '汉代'
    return ''

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

def parse(name):
    """主入口：解析任意艺术家的百度百科"""
    soup = fetch(name)
    if not soup: return None

    raw = parse_basic_info(soup)
    sections = parse_sections(soup)

    # 生卒年
    bs = ds = ''
    for k in ['出生日期','出生时间','生年','出生']:
        if raw.get(k): bs = raw[k]; break
    for k in ['逝世日期','去世时间','卒年','逝世']:
        if raw.get(k): ds = raw[k]; break
    birth = int(m.group(1)) if (m := re.search(r'(\d{4})', bs)) else None
    death = int(m.group(1)) if (m := re.search(r'(\d{4})', ds)) else None
    if birth is None and name in KNOWN_YEARS: birth = KNOWN_YEARS[name][0]
    if death is None and name in KNOWN_YEARS: death = KNOWN_YEARS[name][1]

    # 基础字段
    info = {
        'alias': get_alias(raw, soup),
        'dynasty': get_dynasty(raw, birth),
        'hometown': raw.get('出生地', raw.get('籍贯',''))[:100],
        'birth_year': birth, 'death_year': death,
        'nationality': raw.get('国籍','')[:20] or '中国',
        'occupation': raw.get('职业', raw.get('职    业',''))[:100],
        'main_achievements': raw.get('主要成就','')[:500],
        'summary': get_summary(soup),
    }
    ws = raw.get('代表作品','')
    info['masterpieces'] = json.dumps(
        [w.strip() for w in re.split(r'[、，,《》\s]+', ws) if len(w.strip()) > 1 and w.strip() != '等'][:10],
        ensure_ascii=False) if ws else '[]'

    # 年谱
    info['art_chronology'] = json.dumps(extract_life_chronology(sections, birth, death), ensure_ascii=False)
    info['artwork_chronology'] = json.dumps(extract_art_chronology(soup, sections, birth, death), ensure_ascii=False)

    # 按章节映射字段
    section_texts = {}
    for sec in sections:
        texts = [item['text'] for item in sec['content'] if item['type'] == 'text' and len(item['text']) > 20]
        if not texts: continue
        db_field = map_section(sec['title'], texts)
        if db_field:
            section_texts[db_field] = section_texts.get(db_field, []) + texts

    # 艺术特色
    style = []
    for k in ['art_style_sections']:
        if k in section_texts:
            style.extend(section_texts[k])
    info['art_style'] = '\n\n'.join(style)[:3000]

    # 历史评价
    evals = []
    for k in ['evaluation_sections']:
        if k in section_texts:
            evals.extend(section_texts[k])
    info['historical_evaluation'] = '\n\n'.join(evals)[:2000]

    # 后世影响
    influence = []
    for k in ['influence_sections']:
        if k in section_texts:
            influence.extend(section_texts[k])
    info['influence'] = '\n\n'.join(influence)[:2000]

    # 人物关系
    relations = extract_character_relations(sections)
    info['character_relations'] = json.dumps(relations[:20], ensure_ascii=False)

    # 轶事典故
    anecdotes = extract_anecdotes(sections)
    info['anecdotes'] = json.dumps(anecdotes[:10], ensure_ascii=False)

    # 出版著作
    pubs = []
    for k in ['publications_sections']:
        if k in section_texts:
            pubs.extend(section_texts[k])
    info['published_works'] = json.dumps([{'title': t[:60], 'description': t[:200]} for t in pubs[:10]], ensure_ascii=False)

    return info


if __name__ == '__main__':
    result = parse('齐白石')
    if result:
        print('=== BASIC INFO ===')
        for k in ['alias','dynasty','hometown','birth_year','death_year','occupation','nationality']:
            print(k + ':', result.get(k))
        for label, key in [('summary','summary'),('art_style','art_style'),
                           ('historical_evaluation','historical_evaluation'),('influence','influence')]:
            print(label + ':', len(result.get(key,'')), 'chars')
        for key in ['art_chronology','artwork_chronology','character_relations','anecdotes','published_works']:
            val = json.loads(result.get(key, '[]'))
            print(key + ':', len(val), 'items')
    else:
        print('FAILED')
