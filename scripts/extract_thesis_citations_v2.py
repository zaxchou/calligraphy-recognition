"""
从硕士论文PDF中提取李鱓相关的学术引文（v2，输出为Markdown，避免编码问题）
"""
import pdfplumber
import os
import re

PDF_DIR = r"Z:\硕士论文\pdf"

PRIORITY_FILES = [
    "李鱓的家世与早期作品_薛永年.pdf",
    "李鱓绘画的精神情结_张朵聪.pdf",
    "李鱓绘画美学思想研究_毛秋萍.pdf",
    "李鱓题画书法研究_张君飞.pdf",
    "工写自如__出新意于法度中——李鱓花鸟画艺术三论_吴丽平.pdf",
    "由工转写__天趣横溢——李鱓花鸟画艺术分析_吴丽平.pdf",
    "李鱓花鸟画的艺术特色_许珂.pdf",
    "李鱓水墨花卉研究_张海轮.pdf",
    "李鱓《五松图》的传世画本与家国情怀_尹文.pdf",
    # 注意：文件名含特殊引号，暂时跳过
    # "李鱓题画书法中的金石气研究_马一芳.pdf",
]

# 按数据维度分组的关键词
KEYWORD_GROUPS = {
    "分期": ["早期", "中期", "晚期", "早年", "晚年", "后期", "前期", "分期", "阶段"],
    "情感": ["情感", "消极", "愤世", "牢骚", "抑郁", "愁苦", "悲凉", "感慨", "畅快", "喜悦", "乐观"],
    "身世自况": ["身世", "自况", "落拓", "潦倒", "落魄", "怀才不遇"],
    "咏物寄兴": ["咏物", "寄兴", "借物抒怀", "以物", "托物"],
    "以俗为雅": ["以俗为雅", "俗物", "葱", "蒜", "白菜", "萝卜", "日常"],
    "题跋": ["题跋", "题画诗", "题款", "落款"],
    "宫廷与写意转变": ["宫廷", "蒋廷锡", "石涛", "写意", "工笔", "放逸"],
}

def clean_text(text):
    """清理文本，去掉多余空白和特殊字符"""
    text = re.sub(r"\s+", " ", text)
    # 去掉可能干扰编码的字符
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return text.strip()

def extract_citations(pdf_path):
    """提取PDF中与关键词相关的引文，按维度分组返回"""
    results = {group: [] for group in KEYWORD_GROUPS}
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    continue
                text_clean = clean_text(text)
                
                for group, keywords in KEYWORD_GROUPS.items():
                    for kw in keywords:
                        if kw in text_clean:
                            # 找到包含关键词的句子/段落
                            idx = text_clean.find(kw)
                            start = max(0, idx - 150)
                            end = min(len(text_clean), idx + len(kw) + 200)
                            snippet = text_clean[start:end]
                            results[group].append({
                                "page": i + 1,
                                "keyword": kw,
                                "snippet": snippet,
                            })
                            break  # 每页每个维度只记录一次
    except Exception as e:
        return None, str(e)
    
    # 去重（同一维度的相似片段）
    for group in results:
        seen = set()
        unique = []
        for item in results[group]:
            key = item["snippet"][:50]  # 用前50字去重
            if key not in seen:
                seen.add(key)
                unique.append(item)
        results[group] = unique[:5]  # 每个维度最多5条
    
    return results, None

def main():
    output_path = os.path.join(os.path.dirname(__file__), "thesis_citations_output.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 李鱓相关硕士论文引文提取结果\n\n")
        f.write("> 来源：Z:\\硕士论文\\pdf 中的硕士论文\n\n")
        f.write("---\n\n")
        
        for filename in PRIORITY_FILES:
            pdf_path = os.path.join(PDF_DIR, filename)
            if not os.path.exists(pdf_path):
                f.write(f"## [缺失] {filename}\n\n")
                continue
            
            short_name = filename.replace(".pdf", "")
            f.write(f"## {short_name}\n\n")
            
            results, error = extract_citations(pdf_path)
            if error:
                f.write(f"**读取失败**: {error}\n\n")
                continue
            
            has_content = False
            for group, citations in results.items():
                if not citations:
                    continue
                has_content = True
                f.write(f"### {group}\n\n")
                for cit in citations:
                    f.write(f"- **P{cit['page']}** [{cit['keyword']}]: {cit['snippet']}\n\n")
            
            if not has_content:
                f.write("*（未找到相关关键词）*\n\n")
    
    print(f"提取完成，结果已写入: {output_path}")

if __name__ == "__main__":
    main()
