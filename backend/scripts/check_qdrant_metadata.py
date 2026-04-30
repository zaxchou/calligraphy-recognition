"""Check Qdrant metadata structure"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

QDRANT_URL = "http://localhost:6333"
COLLECTION = "knowledge_texts"

# Scroll through points
scroll_url = f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll"
payload = {
    "limit": 5,
    "with_payload": True
}

r = requests.post(scroll_url, json=payload)
if r.status_code == 200:
    data = r.json()
    points = data.get("result", {}).get("points", [])
    print(f"First 5 points from {COLLECTION}:")
    for p in points:
        payload = p.get("payload", {})
        print(f"\n  ID: {p['id'][:8]}...")
        print(f"  Keys: {list(payload.keys())}")
        print(f"  book_title (top-level): {payload.get('book_title', 'N/A')}")
        metadata = payload.get("metadata", {})
        if metadata:
            print(f"  metadata.book_title: {metadata.get('book_title', 'N/A')}")
        else:
            print(f"  metadata: None")
