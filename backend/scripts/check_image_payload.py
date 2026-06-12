"""检查 Qdrant knowledge_images 集合中的图片 payload 结构"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. 查看前5个点的 payload
resp = requests.post('http://localhost:6333/collections/knowledge_images/points/scroll', json={
    'limit': 5,
    'with_payload': True,
    'with_vector': False
})
if resp.status_code == 200:
    data = resp.json()
    points = data.get('result', {}).get('points', [])
    print(f'Total points found: {len(points)}')
    for i, p in enumerate(points[:3]):
        pid = p.get('id', 'unknown')
        print(f'\n=== Point {i+1} (id={pid}) ===')
        payload = p.get('payload', {})
        for k, v in payload.items():
            if k == 'embedding':
                continue
            if isinstance(v, list) and len(v) > 10:
                print(f'  {k}: [list len={len(v)}]')
            else:
                print(f'  {k}: {v}')
else:
    print(f'Error: {resp.status_code} - {resp.text[:500]}')

# 2. 搜索包含 page_118 的图片
print('\n\n=== 搜索 page_118 图片 ===')
resp2 = requests.post('http://localhost:6333/collections/knowledge_images/points/scroll', json={
    'limit': 100,
    'with_payload': True,
    'with_vector': False,
    'filter': {
        'must': [{
            'key': 'image_path',
            'match': {'value': 'page_118'}
        }]
    }
})
if resp2.status_code == 200:
    data2 = resp2.json()
    points2 = data2.get('result', {}).get('points', [])
    print(f'Found {len(points2)} points with page_118')
    for p in points2[:3]:
        pid = p.get('id', 'unknown')
        payload = p.get('payload', {})
        print(f'\n  id={pid}')
        for k, v in payload.items():
            if k == 'embedding':
                continue
            if isinstance(v, list) and len(v) > 10:
                print(f'    {k}: [list len={len(v)}]')
            else:
                print(f'    {k}: {v}')
else:
    print(f'Error: {resp2.status_code} - {resp2.text[:500]}')
