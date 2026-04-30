"""检查特定 book_id 的数据"""
import requests

base = "http://localhost:6333"
target_book_id = "899591682ff741588ba7017d69188ef1"

# 在 knowledge_texts 中搜索这个 book_id
filter_payload = {
    "must": [
        {"key": "book_id", "match": {"value": target_book_id}}
    ]
}

r = requests.post(
    f"{base}/collections/knowledge_texts/points/scroll",
    json={
        "filter": filter_payload,
        "limit": 3,
        "with_payload": True,
        "with_vector": False
    },
    timeout=10
)

print(f"=== 搜索 book_id={target_book_id} ===\n")

if r.status_code == 200:
    points = r.json().get("result", {}).get("points", [])
    print(f"找到 {len(points)} 个点\n")
    for i, p in enumerate(points):
        payload = p.get("payload", {})
        metadata = payload.get("metadata", {})
        print(f"Point {i+1}:")
        print(f"  payload keys: {list(payload.keys())}")
        print(f"  book_id: {payload.get('book_id', 'N/A')}")
        print(f"  payload.book_title: {payload.get('book_title', 'NOT_FOUND')}")
        print(f"  metadata.book_title: {metadata.get('book_title', 'NOT_FOUND') if isinstance(metadata, dict) else 'N/A'}")
        print(f"  metadata keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'N/A'}")
        print()
else:
    print(f"Error: {r.status_code}")

# 也在 knowledge_images 中搜索
r2 = requests.post(
    f"{base}/collections/knowledge_images/points/scroll",
    json={
        "filter": filter_payload,
        "limit": 3,
        "with_payload": True,
        "with_vector": False
    },
    timeout=10
)

print(f"\n=== knowledge_images 中搜索 ===\n")

if r2.status_code == 200:
    points = r2.json().get("result", {}).get("points", [])
    print(f"找到 {len(points)} 个点\n")
    for i, p in enumerate(points):
        payload = p.get("payload", {})
        metadata = payload.get("metadata", {})
        print(f"Point {i+1}:")
        print(f"  payload keys: {list(payload.keys())}")
        print(f"  book_id: {payload.get('book_id', 'N/A')}")
        print(f"  payload.book_title: {payload.get('book_title', 'NOT_FOUND')}")
        print(f"  metadata.book_title: {metadata.get('book_title', 'NOT_FOUND') if isinstance(metadata, dict) else 'N/A'}")
        print()
