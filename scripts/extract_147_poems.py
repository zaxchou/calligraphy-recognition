# -*- coding: utf-8 -*-
"""
从张君飞《李鱓题画书法研究》中提取147首题画诗的具体内容
"""
import os
from pdfminer.high_level import extract_text

PDF_DIR = r"Z:\硕士论文\pdf"
TARGET_PDF = "李鱓题画书法研究_张君飞.pdf"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "li_shan_147_poems.md")

def main():
    pdf_path = os.path.join(PDF_DIR, TARGET_PDF)
    if not os.path.exists(pdf_path):
        print("[缺失] " + TARGET_PDF)
        return

    print("正在读取: " + TARGET_PDF)

    # 提取全文
    full_text = extract_text(pdf_path)

    # 保存到文件（UTF-8）
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("# 李鱓题画诗提取结果\n\n")
        f.write("来源：" + TARGET_PDF + "\n\n")
        f.write("=" * 80 + "\n\n")
        f.write(full_text)

    print("全文已提取，共 " + str(len(full_text)) + " 字符")
    print("输出文件: " + OUTPUT_PATH)

    # 尝试定位147首相关段落
    keywords = ["147", "扬州八怪题画录", "题画诗", "附录", "其一", "其二", "七言", "五言"]

    print("\n" + "=" * 80)
    print("搜索关键词出现位置：")
    print("=" * 80)

    lines = full_text.split("\n")
    for i, line in enumerate(lines):
        for kw in keywords:
            if kw in line:
                start = max(0, i - 3)
                end = min(len(lines), i + 4)
                context = "\n".join(lines[start:end])
                print("\n--- 第" + str(i+1) + "行，关键词: " + kw + " ---")
                print(context[:400])
                break

if __name__ == "__main__":
    main()
