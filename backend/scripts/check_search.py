"""检查搜索 API 返回的书名"""
import requests
import json

API_URL = "http://localhost:8001"

# 搜索测试
resp = requests.post(f"{API_URL}/api/v1/knowledge/search", json={"query": "构图", "limit": 3})
if resp.status_code == 200:
    data = resp.json()
    results = data.get("results", [])
    print(f"搜索结果数: {len(results)}")
    for i, r in enumerate(results):
        print(f"\n[{i}] result_type={r.get('result_type')}")
        print(f"    book_title = '{r.get('book_title', 'MISSING')}'")
        print(f"    book_id = '{r.get('book_id', 'MISSING')}'")
        if r.get("result_type") == "image":
            print(f"    image.url = '{r.get('image', {}).get('url', 'MISSING')}'")
            print(f"    associated_images = {r.get('associated_images', [])[:1]}")
else:
    print(f"搜索失败: {resp.status_code} {resp.text[:200]}")
