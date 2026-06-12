"""检查特定 book_id 的 book_title 详情"""
import requests

base = "http://localhost:6333"
target_book_id = "2e962cef-8c98-4fee-b212-45e581089b37"

# 搜索这个 book_id 的点
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

print(f"=== book_id={target_book_id} 的详情 ===\n")

if r.status_code == 200:
    points = r.json().get("result", {}).get("points", [])
    print(f"找到 {len(points)} 个点\n")
    for i, p in enumerate(points):
        payload = p.get("payload", {})
        metadata = payload.get("metadata", {})
        print(f"Point {i+1}:")
        print(f"  payload keys: {list(payload.keys())}")
        print(f"  metadata keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'N/A'}")
        print(f"  payload.book_title: {payload.get('book_title', 'NOT_FOUND')}")
        print(f"  metadata.book_title: {metadata.get('book_title', 'NOT_FOUND') if isinstance(metadata, dict) else 'N/A'}")
        print(f"  payload.content (前100字): {str(payload.get('content', ''))[:100]}")
        print()
else:
    print(f"Error: {r.status_code}")

# 也检查 e219df37
target_book_id2 = "e219df37-ce3f-48ed-ad7f-7eee8664aee9"
filter_payload2 = {
    "must": [
        {"key": "book_id", "match": {"value": target_book_id2}}
    ]
}

r2 = requests.post(
    f"{base}/collections/knowledge_texts/points/scroll",
    json={
        "filter": filter_payload2,
        "limit": 3,
        "with_payload": True,
        "with_vector": False
    },
    timeout=10
)

print(f"\n=== book_id={target_book_id2} 的详情 ===\n")

if r2.status_code == 200:
    points = r2.json().get("result", {}).get("points", [])
    print(f"找到 {len(points)} 个点\n")
    for i, p in enumerate(points):
        payload = p.get("payload", {})
        metadata = payload.get("metadata", {})
        print(f"Point {i+1}:")
        print(f"  payload keys: {list(payload.keys())}")
        print(f"  metadata keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'N/A'}")
        print(f"  payload.book_title: {payload.get('book_title', 'NOT_FOUND')}")
        print(f"  metadata.book_title: {metadata.get('book_title', 'NOT_FOUND') if isinstance(metadata, dict) else 'N/A'}")
        print()
