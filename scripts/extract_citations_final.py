"""
从硕士论文PDF提取李鱓相关引文，直接输出为可粘贴到academic_report_service.py的格式
用法：python extract_citations_final.py
输出：console（纯ASCII安全的摘要）+ 写入citations_for_report.py
"""
import pdfplumber
import os
import re

PDF_DIR = r"Z:\硕士论文\pdf"

# 要读取的论文（按优先级）
FILES = [
    "李鱓的家世与早期作品_薛永年.pdf",
    "李鱓绘画的精神情结_张朵聪.pdf",
    "李鱓绘画美学思想研究_毛秋萍.pdf",
    "李鱓题画书法研究_张君飞.pdf",
    "工写自如__出新意于法度中——李鱓花鸟画艺术三论_吴丽平.pdf",
    "由工转写__天趣横溢——李鱓花鸟画艺术分析_吴丽平.pdf",
    "李鱓花鸟画的艺术特色_许珂.pdf",
    "李鱓水墨花卉研究_张海轮.pdf",
    "李鱓《五松图》的传世画本与家国情怀_尹文.pdf",
]

def clean(s):
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u200b", "").replace("\ufeff", "")
    return s.strip()

def search_in_pdf(pdf_path, keywords, context_chars=250):
    """
    在PDF中搜索关键词，返回 (page_num, keyword, context) 列表
    """
    hits = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue
                for kw in keywords:
                    if kw in text:
                        idx = text.find(kw)
                        start = max(0, idx - context_chars // 2)
                        end = min(len(text), idx + len(kw) + context_chars // 2)
                        ctx = clean(text[start:end])
                        hits.append((page_num, kw, ctx))
                        break  # 每页每个关键词组只记录一次
    except Exception as e:
        return None, str(e)
    return hits, None

def main():
    # 收集所有引文
    all_results = []  # (filename, page, keyword, context)
    
    for fname in FILES:
        fpath = os.path.join(PDF_DIR, fname)
        if not os.path.exists(fpath):
            print(f"[跳过] 文件不存在: {fname}")
            continue
        
        print(f"正在处理: {fname} ...")
        
        # 针对不同维度搜索不同的关键词
        search_keywords = [
            "早期", "早年", "宫廷", "蒋廷锡",
            "中期", "中期", "转变", "放逸",
            "晚期", "晚年", "潦倒", "落拓",
            "情感", "愤世", "消极", "牢骚", "愁苦",
            "身世", "自况", "怀才不遇",
            "咏物", "寄兴", "借物抒怀",
            "以俗为雅", "俗物", "葱", "蒜", "白菜",
            "题跋", "题画诗",
        ]
        
        hits, error = search_in_pdf(fpath, search_keywords, context_chars=300)
        if error:
            print(f"  [错误] {error}")
            continue
        if not hits:
            print(f"  [无结果] 未找到相关关键词")
            continue
            
        print(f"  找到 {len(hits)} 处")
        for (page, kw, ctx) in hits:
            all_results.append((fname.replace(".pdf", ""), page, kw, ctx))
    
    # 去重（根据context前60字）
    seen = set()
    unique = []
    for item in all_results:
        key = item[3][:60]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    
    print(f"\n去重后共 {len(unique)} 条引文")
    
    # 按维度分组
    groups = {
        "分期与生平": ["早期", "早年", "宫廷", "蒋廷锡", "中期", "转变", "放逸", "晚期", "晚年", "潦倒", "落拓"],
        "情感表达": ["情感", "愤世", "消极", "牢骚", "愁苦"],
        "身世自况": ["身世", "自况", "怀才不遇", "落拓", "潦倒"],
        "咏物寄兴": ["咏物", "寄兴", "借物抒怀"],
        "以俗为雅": ["以俗为雅", "俗物", "葱", "蒜", "白菜"],
        "题跋研究": ["题跋", "题画诗"],
    }
    
    # 分组
    grouped = {g: [] for g in groups}
    for (fname, page, kw, ctx) in unique:
        for g, kws in groups.items():
            if kw in kws:
                grouped[g].append((fname, page, kw, ctx))
                break
    
    # 输出为可粘贴到academic_report_service.py的格式
    output_path = os.path.join(os.path.dirname(__file__), "citations_for_report.py")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('# -*- coding: utf-8 -*-\n')
        f.write('# 从硕士论文提取的引文，可复制到 academic_report_service.py 的 ARTIST_CONFIG["李鱓"]["art_history"]\n')
        f.write('CITATIONS = {\n')
        
        for g, items in grouped.items():
            if not items:
                continue
            f.write(f'    # {g}\n')
            for i, (fname, page, kw, ctx) in enumerate(items[:4]):  # 每组最多4条
                safe_ctx = ctx.replace('"', "'").replace('\\', '\\\\')[:250]
                f.write(f'    "{fname}_p{page}_{kw}": {{\n')
                f.write(f'        "title": "{fname}",\n')
                f.write(f'        "page": {page},\n')
                f.write(f'        "keyword": "{kw}",\n')
                f.write(f'        "quote": "{safe_ctx}",\n')
                f.write(f'    }},\n')
            f.write('\n')
        
        f.write('}\n')
    
    print(f"\n结果已写入: {output_path}")
    print("\n前5条预览：")
    with open(output_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 30:
                print("... (更多内容请查看文件)")
                break
            print(line.rstrip())

if __name__ == "__main__":
    main()
