"""检查大纲数据和书名显示问题"""
import sqlite3
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

# 1. 检查大纲数据
cursor.execute('SELECT id, title, outline FROM pdf_books WHERE id = ?', ('b250300e-8ae4-486d-a73b-854708c048d3',))
row = cursor.fetchone()
if row:
    print('=== 大纲数据 ===')
    print(f'Book title: {row[1]}')
    outline = json.loads(row[2]) if row[2] else []
    print(f'Outline items: {len(outline)}')
    for item in outline[:5]:
        page = item.get('page', 0)
        level = item.get('level', 0)
        title = item.get('title', '')[:50]
        print(f'  page={page}, level={level}, title={title}')
    pages = [item.get('page', 0) for item in outline]
    print(f'Page values: min={min(pages)}, max={max(pages)}, non-zero={sum(1 for p in pages if p > 0)}')
else:
    print('Book not found')

# 2. 检查所有书籍的 title 和 file_name
print('\n=== 所有书籍 ===')
cursor.execute('SELECT id, title, file_name FROM pdf_books')
for row in cursor.fetchall():
    print(f'  id={row[0][:8]}... | title={row[1]} | file_name={row[2]}')

# 3. 检查 Qdrant 中 book_title 字段
print('\n=== Qdrant book_title 检查 ===')
import requests
resp = requests.post('http://localhost:6333/collections/knowledge_images/points/scroll', json={
    'limit': 5,
    'with_payload': True,
    'with_vector': False,
    'filter': {
        'must': [{
            'key': 'book_id',
            'match': {'value': 'b250300e-8ae4-486d-a73b-854708c048d3'}
        }]
    }
})
if resp.status_code == 200:
    data = resp.json()
    points = data.get('result', {}).get('points', [])
    print(f'Images for 中国画传习文献汇编_part1: {len(points)}')
    for p in points[:3]:
        payload = p.get('payload', {})
        print(f'  book_title={payload.get("book_title")} | image_path={payload.get("image_path", "")[:60]}')
else:
    print(f'Error: {resp.status_code}')

# 4. 检查 Qdrant 中 text chunks 的 book_title
resp2 = requests.post('http://localhost:6333/collections/knowledge_texts/points/scroll', json={
    'limit': 5,
    'with_payload': True,
    'with_vector': False,
    'filter': {
        'must': [{
            'key': 'book_id',
            'match': {'value': 'b250300e-8ae4-486d-a73b-854708c048d3'}
        }]
    }
})
if resp2.status_code == 200:
    data2 = resp2.json()
    points2 = data2.get('result', {}).get('points', [])
    print(f'\nText chunks for 中国画传习文献汇编_part1: {len(points2)}')
    for p in points2[:3]:
        payload = p.get('payload', {})
        print(f'  book_title={payload.get("book_title")} | metadata.book_title={payload.get("metadata", {}).get("book_title")}')
else:
    print(f'Error: {resp2.status_code}')

conn.close()
