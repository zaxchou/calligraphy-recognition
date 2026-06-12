"""Fix book_title in Qdrant"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

QDRANT_URL = "http://localhost:6333"
COLLECTIONS = ["knowledge_texts", "knowledge_images"]

# Old title with UUID prefix
OLD_TITLE = "028b83c2-56a1-4a85-b1c8-58ae17d84ce5_中国画传习文献汇编_part1"
NEW_TITLE = "中国画传习文献汇编_part1"

for collection in COLLECTIONS:
    print(f"\nProcessing collection: {collection}")
    
    # Search for points with old title
    search_url = f"{QDRANT_URL}/collections/{collection}/points/scroll"
    payload = {
        "filter": {
            "must": [
                {
                    "key": "book_title",
                    "match": {"value": OLD_TITLE}
                }
            ]
        },
        "limit": 100,
        "with_payload": True
    }
    
    r = requests.post(search_url, json=payload)
    if r.status_code != 200:
        print(f"  Error: {r.status_code} - {r.text[:200]}")
        continue
    
    data = r.json()
    points = data.get("result", {}).get("points", [])
    print(f"  Found {len(points)} points with old title")
    
    if not points:
        continue
    
    # Update each point's book_title
    update_url = f"{QDRANT_URL}/collections/{collection}/points/payload"
    point_ids = [p["id"] for p in points]
    
    # Set new title
    update_payload = {
        "points": point_ids,
        "payload": {
            "book_title": NEW_TITLE
        }
    }
    
    r = requests.post(update_url, json=update_payload)
    if r.status_code == 200:
        print(f"  Updated {len(point_ids)} points to new title")
    else:
        print(f"  Update failed: {r.status_code} - {r.text[:200]}")

print("\nDone!")
