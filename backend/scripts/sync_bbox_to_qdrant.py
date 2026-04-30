#!/usr/bin/env python3
"""
同步 bbox 数据从 knowledge.db 到 Qdrant
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import httpx
from app.core.config import get_settings


def sync_bbox():
    """同步 bbox 数据"""
    settings = get_settings()
    base_url = settings.QDRANT_URL.rstrip("/") if settings.QDRANT_URL else None
    
    if not base_url:
        print("错误: QDRANT_URL 未配置")
        return
    
    headers = {}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY
    
    client = httpx.Client(timeout=30.0, headers=headers)
    
    # 连接数据库
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. 同步 text_chunks 的 bbox
    print("=== 同步 text_chunks bbox ===")
    
    # 获取所有 text_chunks 的 bbox
    cursor.execute("""
        SELECT tc.id, tc.vector_id, tc.bbox, tc.page_start
        FROM text_chunks tc
        WHERE tc.vector_id IS NOT NULL AND tc.bbox IS NOT NULL AND tc.bbox != 'null'
    """)
    text_chunks = cursor.fetchall()
    
    print(f"  数据库中有 {len(text_chunks)} 条 text_chunks 带 bbox")
    
    # 批量更新 Qdrant
    total_updated = 0
    batch_size = 50
    
    for i in range(0, len(text_chunks), batch_size):
        batch = text_chunks[i:i+batch_size]
        
        # 构建更新请求
        points_to_update = []
        for chunk_id, vector_id, bbox_str, page_start in batch:
            try:
                bbox = json.loads(bbox_str) if bbox_str else None
                if bbox:
                    # 添加 page 信息到 bbox
                    bbox["page"] = page_start
                    points_to_update.append({
                        "id": vector_id,
                        "payload": {"bbox": bbox}
                    })
            except json.JSONDecodeError:
                print(f"    解析 bbox 失败: {chunk_id}")
                continue
        
        if points_to_update:
            # Qdrant set_payload API
            update_payload = {
                "points": [p["id"] for p in points_to_update],
                "payload": points_to_update[0]["payload"]
            }
            
            r = client.post(
                f"{base_url}/collections/knowledge_texts/points/payload",
                json=update_payload
            )
            
            if r.status_code == 200:
                total_updated += len(points_to_update)
                print(f"  已更新 {len(points_to_update)} 个点 (批次 {i//batch_size + 1})")
            else:
                print(f"  批量更新失败: {r.status_code} {r.text[:200]}")
                # 回退到逐个更新
                for p in points_to_update:
                    r = client.post(
                        f"{base_url}/collections/knowledge_texts/points/{p['id']}/payload",
                        json={"payload": p["payload"]}
                    )
                    if r.status_code == 200:
                        total_updated += 1
                    else:
                        print(f"    更新失败 {p['id']}: {r.status_code}")
    
    print(f"  text_chunks 总计更新: {total_updated} 个点")
    
    # 2. 同步 extracted_images 的 bbox
    print("\n=== 同步 extracted_images bbox ===")
    
    cursor.execute("""
        SELECT ei.id, ei.vector_id, ei.bbox, ei.page
        FROM extracted_images ei
        WHERE ei.vector_id IS NOT NULL AND ei.bbox IS NOT NULL AND ei.bbox != 'null'
    """)
    extracted_images = cursor.fetchall()
    
    print(f"  数据库中有 {len(extracted_images)} 条 extracted_images 带 bbox")
    
    total_updated = 0
    
    for i in range(0, len(extracted_images), batch_size):
        batch = extracted_images[i:i+batch_size]
        
        points_to_update = []
        for image_id, vector_id, bbox_str, page in batch:
            try:
                bbox = json.loads(bbox_str) if bbox_str else None
                if bbox:
                    bbox["page"] = page
                    points_to_update.append({
                        "id": vector_id,
                        "payload": {"bbox": bbox}
                    })
            except json.JSONDecodeError:
                print(f"    解析 bbox 失败: {image_id}")
                continue
        
        if points_to_update:
            update_payload = {
                "points": [p["id"] for p in points_to_update],
                "payload": points_to_update[0]["payload"]
            }
            
            r = client.post(
                f"{base_url}/collections/knowledge_images/points/payload",
                json=update_payload
            )
            
            if r.status_code == 200:
                total_updated += len(points_to_update)
                print(f"  已更新 {len(points_to_update)} 个点 (批次 {i//batch_size + 1})")
            else:
                print(f"  批量更新失败: {r.status_code} {r.text[:200]}")
                for p in points_to_update:
                    r = client.post(
                        f"{base_url}/collections/knowledge_images/points/{p['id']}/payload",
                        json={"payload": p["payload"]}
                    )
                    if r.status_code == 200:
                        total_updated += 1
                    else:
                        print(f"    更新失败 {p['id']}: {r.status_code}")
    
    print(f"  extracted_images 总计更新: {total_updated} 个点")
    
    conn.close()
    client.close()


def main():
    print("=== 同步 bbox 到 Qdrant ===\n")
    sync_bbox()
    print("\n=== 同步完成 ===")


if __name__ == "__main__":
    main()
