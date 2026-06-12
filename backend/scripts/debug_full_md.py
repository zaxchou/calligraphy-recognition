#!/usr/bin/env python3
"""调试 full_md 保存问题"""
import sys
import os
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.pantianshou_composition.mineru_client import parse_pdf_with_mineru
from app.modules.pantianshou_composition.mineru_parser import parse_mineru_result

# PDF 文件路径
pdf_path = "Z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/uploads/9727e677-93eb-44f1-a20c-cbb090415721_潘天寿《关于构图问题》.pdf"

print("=== 调试 full_md 保存 ===\n")

# 1. 调用 MinerU
print("1. 调用 MinerU API...")
result = parse_pdf_with_mineru(pdf_path)

if not result.success:
    print(f"失败: {result.error}")
    sys.exit(1)

print(f"   MinerU 结果:")
print(f"   - full_md: {result.full_md is not None}")
print(f"   - full_md 长度: {len(result.full_md or '')}")

# 2. 转换为 PdfContent
print("\n2. 转换为 PdfContent...")
pdf_content = parse_mineru_result(
    content_list=result.content_list,
    images_dir=result.images_dir,
    full_md=result.full_md,
    pdf_path=pdf_path
)

print(f"   PdfContent 结果:")
print(f"   - full_md: {pdf_content.full_md is not None}")
print(f"   - full_md 长度: {len(pdf_content.full_md or '')}")

# 3. 检查 hasattr
print("\n3. 检查 hasattr(pdf_content, 'full_md')...")
print(f"   hasattr: {hasattr(pdf_content, 'full_md')}")
print(f"   bool(pdf_content.full_md): {bool(pdf_content.full_md)}")

# 4. 检查条件
print("\n4. 检查保存条件...")
condition = hasattr(pdf_content, 'full_md') and pdf_content.full_md
print(f"   hasattr(pdf_content, 'full_md') and pdf_content.full_md: {condition}")

if condition:
    print(f"   条件满足，应该保存 {len(pdf_content.full_md)} 字符")
else:
    print(f"   条件不满足，不会保存")
