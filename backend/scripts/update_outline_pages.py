"""更新大纲页码：从标题解析页码并估算无页码标题的位置"""
import sqlite3
import json
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def estimate_missing_pages(outline):
    """估算没有页码的标题位置"""
    if not outline:
        return
    
    # 找到所有有页码的项
    indexed_items = [(i, item) for i, item in enumerate(outline) if item.get("page", 0) > 0]
    
    if len(indexed_items) < 2:
        return
    
    # 对每两个有页码的项之间的无页码项进行插值
    for idx in range(len(indexed_items) - 1):
        i1, item1 = indexed_items[idx]
        i2, item2 = indexed_items[idx + 1]
        
        page1 = item1["page"]
        page2 = item2["page"]
        
        if page1 >= page2:
            continue
        
        middle_count = i2 - i1 - 1
        if middle_count <= 0:
            continue
        
        for j in range(i1 + 1, i2):
            if outline[j].get("page", 0) == 0:
                ratio = (j - i1) / (i2 - i1)
                estimated_page = int(page1 + ratio * (page2 - page1))
                outline[j]["page"] = max(1, estimated_page)
    
    # 处理第一个有页码项之前的项（使用第一个页码作为估算）
    first_idx, first_item = indexed_items[0]
    first_page = first_item["page"]
    for j in range(first_idx):
        if outline[j].get("page", 0) == 0:
            # 估算：越靠前页码越小
            ratio = j / first_idx if first_idx > 0 else 0
            estimated_page = max(1, int(first_page * ratio))
            outline[j]["page"] = estimated_page
    
    # 处理最后一个有页码项之后的项（使用最后一个页码作为基准）
    last_idx, last_item = indexed_items[-1]
    last_page = last_item["page"]
    total_items = len(outline)
    if last_idx < total_items - 1:
        # 计算平均页码间距
        if len(indexed_items) >= 2:
            avg_gap = (indexed_items[-1][1]["page"] - indexed_items[-2][1]["page"]) / (indexed_items[-1][0] - indexed_items[-2][0])
        else:
            avg_gap = 10  # 默认间距
        
        for j in range(last_idx + 1, total_items):
            if outline[j].get("page", 0) == 0:
                offset = j - last_idx
                estimated_page = int(last_page + offset * avg_gap)
                outline[j]["page"] = min(estimated_page, 700)  # 限制最大页码

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

# 获取当前大纲
cursor.execute('SELECT outline FROM pdf_books WHERE id = ?', ('b250300e-8ae4-486d-a73b-854708c048d3',))
row = cursor.fetchone()
if not row or not row[0]:
    print('No outline data found')
    conn.close()
    exit(1)

outline = json.loads(row[0])
print(f'Original outline items: {len(outline)}')

# 统计原始页码
original_pages = [item.get('page', 0) for item in outline]
print(f'Original: non-zero pages = {sum(1 for p in original_pages if p > 0)}')

# 从标题解析页码
page_pattern = re.compile(r'[…\s]+(\d{1,3})$')
for item in outline:
    if item.get('page', 0) == 0:
        title = item.get('title', '')
        page_match = page_pattern.search(title)
        if page_match:
            item['page'] = int(page_match.group(1))

# 估算无页码标题的位置
estimate_missing_pages(outline)

# 统计更新后的页码
updated_pages = [item.get('page', 0) for item in outline]
print(f'Updated: non-zero pages = {sum(1 for p in updated_pages if p > 0)}')

# 显示前10项
print('\nFirst 10 items:')
for item in outline[:10]:
    print(f'  page={item.get("page", 0):3d}, level={item.get("level", 0)}, title={item.get("title", "")[:50]}')

# 更新数据库
cursor.execute('UPDATE pdf_books SET outline = ? WHERE id = ?', 
               (json.dumps(outline, ensure_ascii=False), 'b250300e-8ae4-486d-a73b-854708c048d3'))
conn.commit()
print(f'\nDatabase updated successfully')

conn.close()
