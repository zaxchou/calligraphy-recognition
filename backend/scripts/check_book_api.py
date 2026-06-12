"""检查书籍列表API返回的数据"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Check the book list API
resp = requests.get('http://localhost:8001/api/v1/knowledge/books')
if resp.status_code == 200:
    books = resp.json()
    for book in books:
        bid = book.get('id', '')[:8]
        title = book.get('title')
        file_name = book.get('file_name')
        print(f'id={bid}... | title={title} | file_name={file_name}')
else:
    print(f'Error: {resp.status_code} - {resp.text[:200]}')
