#!/usr/bin/env python3
"""检查 MinerU content_list 中的类型"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.pantianshou_composition.mineru_client import parse_pdf_with_mineru

# PDF 文件路径
pdf_path = "Z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/uploads/9727e677-93eb-44f1-a20c-cbb090415721_潘天寿《关于构图问题》.pdf"

print(f"开始解析: {pdf_path}")
result = parse_pdf_with_mineru(pdf_path)

if not result.success:
    print(f"解析失败: {result.error}")
    sys.exit(1)

print(f"\n解析成功!")
print(f"  内容块数量: {len(result.content_list or [])}")

# 统计类型
if result.content_list:
    types = {}
    for item in result.content_list:
        item_type = item.get("type", "unknown")
        types[item_type] = types.get(item_type, 0) + 1
    
    print(f"\n  类型统计:")
    for t, count in sorted(types.items()):
        print(f"    {t}: {count}")
    
    # 显示前 10 个 title 类型的项目
    titles = [item for item in result.content_list if item.get("type") == "title"]
    print(f"\n  title 类型项目: {len(titles)} 个")
    for t in titles[:10]:
        print(f"    - {t.get('text', '')} (页 {t.get('page_idx', 0) + 1})")
    
    # 显示前 5 个项目的完整结构
    print(f"\n  前 5 个项目结构:")
    for i, item in enumerate(result.content_list[:5]):
        print(f"    [{i}] type={item.get('type')}, text={item.get('text', '')[:50]}...")
