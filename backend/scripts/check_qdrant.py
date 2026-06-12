"""Check Qdrant data"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

QDRANT_URL = "http://localhost:6333"
COLLECTIONS = ["knowledge_texts", "knowledge_images"]

for collection in COLLECTIONS:
    print(f"\n{'='*60}")
    print(f"Collection: {collection}")
    print('='*60)
    
    # Get collection info
    r = requests.get(f"{QDRANT_URL}/collections/{collection}")
    if r.status_code == 200:
        info = r.json().get("result", {})
        print(f"Points: {info.get('points_count', 0)}")
    
    # Scroll through points
    scroll_url = f"{QDRANT_URL}/collections/{collection}/points/scroll"
    payload = {
        "limit": 5,
        "with_payload": True
    }
    
    r = requests.post(scroll_url, json=payload)
    if r.status_code == 200:
        data = r.json()
        points = data.get("result", {}).get("points", [])
        print(f"\nFirst 5 points:")
        for p in points:
            payload = p.get("payload", {})
            book_title = payload.get("book_title", "N/A")
            print(f"  ID: {p['id'][:8]}... | book_title: {book_title}")
