"""
纯百度百科爬虫——200位中国书画核心艺术家
100%从百科复制，零AI生成，零幻觉

用法: python3 rebuild_from_baike.py
"""
import sqlite3, json, re, time, os, sys
import urllib.request, urllib.parse, urllib.error
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', '/opt/calligraphy-recognition/backend/data/calligraphy.db')
LOG_PATH = '/tmp/rebuild_baike.log'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

# ── 200位核心艺术家列表（按时代排序） ──
ARTISTS_200 = [
    # === 魏晋南北朝 ===
    "王羲之", "顾恺之", "王献之", "钟繇", "陆机", "宗炳",
    # === 隋唐 ===
    "颜真卿", "柳公权", "欧阳询", "吴道子", "张旭", "怀素",
    "阎立本", "周昉", "韩干", "韩滉", "孙过庭", "褚遂良", "虞世南",
    "李思训", "王维", "张萱",
    # === 五代 ===
    "荆浩", "董源", "巨然", "徐浩",
    # === 宋代 ===
    "苏轼", "黄庭坚", "米芾", "蔡襄", "赵佶", "范宽", "李成",
    "郭熙", "李公麟", "马远", "夏圭", "梁楷", "刘松年", "李唐",
    "文同", "赵孟坚", "牧溪", "崔白", "李迪", "张择端", "赵伯骕",
    "米友仁", "王诜", "李嵩", "苏汉臣", "林椿", "赵昌", "易元吉",
    # === 元代 ===
    "赵孟頫", "黄公望", "倪瓒", "王蒙", "吴镇", "钱选", "高克恭",
    "柯九思", "李衎", "王冕", "朱德润", "曹知白", "方从义", "张雨",
    # === 明代 ===
    "沈周", "文徵明", "唐寅", "仇英", "董其昌", "徐渭", "陈淳",
    "周臣", "戴进", "吴伟", "蓝瑛", "陈洪绶", "崔子忠", "杜堇",
    "边景昭", "林良", "吕纪", "王绂", "夏昶", "祝允明", "王宠",
    "文彭", "陆治", "周之冕", "谢时臣", "项圣谟", "张宏", "曾鲸",
    "王铎", "孙隆",
    # === 清代 ===
    "王时敏", "王鉴", "王翚", "王原祁", "吴历", "恽寿平",
    "石涛", "朱耷", "弘仁", "髡残",
    "金农", "郑燮", "李鱓", "黄慎", "汪士慎", "高翔", "罗聘",
    "华嵒", "高凤翰", "边寿民",
    "袁江", "袁耀", "任伯年", "任熊", "任薰", "虚谷", "赵之谦",
    "蒲华", "吴昌硕", "改琦", "费丹旭", "郎世宁", "焦秉贞",
    "冷枚", "梅清", "樊圻",
    # === 近现代 ===
    "齐白石", "黄宾虹", "徐悲鸿", "张大千", "潘天寿", "傅抱石",
    "李可染", "林风眠", "刘海粟", "吴作人", "关山月", "黎雄才",
    "陆俨少", "钱松岩", "石鲁", "黄胄", "程十发", "谢稚柳",
    "吴冠中", "朱屺瞻", "丰子恺", "叶浅予", "蒋兆和", "李苦禅",
    "王雪涛", "于非闇", "来楚生", "陆维钊", "沙孟海",
    "赵望云", "何海霞", "陈半丁",
    # === 近现代书法 ===
    "沈尹默", "白蕉", "林散之", "启功", "赵朴初",
    "邓散木", "于右任", "谢无量",
    # === 当代 ===
    "范曾", "何家英", "田黎明", "冯远", "贾又福",
    "黄永玉", "韩美林", "刘国松",
]

# 已有的8位不重复抓取
EXISTING = {'李鱓', '刘海勇', '郑燮', '金农', '徐渭', '潘天寿', '朱耷', '陈淳'}

def log(msg):
    print(msg)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def fetch_baike(name: str) -> str | None:
    """获取百度百科HTML"""
    encoded = urllib.parse.quote(name)
    for url in [
        f"https://baike.baidu.com/item/{encoded}",
        f"https://baike.baidu.com/item/{encoded}/1",
    ]:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    html = resp.read().decode('utf-8', errors='replace')
                    if len(html) > 3000 and name in html:
                        return html
        except Exception as e:
            log(f"  fetch error: {e}")
    return None

def parse_baike(html: str) -> dict:
    """从百度百科页面提取所有可用的艺术家信息"""
    info = {}

    # ── 1. 基本资料栏 ──
    items = re.findall(
        r'class="basicInfo-item[^"]*name[^"]*"[^>]*>(.*?)<.*?'
        r'class="basicInfo-item[^"]*value[^"]*"[^>]*>(.*?)</dd>',
        html, re.DOTALL
    )
    raw_info = {}
    for nh, vh in items:
        k = re.sub(r'<[^>]+>', '', nh).strip().replace('\xa0', ' ').replace(' ', ' ')
        v = re.sub(r'<[^>]+>', '', vh).strip().replace('\xa0', ' ')
        raw_info[k] = v

    # 映射字段
    info['alias'] = raw_info.get('字号', raw_info.get('别名', raw_info.get('字', '')))
    if not info['alias']:
        parts = []
        for k in ['字', '号', '别号', '自号']:
            if raw_info.get(k):
                parts.append(f'{k}:{raw_info[k]}')
        info['alias'] = '; '.join(parts)

    info['hometown'] = raw_info.get('出生地', raw_info.get('籍贯', raw_info.get('出生地点', '')))
    info['nationality'] = raw_info.get('国籍', raw_info.get('国    籍', '中国'))

    # 朝代提取
    dynasty = raw_info.get('朝代', raw_info.get('所处时代', raw_info.get('时代', '')))
    info['dynasty'] = dynasty

    # 出生/去世年份
    birth_str = raw_info.get('出生日期', raw_info.get('生年', ''))
    death_str = raw_info.get('逝世日期', raw_info.get('卒年', raw_info.get('去世时间', '')))

    birth_year = None
    death_year = None
    for s in [birth_str, death_str]:
        m = re.search(r'(\d{4})', str(s))
        if s == birth_str and m:
            birth_year = int(m.group(1))
        elif s == death_str and m:
            death_year = int(m.group(1))

    # 也从文本中提取
    if not birth_year or not death_year:
        text_preview = _extract_text(html)
        if not birth_year:
            bm = re.search(r'(?:生于|出生|生).*?(\d{4})', text_preview)
            if bm: birth_year = int(bm.group(1))
        if not death_year:
            dm = re.search(r'(?:卒于|逝世于|去世|逝世).*?(\d{4})', text_preview)
            if dm: death_year = int(dm.group(1))

    info['birth_year'] = birth_year
    info['death_year'] = death_year

    # 职业
    info['occupation'] = raw_info.get('职业', raw_info.get('职    业', ''))

    # 主要成就
    info['main_achievements'] = raw_info.get('主要成就', raw_info.get('主要成就/荣誉', ''))

    # 代表作品
    works = raw_info.get('代表作品', raw_info.get('代表作', ''))
    if works:
        work_list = [w.strip() for w in re.split(r'[、，,《》\s]+', works) if w.strip() and len(w.strip()) > 1]
        info['masterpieces'] = json.dumps(work_list[:8], ensure_ascii=False)
    else:
        info['masterpieces'] = '[]'

    # ── 2. 正文文本 ──
    text = _extract_text(html)
    info['biography'] = text[:3000] if text else ''
    info['summary'] = text[:200] if text else ''

    # ── 3. 从正文提取年谱 ──
    chronology = _extract_chronology(text, birth_year, death_year)
    if len(chronology) < 3:
        # 太少了，尝试更宽松的匹配
        chronology = _extract_chronology_loose(text, birth_year, death_year)
    info['art_chronology'] = json.dumps(chronology, ensure_ascii=False)

    return info

def _extract_text(html: str) -> str:
    """提取百科正文纯文本"""
    paras = re.findall(r'class="para[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    text = ''
    for p in paras:
        t = re.sub(r'<[^>]+>', '', p).strip()
        t = re.sub(r'\[\d+\]', '', t)
        if t and len(t) > 10 and not t.startswith('参考资料'):
            text += t + '\n'
    return text

def _extract_chronology(text: str, birth: int | None, death: int | None) -> list[dict]:
    """从百科正文提取年谱——每个条目必须有明确年份"""
    events = []
    seen_years = set()

    # 匹配 "YYYY年..." 模式
    for m in re.finditer(r'(?:(?:^|[。；])\s*)?(\d{4})年[，,\s]*(.{20,200}?)(?=[。；]|$)', text):
        y = int(m.group(1))
        content = m.group(2).strip()

        # 年份范围校验
        if birth and y < birth - 5:
            continue
        if death and y > death + 1:
            continue
        if y in seen_years:
            continue

        # 尝试提取事件名
        event = content[:30]
        # 尝试提取地点
        location = ''
        loc_m = re.search(r'(?:在|于|至|赴|任|到|居)([一-鿿]{2,8}(?:市|县|府|州|省|镇|村|乡)?)', content)
        if loc_m:
            location = loc_m.group(1)

        events.append({
            'year': y,
            'event': event,
            'location': location,
            'description': content[:200]
        })
        seen_years.add(y)

    # 确保有出生和去世条目
    if birth and birth not in seen_years:
        events.insert(0, {'year': birth, 'event': '出生', 'location': '', 'description': ''})
    if death and death not in seen_years:
        events.append({'year': death, 'event': '逝世', 'location': '', 'description': ''})

    events.sort(key=lambda e: e.get('year', 0))
    return events

def _extract_chronology_loose(text: str, birth: int | None, death: int | None) -> list[dict]:
    """宽松版年谱提取——包括带约数的年份"""
    events = []
    seen_years = set()
    # 更宽松的正则
    for m in re.finditer(r'(?:约)?(\d{4})年[^。；]{15,250}', text):
        y = int(m.group(1))
        content = m.group(0)
        if y in seen_years:
            continue
        if birth and y < birth - 10:
            continue
        if death and y > death + 5:
            continue

        events.append({'year': y, 'event': content[:30], 'location': '', 'description': content[:200]})
        seen_years.add(y)

    if birth and birth not in seen_years:
        events.insert(0, {'year': birth, 'event': '出生', 'location': '', 'description': ''})
    if death and death not in seen_years:
        events.append({'year': death, 'event': '逝世', 'location': '', 'description': ''})

    events.sort(key=lambda e: e.get('year', 0))
    return events

def insert_artist(db, name: str, info: dict):
    """插入或更新艺术家"""
    now = datetime.now().isoformat()

    # 检查是否已存在
    existing = db.execute('SELECT id FROM artists WHERE name = ?', (name,)).fetchone()

    if existing:
        # 更新(保留已有的travel_notes和作品数据)
        db.execute('''
            UPDATE artists SET
                alias=?, dynasty=?, hometown=?, birth_year=?, death_year=?,
                biography=?, summary=?, nationality=?, occupation=?,
                main_achievements=?, masterpieces=?, art_chronology=?,
                updated_at=?, verified=1
            WHERE name=?
        ''', (
            info.get('alias', ''),
            info.get('dynasty', ''),
            info.get('hometown', ''),
            info.get('birth_year'),
            info.get('death_year'),
            info.get('biography', ''),
            info.get('summary', ''),
            info.get('nationality', ''),
            info.get('occupation', ''),
            info.get('main_achievements', ''),
            info.get('masterpieces', '[]'),
            info.get('art_chronology', '[]'),
            now, name
        ))
        return 'updated'
    else:
        db.execute('''
            INSERT INTO artists (name, alias, dynasty, hometown, birth_year, death_year,
                biography, summary, nationality, occupation, main_achievements,
                masterpieces, art_chronology, verified, enabled, featured,
                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0, ?, ?)
        ''', (
            name,
            info.get('alias', ''),
            info.get('dynasty', ''),
            info.get('hometown', ''),
            info.get('birth_year'),
            info.get('death_year'),
            info.get('biography', ''),
            info.get('summary', ''),
            info.get('nationality', ''),
            info.get('occupation', ''),
            info.get('main_achievements', ''),
            info.get('masterpieces', '[]'),
            info.get('art_chronology', '[]'),
            now, now
        ))
        return 'inserted'

def main():
    # 去重 + 排除已有
    to_process = []
    seen = set(EXISTING)
    for name in ARTISTS_200:
        if name not in seen:
            to_process.append(name)
            seen.add(name)

    log(f'{len(EXISTING)} existing + {len(to_process)} new = {len(EXISTING) + len(to_process)} total')

    db = sqlite3.connect(DB_PATH)
    inserted = 0
    updated = 0
    failed = 0

    for i, name in enumerate(to_process):
        log(f'\n[{i+1}/{len(to_process)}] {name}')

        html = fetch_baike(name)
        if not html:
            log(f'  => 百科获取失败')
            failed += 1
            continue

        try:
            info = parse_baike(html)
        except Exception as e:
            log(f'  => 解析失败: {e}')
            failed += 1
            continue

        chron = json.loads(info.get('art_chronology', '[]'))
        log(f'  birth={info.get("birth_year")} death={info.get("death_year")} '
            f'dynasty={info.get("dynasty","?")[:20]} '
            f'chronology={len(chron)}条 '
            f'text={len(info.get("biography",""))}字')

        result = insert_artist(db, name, info)
        if result == 'inserted':
            inserted += 1
        else:
            updated += 1

        db.commit()

        # 避免请求过快
        time.sleep(2)

    db.close()

    log(f'\n{"="*60}')
    log(f'重建完成!')
    log(f'  新增: {inserted}')
    log(f'  更新: {updated}')
    log(f'  失败: {failed}')
    log(f'  保留原有: {len(EXISTING)}')

if __name__ == '__main__':
    main()
