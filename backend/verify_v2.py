"""
保守版年谱校验 —— 仅标记明确AI幻觉，不自动修改
用法: python3 verify_v2.py [--start N] [--limit M]

标记规则:
1. 事件年在出生前或去世后
2. 3岁前有"创作/出版/举办"等不可能事件
3. 1850年前出生的艺术家有"赴日/赴欧美"事件
4. "创作《XX图》"占比>30%且百科无对应条目
5. 百科文本<200字符(数据来源不可靠)
"""
import sqlite3, json, re, time, sys, os
import urllib.request, urllib.parse, urllib.error

DB_PATH = os.environ.get('DB_PATH', '/opt/molin-wiki/backend/data/calligraphy.db')
REPORT_PATH = os.environ.get('REPORT_PATH', '/opt/molin-wiki/backend/data/chronology_audit_v2.json')
LOG_PATH = '/tmp/verify_v2.log'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

# 明确编造的关键词
FABRICATED_PATTERNS = [
    (re.compile(r'赴[日欧美法德英]'), '赴国外'),
    (re.compile(r'出[国訪访]'), '出国'),
    (re.compile(r'欧洲.*考察|考察.*欧洲'), '欧洲考察'),
    (re.compile(r'日本.*交流|交流.*日本'), '日本交流'),
    (re.compile(r'美国.*展览|展览.*美国'), '美国展览'),
]

def log(msg: str):
    print(msg)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def fetch_baike(name: str) -> tuple[str | None, str]:
    """获取百度百科, 返回 (html, url)"""
    encoded = urllib.parse.quote(name)
    for url in [
        f"https://baike.baidu.com/item/{encoded}",
        f"https://baike.baidu.com/item/{encoded}/1",
    ]:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    html = resp.read().decode('utf-8', errors='replace')
                    if len(html) > 3000:
                        return html, url
        except:
            pass
    return None, ''

def parse_baike(html: str) -> dict:
    """提取百科关键信息"""
    info = {}
    # 基本资料
    items = re.findall(
        r'class="basicInfo-item[^"]*name[^"]*"[^>]*>(.*?)<.*?'
        r'class="basicInfo-item[^"]*value[^"]*"[^>]*>(.*?)</dd>',
        html, re.DOTALL
    )
    for nh, vh in items:
        k = re.sub(r'<[^>]+>', '', nh).strip().replace('\xa0', ' ')
        v = re.sub(r'<[^>]+>', '', vh).strip()
        info[k] = v

    # 正文
    paras = re.findall(r'class="para[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    text = ''
    for p in paras:
        t = re.sub(r'<[^>]+>', '', p).strip()
        t = re.sub(r'\[\d+\]', '', t)
        if t and len(t) > 10:
            text += t + '\n'

    # 提取百科中的年份
    years_in_text = set()
    for m in re.finditer(r'(\d{4})年', text):
        years_in_text.add(int(m.group(1)))

    info['_text'] = text
    info['_text_len'] = len(text)
    info['_years'] = sorted(years_in_text)
    return info

def classify_flags(ai_chron: list[dict], baike_info: dict, birth: int | None, death: int | None, name: str) -> dict:
    """分类标记每条AI年谱条目"""
    text = baike_info.get('_text', '')
    text_years = baike_info.get('_years', [])

    flags = {
        'impossible_age': [],     # 不可能年龄的事件
        'after_death': [],         # 去世后的事件
        'fabricated_abroad': [],   # 编造的出国
        'generic_painting': [],    # 泛型创作条目
        'no_baike_match': [],      # 百科中无任何印证
        'total': len(ai_chron),
    }

    generic_paint_count = 0
    for entry in ai_chron:
        y = entry.get('year')
        ev = entry.get('event', '')
        desc = entry.get('description', '')
        combined = f"{ev} {desc}"

        try: year_int = int(y) if y else None
        except: year_int = None

        # 1. 不可能年龄 (3岁前非出生事件)
        if birth and year_int and year_int - birth < 3 and year_int >= birth:
            if '出生' not in ev and '诞' not in ev:
                flags['impossible_age'].append(entry)

        # 2. 去世后的事件
        if death and year_int and year_int > death:
            flags['after_death'].append(entry)

        # 3. 编造的出国 (1850年前的艺术家)
        if birth and birth < 1850:
            for pat, label in FABRICATED_PATTERNS:
                if pat.search(combined):
                    flags['fabricated_abroad'].append({**entry, 'pattern': label})

        # 4. 统计泛型"创作《XX图》"
        if '创作《' in combined and '图' in combined:
            generic_paint_count += 1

    # 5. 检查百科印证度
    if len(text) < 200:
        flags['baike_insufficient'] = True
    else:
        # 对于较新的艺术家(birth > 1900)，要求更高
        threshold = 0.3 if (birth and birth > 1900) else 0.15
        verified = 0
        for entry in ai_chron:
            ev = entry.get('event', '')
            keywords = re.findall(r'[一-鿿]{3,}', ev)
            if keywords and any(kw in text for kw in keywords[:2]):
                verified += 1
        flags['baike_verified_ratio'] = verified / len(ai_chron) if ai_chron else 0
        flags['baike_verified_count'] = verified

    # 6. 泛型创作占比过高
    if generic_paint_count > len(ai_chron) * 0.3 and len(ai_chron) > 10:
        flags['generic_paint_ratio'] = generic_paint_count / len(ai_chron)

    # 综合判断是否可疑
    issue_count = (
        len(flags['impossible_age']) +
        len(flags['after_death']) +
        len(flags['fabricated_abroad'])
    )
    flags['suspicious'] = issue_count > 0
    flags['suspicious_count'] = issue_count

    return flags

def main():
    start = 0
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == '--start' and i + 1 < len(sys.argv):
            start = int(sys.argv[i + 1])
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    db = sqlite3.connect(DB_PATH)
    rows = db.execute(
        'SELECT name, birth_year, death_year, art_chronology FROM artists '
        'WHERE art_chronology IS NOT NULL AND art_chronology != "" AND art_chronology != "[]" '
        'ORDER BY name'
    ).fetchall()
    db.close()

    # Resume from saved state
    saved_results = []
    if os.path.exists(REPORT_PATH) and start == 0:
        try:
            with open(REPORT_PATH, encoding='utf-8') as f:
                saved_results = json.load(f)
            saved_names = {r['name'] for r in saved_results}
            rows = [r for r in rows if r[0] not in saved_names]
            log(f'Resuming: {len(saved_results)} already processed, {len(rows)} remaining')
        except:
            pass

    if limit:
        rows = rows[:limit]
    total = len(rows)

    results = list(saved_results)
    for i, (name, birth, death, chron_raw) in enumerate(rows):
        try:
            ai_chron = json.loads(chron_raw)
        except:
            continue

        log(f'\n[{i+1}/{total}] {name} ({birth}-{death}) — {len(ai_chron)}条')

        # Fetch Baidu
        html, url = fetch_baike(name)
        if not html:
            result = {'name': name, 'birth': birth, 'death': death,
                       'ai_count': len(ai_chron), 'status': 'baike_not_found'}
            results.append(result)
            log(f'  => 百科未找到')
            continue

        # Parse and classify
        baike_info = parse_baike(html)
        flags = classify_flags(ai_chron, baike_info, birth, death, name)

        result = {
            'name': name,
            'birth': birth,
            'death': death,
            'ai_count': len(ai_chron),
            'status': 'suspicious' if flags['suspicious'] else 'ok',
            'baike_text_len': baike_info['_text_len'],
            'baike_years_count': len(baike_info.get('_years', [])),
            'flags': {
                'impossible_age': len(flags['impossible_age']),
                'after_death': len(flags['after_death']),
                'fabricated_abroad': len(flags['fabricated_abroad']),
                'baike_verified_ratio': round(flags.get('baike_verified_ratio', 0), 2),
                'generic_paint_ratio': round(flags.get('generic_paint_ratio', 0), 2),
                'baike_insufficient': flags.get('baike_insufficient', False),
            },
            'flagged_items': [],
        }

        # 记录被标记的具体条目
        for cat in ['impossible_age', 'after_death', 'fabricated_abroad']:
            for item in flags[cat]:
                result['flagged_items'].append({
                    'category': cat,
                    'year': item.get('year'),
                    'event': item.get('event', '')[:80],
                    'pattern': item.get('pattern', ''),
                })

        results.append(result)

        status_icon = '⚠️' if flags['suspicious'] else '✅'
        log(f'  {status_icon} 年龄异常:{len(flags["impossible_age"])} 去世后:{len(flags["after_death"])} '
            f'出国编造:{len(flags["fabricated_abroad"])} 百科印证率:{flags.get("baike_verified_ratio", 0):.0%}')

        # Save every 10
        if (i + 1) % 10 == 0:
            with open(REPORT_PATH, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(1.5)

    # Final save
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    ok = sum(1 for r in results if r.get('status') == 'ok')
    susp = sum(1 for r in results if r.get('status') == 'suspicious')
    nf = sum(1 for r in results if r.get('status') == 'baike_not_found')
    total_impossible = sum(r['flags']['impossible_age'] for r in results)
    total_death = sum(r['flags']['after_death'] for r in results)
    total_abroad = sum(r['flags']['fabricated_abroad'] for r in results)

    log(f'\n{"="*60}')
    log(f'校验完成! 总计: {len(results)}')
    log(f'  ✅ 通过: {ok}')
    log(f'  ⚠️  可疑: {susp}')
    log(f'  ❓ 百科未收录: {nf}')
    log(f'  年龄异常: {total_impossible}条')
    log(f'  去世后事件: {total_death}条')
    log(f'  编造出国: {total_abroad}条')
    log(f'  报告: {REPORT_PATH}')

if __name__ == '__main__':
    main()
