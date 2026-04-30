"""详细检查三个问题"""
import requests
import json

QDRANT_URL = "http://localhost:6333"
API_URL = "http://localhost:8001"

# 1. 检查中国画传习文献汇编_part1 在 Qdrant 中的 book_title
print("=== 问题1: 中国画传习文献汇编_part1 的 book_title ===")
resp = requests.post(f"{QDRANT_URL}/collections/knowledge_texts/points/scroll",
                     json={"limit": 2000, "with_payload": True, "with_vector": False})
all_points = resp.json()["result"]["points"]
book_id_prefix = "b250300e"
matching = [p for p in all_points if p["payload"].get("book_id", "").startswith(book_id_prefix)]
print(f"  找到 {len(matching)} 个属于此书的点")
if matching:
    titles = set()
    for p in matching:
        t = p["payload"].get("book_title", "MISSING")
        titles.add(t)
    print(f"  不同的 book_title 值: {titles}")

# 2. 检查大纲数据的 page 值
print("\n=== 问题2: 大纲 page 值 ===")
resp = requests.get(f"{API_URL}/api/v1/knowledge/books/b250300e-8ae4-486d-a73b-854708c048d3/outline")
if resp.status_code == 200:
    outline = resp.json().get("outline", [])
    pages = [item.get("page", -1) for item in outline[:20]]
    print(f"  前20项的 page 值: {pages}")
    zero_count = sum(1 for item in outline if item.get("page", 0) == 0)
    print(f"  page=0 的项数: {zero_count}/{len(outline)}")

# 3. 检查图片数据
print("\n=== 问题3: 图片数据 ===")
resp = requests.post(f"{QDRANT_URL}/collections/knowledge_images/points/scroll",
                     json={"limit": 5, "with_payload": True, "with_vector": False})
img_points = resp.json()["result"]["points"]
for i, p in enumerate(img_points):
    payload = p["payload"]
    print(f"  [{i}] keys: {list(payload.keys())}")
    print(f"      url: '{payload.get('url', 'MISSING')}'")
    print(f"      file_path: '{payload.get('file_path', 'MISSING')}'")
    print(f"      image_path: '{payload.get('image_path', 'MISSING')}'")
    meta = payload.get("metadata", {})
    if isinstance(meta, dict):
        print(f"      metadata keys: {list(meta.keys())}")

# 4. 检查图片 API 端点
print("\n=== 图片 API 端点测试 ===")
resp = requests.get(f"{API_URL}/api/v1/knowledge/books/b250300e-8ae4-486d-a73b-854708c048d3/images")
if resp.status_code == 200:
    images = resp.json()
    print(f"  书籍图片数: {len(images)}")
    if images:
        img = images[0]
        print(f"  第一张图片: {json.dumps(img, ensure_ascii=False, indent=2)[:500]}")
