"""检查 Qdrant 中的 book_id 分布"""
import requests
from collections import Counter

base = "http://localhost:6333"

# 获取所有不同的 book_id
r = requests.post(
    f"{base}/collections/knowledge_texts/points/scroll",
    json={"limit": 100, "with_payload": True, "with_vector": False},
    timeout=10
)

if r.status_code == 200:
    points = r.json().get("result", {}).get("points", [])
    book_ids = Counter()
    for p in points:
        payload = p.get("payload", {})
        book_id = payload.get("book_id", "N/A")
        book_ids[book_id] += 1
    
    print("=== knowledge_texts 中的 book_id 分布 ===\n")
    for bid, count in book_ids.most_common():
        print(f"  {bid}: {count} 个点")
    
    # 检查是否有 next_page
    next_page = r.json().get("result", {}).get("next_page_offset")
    if next_page:
        print(f"\n  (还有更多数据，offset={next_page})")
else:
    print(f"Error: {r.status_code}")

# 也检查 knowledge_images
r2 = requests.post(
    f"{base}/collections/knowledge_images/points/scroll",
    json={"limit": 100, "with_payload": True, "with_vector": False},
    timeout=10
)

if r2.status_code == 200:
    points = r2.json().get("result", {}).get("points", [])
    book_ids = Counter()
    for p in points:
        payload = p.get("payload", {})
        book_id = payload.get("book_id", "N/A")
        book_ids[book_id] += 1
    
    print("\n=== knowledge_images 中的 book_id 分布 ===\n")
    for bid, count in book_ids.most_common():
        print(f"  {bid}: {count} 个点")
