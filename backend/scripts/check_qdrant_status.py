"""检查 Qdrant 数据状态"""
import requests
import json

QDRANT_URL = "http://localhost:6333"

def check_collection(name, limit=3):
    print(f"\n=== {name} ===")
    resp = requests.post(f"{QDRANT_URL}/collections/{name}/points/scroll", 
                         json={"limit": limit, "with_payload": True, "with_vector": False})
    if resp.status_code != 200:
        print(f"  ERROR: {resp.status_code}")
        return
    data = resp.json()
    points = data["result"]["points"]
    for i, point in enumerate(points):
        p = point["payload"]
        top_title = p.get("book_title", "MISSING")
        meta = p.get("metadata", {})
        meta_title = meta.get("book_title", "MISSING") if isinstance(meta, dict) else "N/A"
        book_id = p.get("book_id", "MISSING")
        print(f"  [{i}] book_id={book_id[:12]}...")
        print(f"      top-level book_title = '{top_title}'")
        print(f"      metadata.book_title  = '{meta_title}'")

def check_image_api():
    print("\n=== Image API Test ===")
    # 获取一个图片点
    resp = requests.post(f"{QDRANT_URL}/collections/knowledge_images/points/scroll",
                         json={"limit": 1, "with_payload": True, "with_vector": False})
    if resp.status_code == 200:
        points = resp.json()["result"]["points"]
        if points:
            p = points[0]["payload"]
            img_url = p.get("url", "")
            print(f"  Image URL from Qdrant: {img_url}")
            # 测试本地 API
            if img_url:
                api_url = f"http://localhost:8001{img_url}"
                api_resp = requests.get(api_url)
                print(f"  API response: {api_resp.status_code}")

def check_outline_api():
    print("\n=== Outline API Test ===")
    # 获取一本书
    resp = requests.get("http://localhost:8001/api/v1/knowledge/books")
    if resp.status_code == 200:
        books = resp.json()
        if books:
            book = books[0]
            book_id = book.get("id", "")
            print(f"  Book: {book.get('title', 'N/A')} (id={book_id[:12]}...)")
            # 测试大纲 API
            outline_resp = requests.get(f"http://localhost:8001/api/v1/knowledge/books/{book_id}/outline")
            print(f"  Outline API: {outline_resp.status_code}")
            if outline_resp.status_code == 200:
                data = outline_resp.json()
                outline = data.get("outline", [])
                print(f"  Outline items: {len(outline)}")
                if outline:
                    print(f"  First item: {outline[0]}")

if __name__ == "__main__":
    check_collection("knowledge_texts")
    check_collection("knowledge_images")
    check_image_api()
    check_outline_api()
