#!/usr/bin/env python3
"""
修复 Qdrant 中的 book_title（从 SQLite 获取正确书名）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import sqlite3
from app.core.config import get_settings


def get_book_titles_from_db():
    """从 SQLite 获取 book_id -> title 映射"""
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, title, file_name FROM pdf_books")
    books = cursor.fetchall()
    conn.close()
    
    # 构建映射：book_id -> title
    title_map = {}
    for book_id, title, file_name in books:
        if title:
            title_map[book_id] = title
        elif file_name:
            # 如果没有 title，使用 file_name 去掉 .pdf 后缀
            title_map[book_id] = file_name.replace(".pdf", "")
    
    return title_map


def fix_qdrant():
    """修复 Qdrant 中的 book_title"""
    settings = get_settings()
    base_url = settings.QDRANT_URL.rstrip("/") if settings.QDRANT_URL else None
    
    if not base_url:
        print("错误: QDRANT_URL 未配置")
        return
    
    headers = {}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY
    
    client = httpx.Client(timeout=30.0, headers=headers)
    
    # 从 SQLite 获取正确的书名映射
    title_map = get_book_titles_from_db()
    print(f"从 SQLite 获取到 {len(title_map)} 本书的书名\n")
    
    for book_id, title in title_map.items():
        print(f"  {book_id[:20]}... -> {title}")
    
    print("\n=== 修复 knowledge_texts ===")
    fix_collection(client, base_url, "knowledge_texts", title_map)
    
    print("\n=== 修复 knowledge_images ===")
    fix_collection(client, base_url, "knowledge_images", title_map)
    
    client.close()


def fix_collection(client: httpx.Client, base_url: str, collection: str, title_map: dict):
    """修复单个集合中的 book_title"""
    
    offset = None
    total_updated = 0
    batch_size = 100
    
    while True:
        # 滚动获取点
        scroll_payload = {
            "limit": batch_size,
            "with_payload": True,
            "with_vector": False
        }
        if offset:
            scroll_payload["offset"] = offset
        
        r = client.post(
            f"{base_url}/collections/{collection}/points/scroll",
            json=scroll_payload
        )
        
        if r.status_code != 200:
            print(f"  获取数据失败: {r.status_code}")
            break
        
        result = r.json().get("result", {})
        points = result.get("points", [])
        next_offset = result.get("next_page_offset")
        
        if not points:
            break
        
        # 找出需要更新的点
        points_to_update = []
        for point in points:
            payload = point.get("payload", {})
            book_id = payload.get("book_id")
            
            if not book_id or book_id not in title_map:
                continue
            
            correct_title = title_map[book_id]
            
            # 检查 metadata.book_title 是否需要更新
            metadata = payload.get("metadata", {})
            current_title = metadata.get("book_title", "")
            
            if current_title != correct_title:
                points_to_update.append({
                    "id": point["id"],
                    "correct_title": correct_title
                })
        
        # 批量更新
        if points_to_update:
            # 按书名分组更新
            titles_to_update = {}
            for p in points_to_update:
                title = p["correct_title"]
                if title not in titles_to_update:
                    titles_to_update[title] = []
                titles_to_update[title].append(p["id"])
            
            for title, point_ids in titles_to_update.items():
                update_payload = {
                    "points": point_ids,
                    "payload": {
                        "metadata": {
                            "book_title": title
                        }
                    }
                }
                
                r = client.post(
                    f"{base_url}/collections/{collection}/points/payload",
                    json=update_payload
                )
                
                if r.status_code == 200:
                    total_updated += len(point_ids)
                    print(f"  更新 {len(point_ids)} 个点 -> {title}")
                else:
                    print(f"  更新失败: {r.status_code} {r.text[:200]}")
        
        offset = next_offset
        if not offset:
            break
    
    print(f"  总计更新: {total_updated} 个点")


def main():
    print("=== 修复 Qdrant book_title（从 SQLite 获取正确书名）===\n")
    fix_qdrant()
    print("\n=== 修复完成 ===")


if __name__ == "__main__":
    main()
