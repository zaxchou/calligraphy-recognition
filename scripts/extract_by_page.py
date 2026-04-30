"""
按页提取PDF文本，获取准确页码，输出可直接用于art_history的引文
"""
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
import os
import re

PDF_DIR = r"Z:\硕士论文\pdf"

FILES = [
    ("李鱓的家世与早期作品_薛永年.pdf", "薛永年《李鱓的家世与早期作品》"),
    ("李鱓题画书法研究_张君飞.pdf", "张君飞《李鱓题画书法研究》"),
    ("工写自如__出新意于法度中——李鱓花鸟画艺术三论_吴丽平.pdf", "吴丽平《工写自如 出新意于法度中》"),
    ("由工转写__天趣横溢——李鱓花鸟画艺术分析_吴丽平.pdf", "吴丽平《由工转写 天趣横溢》"),
    ("李鱓《五松图》的传世画本与家国情怀_尹文.pdf", "尹文《李鱓《五松图》的传世画本与家国情怀》"),
    ("李鱓绘画美学思想研究_毛秋萍.pdf", "毛秋萍《李鱓绘画美学思想研究》"),
    ("李鱓花鸟画的艺术特色_许珂.pdf", "许珂《李鱓花鸟画的艺术特色》"),
    ("李鱓水墨花卉研究_张海轮.pdf", "张海轮《李鱓水墨花卉研究》"),
]

# 搜索关键词，按数据维度分组
SEARCH = {
    "分期与生平": ["早期", "早年", "中期", "晚期", "晚年"],
    "宫廷与写意转变": ["宫廷", "蒋廷锡", "石涛", "写意", "工笔", "放逸", "转折"],
    "情感表达": ["情感", "消极", "愤世", "牢骚", "愁苦", "感慨"],
    "身世自况": ["身世", "自况", "落拓", "潦倒", "落魄"],
    "咏物寄兴": ["咏物", "寄兴", "借物抒怀", "托物"],
    "以俗为雅": ["以俗为雅", "俗物", "葱", "蒜", "白菜", "萝卜", "辣椒"],
    "题跋研究": ["题跋", "题画诗", "题款"],
}

def extract_page_text(page):
    """提取单页文本"""
    text = ""
    try:
        for element in page:
            if isinstance(element, LTTextContainer):
                text += element.get_text()
    except:
        pass
    return text

def clean(s):
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def search_pdf_by_page(pdf_path):
    """
    按页搜索PDF，返回 [(dimension, page_num, keyword, context)]
    """
    results = []
    try:
        for i, page in enumerate(extract_pages(pdf_path), 1):
            text = extract_page_text(page)
            if not text:
                continue
            for dim, keywords in SEARCH.items():
                for kw in keywords:
                    if kw in text:
                        idx = text.find(kw)
                        start = max(0, idx - 100)
                        end = min(len(text), idx + len(kw) + 150)
                        ctx = clean(text[start:end])
                        results.append((dim, i, kw, ctx))
                        break  # 每页每维度只取第一个匹配
                        break
    except Exception as e:
        print(f"  错误: {e}")
    return results

def main():
    # 收集所有引文
    all_citations = []  # (source_title, dimension, page, keyword, context)
    
    for fname, source_title in FILES:
        fpath = os.path.join(PDF_DIR, fname)
        if not os.path.exists(fpath):
            print(f"[跳过] {fname}")
            continue
        
        print(f"正在处理: {source_title} ...")
        hits = search_pdf_by_page(fpath)
        print(f"  找到 {len(hits)} 处")
        for (dim, page, kw, ctx) in hits:
            all_citations.append((source_title, dim, page, kw, ctx))
    
    # 去重
    seen = set()
    unique = []
    for item in all_citations:
        key = item[4][:60]  # context前60字去重
        if key not in seen:
            seen.add(key)
            unique.append(item)
    
    print(f"\n去重后共 {len(unique)} 条")
    
    # 按维度分组，每组最多选3条最有价值的
    grouped = {dim: [] for dim in SEARCH}
    for (source, dim, page, kw, ctx) in unique:
        if len(grouped[dim]) < 3:
            grouped[dim].append((source, page, kw, ctx))
    
    # 输出为可粘贴到 academic_report_service.py 的格式
    output_path = os.path.join(os.path.dirname(__file__), "citations_ready.py")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('# -*- coding: utf-8 -*-\n')
        f.write('# 从硕士论文提取的引文，可直接复制到 academic_report_service.py\n')
        f.write('ART_HISTORY_NEW = {\n')
        
        for dim, items in grouped.items():
            if not items:
                continue
            f.write(f'    # {dim}\n')
            for i, (source, page, kw, ctx) in enumerate(items):
                key = f"{source[:15]}_p{page}_{kw}"[:40]
                safe_ctx = ctx.replace('"', "'").replace('\\', '\\\\')[:200]
                f.write(f'    "{key}": {{\n')
                f.write(f'        "title": "{source}",\n')
                f.write(f'        "page": {page},\n')
                f.write(f'        "keyword": "{kw}",\n')
                f.write(f'        "quote": "{safe_ctx}",\n')
                f.write(f'    }},\n')
            f.write('\n')
        
        f.write('}\n')
    
    print(f"\n结果已写入: {output_path}")
    print("\n前10条预览：")
    with open(output_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 50:
                print("... (更多内容请查看文件)")
                break
            print(line.rstrip())

if __name__ == "__main__":
    main()
