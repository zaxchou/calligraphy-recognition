"""
使用 pdfminer.six 从硕士论文PDF中提取李鱓相关引文
pdfminer 对中文编码支持更好
"""
from pdfminer.high_level import extract_text
import os
import re

PDF_DIR = r"Z:\硕士论文\pdf"

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

# 按数据维度分组的关键词
KEYWORD_GROUPS = {
    "分期与生平": ["早期", "早年", "中期", "晚期", "晚年", "后期", "阶段", "分期"],
    "宫廷与写意转变": ["宫廷", "蒋廷锡", "石涛", "写意", "工笔", "放逸", "转折"],
    "情感表达": ["情感", "消极", "愤世", "牢骚", "愁苦", "悲凉", "感慨", "抑郁"],
    "积极情感": ["喜悦", "乐观", "畅快", "得意"],
    "身世自况": ["身世", "自况", "落拓", "潦倒", "落魄", "怀才不遇", "穷困"],
    "咏物寄兴": ["咏物", "寄兴", "借物抒怀", "托物言志"],
    "以俗为雅": ["以俗为雅", "俗物", "葱", "蒜", "白菜", "萝卜", "日常"],
    "题跋研究": ["题跋", "题画诗", "题款", "落款"],
}

def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_with_pdfminer(pdf_path):
    """使用 pdfminer 提取整篇 PDF 文本，按维度返回匹配片段"""
    try:
        full_text = extract_text(pdf_path)
    except Exception as e:
        return None, str(e)
    
    if not full_text:
        return None, "empty text"
    
    results = {group: [] for group in KEYWORD_GROUPS}
    
    for group, keywords in KEYWORD_GROUPS.items():
        for kw in keywords:
            idx = full_text.find(kw)
            while idx != -1:
                start = max(0, idx - 120)
                end = min(len(full_text), idx + len(kw) + 180)
                snippet = clean_text(full_text[start:end])
                results[group].append({
                    "keyword": kw,
                    "snippet": snippet,
                })
                # 继续查找下一个匹配
                idx = full_text.find(kw, idx + 1)
                if len(results[group]) >= 5:  # 每维度每关键词最多5条
                    break
            if len(results[group]) >= 8:  # 每维度最多8条
                break
    
    return results, None

def find_page_for_keyword(pdf_path, keyword):
    """尝试定位关键词所在的页码（pdfminer 不直接提供页码，用分段估算）"""
    # 退化方案：返回 "见原文"
    return "见原文"

def main():
    output_path = os.path.join(os.path.dirname(__file__), "thesis_citations_clean.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 李鱓相关硕士论文引文（pdfminer提取）\n\n")
        f.write("> 提取工具：pdfminer.six（对中文支持更好）\n\n")
        f.write("---\n\n")
        
        for filename in FILES:
            pdf_path = os.path.join(PDF_DIR, filename)
            if not os.path.exists(pdf_path):
                f.write(f"## [缺失] {filename}\n\n")
                continue
            
            short_name = filename.replace(".pdf", "")
            f.write(f"## {short_name}\n\n")
            
            results, error = extract_with_pdfminer(pdf_path)
            if error:
                f.write(f"**提取失败**: {error}\n\n")
                continue
            
            has_any = False
            for group, citations in results.items():
                if not citations:
                    continue
                has_any = True
                f.write(f"### {group}\n\n")
                for i, cit in enumerate(citations[:3]):  # 每组最多显示3条
                    f.write(f"{i+1}. **[{cit['keyword']}]** {cit['snippet']}\n\n")
            
            if not has_any:
                f.write("*（未找到相关关键词）*\n\n")
    
    print(f"提取完成，结果已写入: {output_path}")
    print("请查看该文件，选取合适的引文复制到 academic_report_service.py")

if __name__ == "__main__":
    main()
