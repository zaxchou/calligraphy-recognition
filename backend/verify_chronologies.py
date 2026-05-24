"""
批量校验艺术家年谱 —— 逐位从百度百科提取真实数据
用法: python verify_chronologies.py [--start N] [--limit M] [--fix]
"""
import sqlite3, json, re, time, sys, os
import urllib.request
import urllib.error

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'calligraphy.db'))
REPORT_PATH = os.environ.get('REPORT_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'chronology_audit.json'))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

def fetch_baike(name: str) -> str | None:
    """获取百度百科页面HTML"""
    import urllib.parse
    encoded = urllib.parse.quote(name)
    url = f"https://baike.baidu.com/item/{encoded}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                html = resp.read().decode('utf-8', errors='replace')
                if len(html) > 5000 and name in html:
                    return html
    except Exception as e:
        print(f"  fetch error: {e}")
    return None

def parse_baike_basic(html: str) -> dict:
    """从百度百科页面提取基本信息"""
    info = {}
    # 基本资料栏
    items = re.findall(
        r'class="basicInfo-item[^"]*name[^"]*"[^>]*>(.*?)<.*?'
        r'class="basicInfo-item[^"]*value[^"]*"[^>]*>(.*?)</dd>',
        html, re.DOTALL
    )
    for name_html, value_html in items:
        key = re.sub(r'<[^>]+>', '', name_html).strip().replace('\xa0', ' ').replace(' ', ' ')
        val = re.sub(r'<[^>]+>', '', value_html).strip()
        info[key] = val

    # 提取所有段落文本
    paras = re.findall(r'class="para[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    text = ''
    for p in paras:
        t = re.sub(r'<[^>]+>', '', p).strip()
        t = re.sub(r'\[\d+\]', '', t)  # 去掉引用标记
        if t and len(t) > 10:
            text += t + '\n'
    info['_full_text'] = text
    info['_text_length'] = len(text)
    return info

def extract_years_from_text(text: str, birth: int | None, death: int | None) -> list[dict]:
    """从百科文本中提取带年份的事件"""
    events = []
    # 匹配 "YYYY年" 模式
    year_pattern = re.finditer(r'(\d{4})年[^。；.]{10,120}', text)
    for m in year_pattern:
        y = int(m.group(1))
        content = m.group(0)
        # 跳过纯数字年份引用
        if birth and y < birth - 5:
            continue
        if death and y > death + 1:
            continue
        events.append({'year': y, 'raw': content[:200]})
    return events

def compare_chronologies(ai_chron: list[dict], baike_info: dict, birth: int | None, death: int | None) -> dict:
    """对比 AI 年谱和百度百科数据"""
    text = baike_info.get('_full_text', '')
    verified_events = []
    suspicious_events = []

    for entry in ai_chron:
        ev = entry.get('event', '')
        desc = entry.get('description', '')
        combined = f"{ev} {desc}"

        # 在百科文本中搜索关键词
        # 取事件名中前几个有意义的词
        keywords = re.findall(r'[一-鿿]{3,}', ev)
        found = any(kw in text for kw in keywords) if keywords else False

        # 也检查年份+关键词组合
        year = entry.get('year')
        if year and not found:
            year_str = str(year)
            for kw in keywords[:3]:
                # 在年份附近搜索
                idx = text.find(year_str)
                if idx >= 0:
                    context = text[max(0, idx-50):idx+200]
                    if kw in context:
                        found = True
                        break

        if found:
            verified_events.append(entry)
        else:
            suspicious_events.append(entry)

    return {
        'total_ai': len(ai_chron),
        'verified': len(verified_events),
        'suspicious': len(suspicious_events),
        'suspicious_list': suspicious_events,
        'verified_list': verified_events,
        'baike_has_text': len(text) > 100,
    }

def build_verified_chronology(baike_info: dict, birth: int | None, death: int | None, name: str) -> list[dict]:
    """从百度百科数据构建真实年谱"""
    chron = []
    text = baike_info.get('_full_text', '')
    basic = {k: v for k, v in baike_info.items() if not k.startswith('_')}

    # 出生
    if birth:
        hometown = basic.get('出生地', basic.get('籍贯', ''))
        chron.append({
            'year': birth,
            'event': '出生',
            'location': hometown if hometown else '',
            'description': f'{name}出生于{hometown}。' if hometown else f'{name}出生。'
        })

    # 提取文本中的年份事件
    year_events = []
    for m in re.finditer(r'(?:^|[。；])\s*(\d{4})年[，,、]?(.{15,200}?)(?=[。；]|$)', text):
        y = int(m.group(1))
        content = m.group(2).strip()
        if birth and death:
            if y < birth - 2 or y > death + 1:
                continue
        year_events.append((y, content))

    # 去重并构建事件
    seen_years = {birth} if birth else set()
    for y, content in year_events:
        # 尝试提取事件名（前几个字）
        event_name = content[:30]
        # 尝试提取地点
        location = ''
        loc_match = re.search(r'(?:在|于|至|赴|任|到)([一-鿿]{2,8}(?:市|县|府|州|省|镇)?)', content)
        if loc_match:
            location = loc_match.group(1)

        # 去重同年
        if y not in seen_years or len(content) > 60:
            chron.append({
                'year': y,
                'event': event_name,
                'location': location,
                'description': content[:200]
            })
            seen_years.add(y)

    # 去世
    if death:
        chron.append({
            'year': death,
            'event': '逝世',
            'location': '',
            'description': f'{name}于{death}年去世。'
        })

    # 按年份排序
    chron.sort(key=lambda e: e.get('year', 0))
    return chron

def process_artist(name: str, birth: int | None, death: int | None, ai_chron: list[dict], fix: bool = False) -> dict:
    """处理单个艺术家"""
    print(f'\n{"="*60}')
    print(f'处理: {name} ({birth}-{death})')

    # 1. 获取百度百科
    html = fetch_baike(name)
    if not html:
        return {'status': 'baike_not_found', 'name': name}

    # 2. 解析百科数据
    baike_info = parse_baike_basic(html)
    print(f'  百科文本: {baike_info.get("_text_length", 0)} 字符')

    # 3. 对比
    comparison = compare_chronologies(ai_chron, baike_info, birth, death)
    print(f'  AI条目: {comparison["total_ai"]}, 验证通过: {comparison["verified"]}, 可疑: {comparison["suspicious"]}')

    if comparison['suspicious'] > 0:
        print(f'  可疑条目:')
        for e in comparison['suspicious_list'][:5]:
            print(f'    {e.get("year","?")} | {e.get("event","")[:50]}')

    # 4. 从百科构建真实年谱
    verified_chron = build_verified_chronology(baike_info, birth, death, name)
    print(f'  百科可提取事件: {len(verified_chron)}')

    result = {
        'name': name,
        'birth': birth,
        'death': death,
        'status': 'ok' if comparison['suspicious'] == 0 else 'suspicious',
        'ai_count': len(ai_chron),
        'verified_count': comparison['verified'],
        'suspicious_count': comparison['suspicious'],
        'baike_event_count': len(verified_chron),
        'suspicious_entries': comparison['suspicious_list'],
    }

    # 5. 如果有可疑条目且开启了fix，用百科数据替换
    if fix and comparison['suspicious'] > 0:
        if len(verified_chron) >= 3:
            db = sqlite3.connect(DB_PATH)
            db.execute(
                'UPDATE artists SET art_chronology = ? WHERE name = ?',
                (json.dumps(verified_chron, ensure_ascii=False), name)
            )
            db.commit()
            db.close()
            result['fixed'] = True
            print(f'  >> 已用百科数据替换 ({len(verified_chron)} 条)')
        else:
            # 百科数据太少，降级为"仅保留验证通过的条目"
            verified_only = comparison['verified_list']
            if len(verified_only) >= 2:
                db = sqlite3.connect(DB_PATH)
                db.execute(
                    'UPDATE artists SET art_chronology = ? WHERE name = ?',
                    (json.dumps(verified_only, ensure_ascii=False), name),
                )
                db.commit()
                db.close()
                result['fixed'] = True
                result['trimmed_to'] = len(verified_only)
                print(f'  >> 百科数据不足，仅保留 {len(verified_only)} 条验证通过的条目')

    return result

def main():
    fix_mode = '--fix' in sys.argv
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

    print(f'共 {len(rows)} 位艺术家需要校验')
    if start > 0 or limit:
        rows = rows[start:start + limit] if limit else rows[start:]
        print(f'处理范围: {start} - {start + len(rows)}')

    results = []
    for i, (name, birth, death, chron_raw) in enumerate(rows):
        try:
            ai_chron = json.loads(chron_raw)
        except:
            continue

        result = process_artist(name, birth, death, ai_chron, fix=fix_mode)
        results.append(result)

        # 每处理10个保存一次中间结果
        if (i + 1) % 10 == 0:
            with open(REPORT_PATH, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f'\n=== 进度: {i+1}/{len(rows)}, 已保存中间结果 ===')

        # 避免请求过快
        time.sleep(1.5)

    # 保存最终报告
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计
    ok = sum(1 for r in results if r.get('status') == 'ok')
    suspicious = sum(1 for r in results if r.get('status') == 'suspicious')
    not_found = sum(1 for r in results if r.get('status') == 'baike_not_found')
    fixed = sum(1 for r in results if r.get('fixed'))

    print(f'\n{"="*60}')
    print(f'校验完成!')
    print(f'  总计: {len(results)}')
    print(f'  验证通过: {ok}')
    print(f'  有可疑条目: {suspicious}')
    print(f'  百科未找到: {not_found}')
    if fix_mode:
        print(f'  已自动修复: {fixed}')
    print(f'  报告保存至: {REPORT_PATH}')

if __name__ == '__main__':
    main()
