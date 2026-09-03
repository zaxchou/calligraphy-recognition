"""
批量创建书画家名录 并 调用 AI 补全信息
用法：
  set AUTH_TOKEN=your_jwt_token
  python scripts\batch_import_artists.py

前置条件：
  - 后端已启动在 http://localhost:3000
  - 需要一个编辑权限以上的 JWT token
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

API_BASE = os.environ.get("API_BASE", "http://localhost:3000/api/v1")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")

if not AUTH_TOKEN:
    token_file = os.path.join(os.path.dirname(__file__), ".token.txt")
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            AUTH_TOKEN = f.read().strip()

if not AUTH_TOKEN:
    print("请设置 AUTH_TOKEN 环境变量（浏览器登录后从 localStorage 的 auth_token 取）")
    print("  $env:AUTH_TOKEN='eyJ...'  (PowerShell)")
    sys.exit(1)

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {AUTH_TOKEN}",
}


def api_request(method, path, body=None):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        return {"error": True, "status": e.code, "detail": err}
    except Exception as e:
        return {"error": True, "status": 0, "detail": str(e)}


def create_artist(name):
    """创建画家（幂等），返回 artist_id"""
    result = api_request("POST", "/artists", {"name": name})
    if result.get("success") and result.get("id"):
        return result["id"]
    return None


def ai_fill(artist_id):
    """调用 AI 补全信息"""
    return api_request("POST", f"/artists/{artist_id}/ai-fill")


def has_artist_data(artist_id):
    """检查艺术家是否已有足够数据（跳过AI补全）"""
    result = api_request("GET", f"/artists/{artist_id}")
    if result.get("success") and result.get("artist"):
        a = result["artist"]
        if a.get("summary") and len(str(a["summary"])) > 20:
            return True
        if a.get("biography") and len(str(a["biography"])) > 50:
            return True
    return False


def _write_progress(filepath, current, total, ok, fail, skip, last_name):
    from datetime import datetime
    now = datetime.now().strftime("%H:%M:%S")
    pct = current / total * 100
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"进度: {current}/{total} ({pct:.1f}%)  已填充: {ok}  跳过: {skip}  失败: {fail}\n")
        f.write(f"上次: {last_name}  时间: {now}\n")


def _save_resume(filepath, index):
    with open(filepath, "w") as f:
        f.write(str(index))


# ════════════════════════════════════════════════════════════════
# 书画家名录
# ════════════════════════════════════════════════════════════════

ARTISTS = []

# ── 魏晋南北朝 ──
ARTISTS += [
    "钟繇", "卫夫人", "王羲之", "王献之", "王珣",
    "陆机", "索靖", "谢安", "郗愔",
    "顾恺之", "陆探微", "张僧繇",
    "羊欣", "王僧虔", "萧子云", "智永",
    "郑道昭", "寇谦之",
]

# ── 隋唐五代 ──
ARTISTS += [
    "欧阳询", "虞世南", "褚遂良", "薛稷",
    "张旭", "怀素", "颜真卿", "柳公权",
    "孙过庭", "李邕", "徐浩", "钟绍京",
    "贺知章", "李白", "杜牧",
    "阎立本", "吴道子", "李思训", "李昭道",
    "王维", "韩干", "韩滉", "张萱", "周昉",
    "边鸾", "刁光胤", "孙位",
    "杨凝式", "徐铉", "李煜",
    "荆浩", "关仝", "董源", "巨然",
    "黄筌", "徐熙", "周文矩", "顾闳中",
    "赵干", "卫贤", "阮郜",
]

# ── 两宋 ──
ARTISTS += [
    "李成", "范宽", "郭熙", "王诜",
    "苏轼", "黄庭坚", "米芾", "蔡襄",
    "赵佶", "李公麟", "张择端", "王希孟",
    "李唐", "刘松年", "马远", "夏圭",
    "梁楷", "牧溪", "赵孟坚",
    "崔白", "赵昌", "易元吉",
    "文同", "杨无咎", "赵孟頫",
    "苏汉臣", "李嵩", "陈居中",
    "燕文贵", "许道宁", "高克明",
    "赵令穰", "赵伯驹", "赵伯骕",
    "米友仁", "马和之", "李迪",
    "朱熹", "陆游", "姜夔", "吴琚",
    "张即之", "赵孟坚",
]

# ── 元代 ──
ARTISTS += [
    "钱选", "高克恭", "赵孟頫",
    "黄公望", "吴镇", "倪瓒", "王蒙",
    "李衎", "柯九思", "顾安",
    "朱德润", "唐棣", "曹知白",
    "方从义", "盛懋", "王冕",
    "杨维桢", "张雨", "康里巎巎",
    "鲜于枢", "邓文原", "虞集",
    "任仁发", "赵雍", "王渊",
    "张渥", "卫九鼎",
]

# ── 明代 ──
ARTISTS += [
    "沈周", "文徵明", "唐寅", "仇英",
    "董其昌", "陈继儒", "莫是龙",
    "徐渭", "陈淳", "周之冕",
    "戴进", "吴伟", "王谔",
    "边景昭", "林良", "吕纪",
    "谢环", "商喜", "刘俊",
    "杜堇", "周臣", "吴彬",
    "蓝瑛", "项圣谟", "孙隆",
    "文彭", "文嘉", "文伯仁", "钱谷",
    "陆治", "陆师道", "王谷祥", "谢时臣",
    "居节", "朱朗",
    "祝允明", "王宠", "张瑞图", "黄道周",
    "倪元璐", "王铎", "傅山",
    "邢侗", "米万钟",
    "曾鲸", "崔子忠", "陈洪绶",
    "邵弥", "杨文骢", "程嘉燧",
    "李流芳", "卞文瑜", "张宏",
]

# ── 清代 ──
ARTISTS += [
    "王时敏", "王鉴", "王翚", "王原祁",
    "吴历", "恽寿平",
    "朱耷", "石涛", "髡残", "弘仁",
    "龚贤", "樊圻", "高岑", "邹喆", "吴宏",
    "叶欣", "胡慥", "谢荪",
    "查士标", "梅清", "戴本孝",
    "金农", "郑燮", "黄慎", "李鱓",
    "李方膺", "汪士慎", "罗聘", "高翔",
    "袁江", "袁耀",
    "郎世宁", "王致诚", "艾启蒙",
    "高其佩", "蒋廷锡", "邹一桂",
    "钱维城", "董邦达", "董诰",
    "冷枚", "焦秉贞", "唐岱",
    "张宗苍", "徐扬", "金廷标",
    "丁观鹏", "姚文瀚",
    "费丹旭", "改琦", "任熊", "任薰",
    "任颐", "虚谷", "蒲华",
    "赵之谦", "吴昌硕",
    "钱杜", "汤贻汾", "戴熙",
    "邓石如", "伊秉绶", "何绍基",
    "翁同龢", "刘墉", "梁同书", "王文治",
    "翁方纲", "成亲王", "铁保",
    "笪重光", "姜宸英", "张照",
    "吴大澂", "杨守敬", "康有为",
]

# ── 近现代 ──
ARTISTS += [
    "齐白石", "黄宾虹", "李可染",
    "张大千", "傅抱石", "潘天寿",
    "徐悲鸿", "刘海粟", "林风眠",
    "李苦禅", "王雪涛", "钱松喦",
    "关山月", "黎雄才", "赵少昂",
    "石鲁", "何海霞", "陆俨少",
    "吴冠中", "朱德群", "赵无极",
    "陈师曾", "姚茫父", "金城",
    "吴湖帆", "冯超然", "赵叔孺",
    "郑午昌", "贺天健", "钱瘦铁",
    "于非闇", "陈之佛", "刘奎龄",
    "李铁夫", "冯钢百", "颜文樑",
    "吴作人", "吕斯百", "常书鸿",
    "董希文", "罗工柳", "艾中信",
    "王式廓", "蒋兆和", "叶浅予",
    "黄胄", "周昌谷", "方增先",
    "刘文西", "杨之光", "程十发",
    "谢稚柳", "陆抑非", "唐云",
    "启功", "沙孟海", "林散之", "沈尹默",
    "高二适", "来楚生", "王遽常",
    "萧娴", "卫俊秀",
]

# ── 中国美术学院 ──
ARTISTS += [
    "潘天寿", "吴大羽", "黄宾虹", "李可染",
    "吴冠中", "朱德群", "赵无极",
    "张漾兮", "莫朴", "胡善余",
    "关良", "邓白", "全山石",
    "肖峰", "刘国辉", "吴山明",
    "卓鹤君", "闵学林", "刘健",
    "王赞", "尉晓榕", "何加林",
    "张捷", "林海钟", "许江",
    "王澍", "邱志杰", "高世名",
    "曹意强", "范景中", "欧阳英",
    "尉天池", "朱关田", "陈振濂",
    "王冬龄", "祝遂之", "沈浩",
    "戴家妙", "鲁大东",
    "井士剑", "杨参军", "何红舟",
    "崔小冬", "焦小健", "常青",
    "章晓明", "赵军", "蒋梁",
    "顾迎庆", "徐默", "盛天晔",
    "花俊", "刘海勇", "潘汶汛",
    "孙善春", "孙周兴", "檀梓栋",
]

# ── 中央美术学院 ──
ARTISTS += [
    "徐悲鸿", "吴作人", "靳尚谊",
    "詹建俊", "侯一民", "朱乃正",
    "钱绍武", "盛扬", "王临乙",
    "滑田友", "刘开渠", "曾竹韶",
    "王朝闻", "罗工柳", "钟涵",
    "闻立鹏", "潘世勋", "苏高礼",
    "孙为民", "朝戈", "杨飞云",
    "刘小东", "喻红", "刘商英",
    "马路", "王玉平", "申玲",
    "刘庆和", "武艺", "王晓辉",
    "陈平", "丘挺", "姚鸣京",
    "李洋", "唐勇力", "毕建勋",
    "王华祥", "苏新平", "张桂林",
    "徐冰", "谭平", "王璜生",
    "隋建国", "吕胜中", "展望",
    "于凡", "姜杰", "邵大箴",
    "薛永年", "尹吉男", "孙家钵",
    "王少军", "吕品昌", "张伟",
    "曹力", "刘刚", "孟禄丁",
    "马刚", "金日龙", "康蕾",
    "李晓林", "陈科", "周思聪",
    "卢沉", "姚有多", "田黎明",
    "陈平", "贾又福", "李铁生",
]

# ── 当代名家补充 ──
ARTISTS += [
    "陈丹青", "王沂东", "艾轩", "何多苓",
    "罗中立", "程丛林", "张晓刚",
    "方力钧", "岳敏君", "曾梵志",
    "刘炜", "王广义", "周春芽",
    "毛焰", "刘野", "丁乙",
    "徐累", "何家英", "冯远",
    "范扬", "龙瑞", "卢禹舜",
    "赵卫", "满维起", "张复兴",
    "姜宝林", "郭怡孮", "张立辰",
    "郭石夫", "吴悦石", "霍春阳",
    "史国良", "范曾", "袁运甫",
    "袁运生", "尚扬", "夏小万",
    "徐冰", "蔡国强", "黄永砯",
    "邱黯雄", "杨福东", "汪建伟",
    "王劲松", "宋冬", "尹秀珍",
    "张洹", "马六明", "朱金石",
    "韩美林", "吴为山", "李象群",
]


def main():
    seen = set()
    unique = []
    for name in ARTISTS:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    artists = unique

    print(f"共 {len(artists)} 位书画家（去重后）")
    print(f"API: {API_BASE}")
    print()

    total = len(artists)
    ok_count = 0
    fail_count = 0
    skip_count = 0
    progress_file = os.path.join(os.path.dirname(__file__), ".progress.txt")
    resume_file = os.path.join(os.path.dirname(__file__), ".resume.txt")

    start_index = 0
    if os.path.exists(resume_file):
        try:
            with open(resume_file, "r") as f:
                start_index = int(f.read().strip())
                print(f"从第 {start_index + 1} 位继续（已跳过 {start_index} 位）\n")
        except Exception:
            pass

    for i, name in enumerate(artists):
        if i < start_index:
            continue
        print(f"[{i+1}/{total}] {name} ... ", end="", flush=True)
        artist_id = create_artist(name)
        if not artist_id:
            print("创建失败")
            fail_count += 1
            _write_progress(progress_file, i + 1, total, ok_count, fail_count, skip_count, name)
            _save_resume(resume_file, i + 1)
            time.sleep(3)
            continue

        if has_artist_data(artist_id):
            print(f"id={artist_id} 已有数据，跳过AI补全")
            skip_count += 1
            _write_progress(progress_file, i + 1, total, ok_count, fail_count, skip_count, name)
            _save_resume(resume_file, i + 1)
            time.sleep(0.5)
            continue

        print(f"id={artist_id} AI补全 ... ", end="", flush=True)
        fill_result = ai_fill(artist_id)
        if fill_result.get("error") and "time" in str(fill_result.get("detail", "")).lower():
            print("超时重试 ... ", end="", flush=True)
            time.sleep(2)
            fill_result = ai_fill(artist_id)
        if fill_result.get("success"):
            msg = fill_result.get("message", "OK")
            print(msg)
            ok_count += 1
        elif fill_result.get("error"):
            print(f"失败 {fill_result.get('detail', '')[:60]}")
            fail_count += 1
        else:
            print("未知")
            fail_count += 1

        _write_progress(progress_file, i + 1, total, ok_count, fail_count, skip_count, name)
        _save_resume(resume_file, i + 1)
        time.sleep(3)  # 给服务器喘息时间，避免单worker全部阻塞

    print()
    print(f"完成: 已填充 {ok_count}, 跳过 {skip_count}, 失败 {fail_count}")

    if ok_count > 0:
        print("\n请在后台编辑器中逐个检查并微调 AI 填充的内容。")


if __name__ == "__main__":
    main()
