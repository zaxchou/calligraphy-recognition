"""清理 Qdrant 中的孤立向量（book_id 在 SQLite 中不存在的向量）"""
import requests
import sqlite3
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置
QDRANT_URL = "http://localhost:6333"
SQLITE_DB = "data/knowledge.db"
COLLECTIONS = ["knowledge_texts", "knowledge_images", "knowledge_tables"]

def get_sqlite_book_ids():
    """获取 SQLite 中所有存在的 book_id"""
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM pdf_books")
    book_ids = set(row[0] for row in cursor.fetchall())
    conn.close()
    return book_ids

def get_qdrant_book_ids(collection):
    """获取 Qdrant 集合中所有唯一的 book_id"""
    book_ids = set()
    offset = None
    
    while True:
        payload = {
            "limit": 100,
            "with_payload": ["book_id"],
            "with_vector": False
        }
        if offset:
            payload["offset"] = offset
        
        r = requests.post(
            f"{QDRANT_URL}/collections/{collection}/points/scroll",
            json=payload
        )
        data = r.json()
        points = data.get("result", {}).get("points", [])
        
        if not points:
            break
        
        for p in points:
            bid = p.get("payload", {}).get("book_id")
            if bid:
                book_ids.add(bid)
        
        offset = data.get("result", {}).get("next_page_offset")
        if not offset:
            break
    
    return book_ids

def delete_points_by_book_id(collection, book_id):
    """删除集合中指定 book_id 的所有点"""
    filter_payload = {
        "must": [
            {"key": "book_id", "match": {"value": book_id}}
        ]
    }
    
    r = requests.post(
        f"{QDRANT_URL}/collections/{collection}/points/delete",
        json={"filter": filter_payload}
    )
    return r.status_code == 200

def main():
    print("=== 清理 Qdrant 孤立向量 ===\n")
    
    # 获取 SQLite 中的 book_id
    sqlite_book_ids = get_sqlite_book_ids()
    print(f"SQLite 中的书籍: {len(sqlite_book_ids)} 本")
    
    total_deleted = 0
    
    for collection in COLLECTIONS:
        print(f"\n--- 处理集合: {collection} ---")
        
        # 获取 Qdrant 中的 book_id
        qdrant_book_ids = get_qdrant_book_ids(collection)
        print(f"Qdrant 中的 book_id: {len(qdrant_book_ids)} 个")
        
        # 找出孤立的 book_id
        orphan_ids = qdrant_book_ids - sqlite_book_ids
        print(f"孤立的 book_id: {len(orphan_ids)} 个")
        
        if not orphan_ids:
            print("  无孤立数据，跳过")
            continue
        
        # 删除孤立向量
        for bid in orphan_ids:
            print(f"  删除 book_id={bid} ...")
            if delete_points_by_book_id(collection, bid):
                print(f"    ✓ 已删除")
                total_deleted += 1
            else:
                print(f"    ✗ 删除失败")
    
    print(f"\n=== 清理完成，共删除 {total_deleted} 组孤立向量 ===")

if __name__ == "__main__":
    main()
