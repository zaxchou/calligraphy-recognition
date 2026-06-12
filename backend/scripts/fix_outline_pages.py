"""修复大纲页码：按实际 PDF 页数重新计算"""
import sqlite3
import json
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BOOK_ID = "b250300e-8ae4-486d-a73b-854708c048d3"

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

# 获取 PDF 总页数
cursor.execute("SELECT total_pages FROM pdf_books WHERE id = ?", (BOOK_ID,))
total_pages = cursor.fetchone()[0]
print(f"PDF total pages: {total_pages}")

# 获取当前大纲
cursor.execute('SELECT outline FROM pdf_books WHERE id = ?', (BOOK_ID,))
row = cursor.fetchone()
if not row or not row[0]:
    print('No outline data found')
    conn.close()
    exit(1)

outline = json.loads(row[0])
print(f"Outline items: {len(outline)}")

# 步骤1：从标题中提取原始页码
page_pattern = re.compile(r'[…\s]+(\d{1,3})$')
original_pages = []
for i, item in enumerate(outline):
    page = 0
    title = item.get('title', '')
    page_match = page_pattern.search(title)
    if page_match:
        page = int(page_match.group(1))
    original_pages.append(page)

# 统计
indexed = [(i, p) for i, p in enumerate(original_pages) if p > 0]
print(f"Items with page from title: {len(indexed)}")
for i, p in indexed:
    print(f"  {i:3d}. page={p:3d}, title={outline[i]['title'][:50]}")

# 步骤2：计算比例因子
# 原书最大页码 vs 实际 PDF 页数
if indexed:
    max_original_page = max(p for _, p in indexed)
    print(f"\nMax original page: {max_original_page}")
    print(f"Actual PDF pages: {total_pages}")
    
    if max_original_page > total_pages:
        scale = total_pages / max_original_page
        print(f"Scale factor: {scale:.4f}")
    else:
        scale = 1.0
        print("No scaling needed")
else:
    scale = 1.0

# 步骤3：重新计算所有页码
# 先用标题中的原始页码（按比例缩放）
scaled_pages = []
for i, p in enumerate(original_pages):
    if p > 0:
        scaled_pages.append((i, max(1, int(p * scale))))
    else:
        scaled_pages.append((i, 0))

# 步骤4：线性插值填补空缺
# 找到所有有页码的项
indexed_items = [(i, p) for i, p in scaled_pages if p > 0]

if len(indexed_items) >= 2:
    # 处理第一个有页码项之前的项
    first_idx, first_page = indexed_items[0]
    for j in range(first_idx):
        if scaled_pages[j][1] == 0:
            ratio = (j + 1) / (first_idx + 1)
            estimated = max(1, int(first_page * ratio))
            scaled_pages[j] = (j, min(estimated, total_pages))
    
    # 处理中间的项
    for idx in range(len(indexed_items) - 1):
        i1, p1 = indexed_items[idx]
        i2, p2 = indexed_items[idx + 1]
        
        middle_count = i2 - i1 - 1
        if middle_count <= 0:
            continue
        
        for j in range(i1 + 1, i2):
            if scaled_pages[j][1] == 0:
                ratio = (j - i1) / (i2 - i1)
                estimated = int(p1 + ratio * (p2 - p1))
                scaled_pages[j] = (j, max(1, min(estimated, total_pages)))
    
    # 处理最后一个有页码项之后的项
    last_idx, last_page = indexed_items[-1]
    if last_idx < len(scaled_pages) - 1:
        # 使用最后两个有页码项的间距
        if len(indexed_items) >= 2:
            prev_idx, prev_page = indexed_items[-2]
            avg_gap = (last_page - prev_page) / (last_idx - prev_idx)
        else:
            avg_gap = total_pages / len(scaled_pages)
        
        for j in range(last_idx + 1, len(scaled_pages)):
            if scaled_pages[j][1] == 0:
                offset = j - last_idx
                estimated = int(last_page + offset * avg_gap)
                scaled_pages[j] = (j, min(estimated, total_pages))

# 步骤5：更新 outline
for i, (idx, page) in enumerate(scaled_pages):
    outline[idx]['page'] = page

# 统计更新后的页码
pages = [item.get('page', 0) for item in outline]
non_zero = sum(1 for p in pages if p > 0)
print(f"\nUpdated: {non_zero}/{len(outline)} items have page numbers")
print(f"Page range: {min(pages)} - {max(pages)}")

# 显示前15项
print("\nFirst 15 items:")
for i, item in enumerate(outline[:15]):
    print(f"  {i:3d}. page={item.get('page', 0):3d}, title={item.get('title', '')[:50]}")

# 显示最后10项
print("\nLast 10 items:")
for i in range(max(0, len(outline)-10), len(outline)):
    item = outline[i]
    print(f"  {i:3d}. page={item.get('page', 0):3d}, title={item.get('title', '')[:50]}")

# 更新数据库
cursor.execute('UPDATE pdf_books SET outline = ? WHERE id = ?', 
               (json.dumps(outline, ensure_ascii=False), BOOK_ID))
conn.commit()
print(f"\nDatabase updated successfully")

conn.close()
