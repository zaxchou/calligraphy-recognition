"""
从硕士论文PDF中提取李鱓相关的学术引文
输出格式：文件名 | 页码 | 引文内容 | 可印证的数据维度
"""
import pdfplumber
import os
import re

PDF_DIR = r"Z:\硕士论文\pdf"

# 优先读取与李鱓直接相关且有学术价值的论文
PRIORITY_FILES = [
    "李鱓的家世与早期作品_薛永年.pdf",
    "李鱓绘画的精神情结_张朵聪.pdf",
    "李鱓绘画美学思想研究_毛秋萍.pdf",
    "李鱓题画书法研究_张君飞.pdf",
    "工写自如__出新意于法度中——李鱓花鸟画艺术三论_吴丽平.pdf",
    "由工转写__天趣横溢——李鱓花鸟画艺术分析_吴丽平.pdf",
    "李鱓花鸟画的艺术特色_许珂.pdf",
    "李鱓水墨花卉研究_张海轮.pdf",
]

KEYWORDS = [
    # 分期相关
    "早期", "中期", "晚期", "早年", "晚年", "后期", "前期",
    # 情感相关
    "情感", "消极", "积极", "愤世", "牢骚", "抑郁", "畅快", "喜悦",
    "身世", "自况", "落拓", "潦倒",
    # 题材相关
    "咏物", "寄兴", "借物抒怀", "以俗为雅", "葱", "蒜", "白菜", "萝卜",
    # 题跋相关
    "题跋", "题画诗", "题款",
    # 风格转变
    "宫廷", "蒋廷锡", "石涛", "写意", "工笔",
]

def extract_relevant_pages(pdf_path, keywords=KEYWORDS):
    """提取包含关键词的页面，返回 (page_num, text) 列表"""
    results = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    continue
                for kw in keywords:
                    if kw in text:
                        results.append((i + 1, text, kw))
                        break
    except Exception as e:
        print(f"  读取失败: {e}")
    return results

def find_context(text, keyword, window=300):
    """在文本中找到关键词所在段落，返回上下文"""
    idx = text.find(keyword)
    if idx == -1:
        return ""
    start = max(0, idx - window // 2)
    end = min(len(text), idx + len(keyword) + window // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    # 清理多余空格
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet

def main():
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("李鱓相关硕士论文引文提取")
    output_lines.append("=" * 80)

    all_citations = []

    for filename in PRIORITY_FILES:
        pdf_path = os.path.join(PDF_DIR, filename)
        if not os.path.exists(pdf_path):
            output_lines.append(f"\n[缺失] {filename}")
            continue

        output_lines.append(f"\n{'='*60}")
        output_lines.append(f"正在读取: {filename}")
        output_lines.append(f"{'='*60}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if not text:
                        continue

                    # 检查是否包含关键词
                    matched_kws = [kw for kw in KEYWORDS if kw in text]
                    if not matched_kws:
                        continue

                    # 对每个匹配的关键词，提取上下文
                    for kw in matched_kws:
                        context = find_context(text, kw, window=400)
                        if context and len(context) > 20:
                            citation = {
                                "file": filename.replace(".pdf", ""),
                                "page": i + 1,
                                "keyword": kw,
                                "context": context[:300],  # 限制长度
                            }
                            all_citations.append(citation)
                            output_lines.append(f"\n  [P{i+1}] 关键词: {kw}")
                            output_lines.append(f"  引文片段: {context[:250]}")
        except Exception as e:
            output_lines.append(f"  处理失败: {e}")

    # 输出汇总
    output_lines.append("\n\n" + "=" * 80)
    output_lines.append(f"共提取 {len(all_citations)} 条潜在引文")
    output_lines.append("=" * 80)

    # 按文件分组输出
    current_file = ""
    for cit in all_citations:
        if cit["file"] != current_file:
            current_file = cit["file"]
            output_lines.append(f"\n## {current_file}")
            output_lines.append("-" * 60)
        output_lines.append(f"  P{cit['page']} | {cit['keyword']} | {cit['context']}")

    # 写入UTF-8文件
    output_path = os.path.join(os.path.dirname(__file__), "thesis_citations_output.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    
    print(f"提取完成，结果已写入: {output_path}")
    print(f"共提取 {len(all_citations)} 条潜在引文")

if __name__ == "__main__":
    main()
