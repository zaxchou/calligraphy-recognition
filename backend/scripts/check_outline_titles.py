"""检查大纲标题中是否包含页码"""
import sqlite3
import json
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

cursor.execute('SELECT outline FROM pdf_books WHERE id = ?', ('b250300e-8ae4-486d-a73b-854708c048d3',))
row = cursor.fetchone()
if row and row[0]:
    outline = json.loads(row[0])
    print(f'Total outline items: {len(outline)}')
    
    # Check if titles contain page numbers
    page_pattern = re.compile(r'[…\s]+(\d{1,3})$')
    items_with_pages = []
    items_without_pages = []
    
    for item in outline:
        title = item.get('title', '')
        match = page_pattern.search(title)
        if match:
            page_num = int(match.group(1))
            items_with_pages.append((title, page_num))
        else:
            items_without_pages.append(title)
    
    print(f'\nItems with page numbers in title: {len(items_with_pages)}')
    for title, page in items_with_pages[:10]:
        print(f'  page={page}, title={title[:60]}')
    
    print(f'\nItems without page numbers: {len(items_without_pages)}')
    for title in items_without_pages[:10]:
        print(f'  title={title[:60]}')
else:
    print('No outline data found')

conn.close()
