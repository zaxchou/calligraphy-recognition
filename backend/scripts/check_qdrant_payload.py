"""检查 Qdrant 中的 payload 结构"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 获取第一个点
r = requests.post('http://localhost:6333/collections/knowledge_texts/points/scroll', 
                   json={'limit': 1, 'with_payload': True})
data = r.json()

points = data.get('result', {}).get('points', [])
if points:
    payload = points[0].get('payload', {})
    print("=== First point payload ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
else:
    print("No points found")

# 搜索包含特定书名的点
print("\n=== Searching for 中国画传习文献汇编 ===")
r2 = requests.post('http://localhost:6333/collections/knowledge_texts/points/scroll', 
                    json={
                        'limit': 5,
                        'with_payload': True,
                        'filter': {
                            'must': [
                                {
                                    'key': 'metadata.book_title',
                                    'match': {'value': '中国画传习文献汇编_part1'}
                                }
                            ]
                        }
                    })
data2 = r2.json()
points2 = data2.get('result', {}).get('points', [])
print(f"Found {len(points2)} points with book_title=中国画传习文献汇编_part1")
for i, p in enumerate(points2[:3]):
    payload = p.get('payload', {})
    metadata = payload.get('metadata', {})
    print(f"\nPoint {i+1}:")
    print(f"  book_title: {metadata.get('book_title', 'N/A')}")
    print(f"  book_id: {payload.get('book_id', 'N/A')}")
