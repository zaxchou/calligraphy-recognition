"""检查是否有 028b83c2 UUID 前缀的数据"""
import requests

QDRANT_URL = "http://localhost:6333"

# 搜索包含 028b83c2 的 book_title
for collection in ["knowledge_texts", "knowledge_images"]:
    print(f"\n=== {collection} ===")
    offset = None
    found = 0
    while True:
        resp = requests.post(f"{QDRANT_URL}/collections/{collection}/points/scroll",
                             json={"limit": 100, "with_payload": True, "with_vector": False,
                                   "offset": offset})
        if resp.status_code != 200:
            break
        data = resp.json()
        points = data["result"]["points"]
        if not points:
            break
        for p in points:
            title = p["payload"].get("book_title", "")
            if "028b83c2" in title:
                found += 1
                print(f"  FOUND: book_title='{title}'")
                print(f"    book_id={p['payload'].get('book_id', 'N/A')}")
                print(f"    id={p['id']}")
        offset = data["result"].get("next_page_offset")
        if not offset:
            break
    print(f"  总计找到 {found} 个包含 028b83c2 的点")
