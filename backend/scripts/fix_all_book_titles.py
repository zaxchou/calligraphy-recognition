"""Fix all book titles in Qdrant"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

QDRANT_URL = "http://localhost:6333"
COLLECTIONS = ["knowledge_texts", "knowledge_images"]

def clean_title(title):
    """Remove UUID prefix from title"""
    if not title:
        return title
    # Check if title starts with UUID
    if '_' in title and len(title.split('_')[0]) == 36:
        parts = title.split('_', 1)
        if len(parts) == 2:
            return parts[1]
    return title

for collection in COLLECTIONS:
    print(f"\n{'='*60}")
    print(f"Processing collection: {collection}")
    print('='*60)
    
    # Scroll through all points
    scroll_url = f"{QDRANT_URL}/collections/{collection}/points/scroll"
    offset = None
    total_updated = 0
    
    while True:
        payload = {
            "limit": 100,
            "with_payload": True
        }
        if offset:
            payload["offset"] = offset
        
        r = requests.post(scroll_url, json=payload)
        if r.status_code != 200:
            print(f"  Error: {r.status_code}")
            break
        
        data = r.json()
        points = data.get("result", {}).get("points", [])
        next_offset = data.get("result", {}).get("next_page_offset")
        
        if not points:
            break
        
        # Process each point
        for p in points:
            point_id = p["id"]
            payload = p.get("payload", {})
            metadata = payload.get("metadata", {})
            
            # Get book_title from metadata
            book_title = metadata.get("book_title")
            if book_title:
                # Clean the title
                clean_book_title = clean_title(book_title)
                
                # Update the point with top-level book_title
                update_url = f"{QDRANT_URL}/collections/{collection}/points/payload"
                update_payload = {
                    "points": [point_id],
                    "payload": {
                        "book_title": clean_book_title
                    }
                }
                
                r = requests.post(update_url, json=update_payload)
                if r.status_code == 200:
                    total_updated += 1
                else:
                    print(f"  Failed to update {point_id[:8]}...")
        
        offset = next_offset
        if not offset:
            break
    
    print(f"  Updated {total_updated} points")

print("\nDone!")
