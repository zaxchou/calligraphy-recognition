"""检查 Qdrant 中的 book_title 字段值"""
import requests
import json

base = "http://localhost:6333"
collection = "knowledge_texts"

# 获取几个点看看 book_title 字段
r = requests.post(
    f"{base}/collections/{collection}/points/scroll",
    json={"limit": 5, "with_payload": True, "with_vector": False},
    timeout=10
)

if r.status_code == 200:
    points = r.json().get("result", {}).get("points", [])
    print(f"=== 检查 {collection} 集合 ===\n")
    for i, p in enumerate(points):
        payload = p.get("payload", {})
        book_id = payload.get("book_id", "N/A")
        # 检查各种可能的 book_title 字段
        metadata = payload.get("metadata", {})
        book_title_in_payload = payload.get("book_title", "NOT_FOUND")
        book_title_in_metadata = metadata.get("book_title", "NOT_FOUND") if isinstance(metadata, dict) else "N/A"
        print(f"Point {i+1}:")
        print(f"  ID: {p.get('id', '')[:40]}...")
        print(f"  book_id: {book_id}")
        print(f"  payload.book_title: {book_title_in_payload}")
        print(f"  metadata.book_title: {book_title_in_metadata}")
        print()
else:
    print(f"Error: {r.status_code} - {r.text}")

# 也检查 knowledge_images 集合
collection2 = "knowledge_images"
r2 = requests.post(
    f"{base}/collections/{collection2}/points/scroll",
    json={"limit": 3, "with_payload": True, "with_vector": False},
    timeout=10
)

if r2.status_code == 200:
    points = r2.json().get("result", {}).get("points", [])
    print(f"\n=== 检查 {collection2} 集合 ===\n")
    for i, p in enumerate(points):
        payload = p.get("payload", {})
        book_id = payload.get("book_id", "N/A")
        metadata = payload.get("metadata", {})
        book_title_in_payload = payload.get("book_title", "NOT_FOUND")
        book_title_in_metadata = metadata.get("book_title", "NOT_FOUND") if isinstance(metadata, dict) else "N/A"
        print(f"Point {i+1}:")
        print(f"  ID: {p.get('id', '')[:40]}...")
        print(f"  book_id: {book_id}")
        print(f"  payload.book_title: {book_title_in_payload}")
        print(f"  metadata.book_title: {book_title_in_metadata}")
        print()
