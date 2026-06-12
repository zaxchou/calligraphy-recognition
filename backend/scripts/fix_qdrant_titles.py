#!/usr/bin/env python3
"""
批量修复 Qdrant 中的 book_title（去除 UUID 前缀）
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.core.config import get_settings

# UUID 前缀模式：8-4-4-4-12_
UUID_PREFIX_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_')


def clean_title(title: str) -> str:
    """去除 UUID 前缀"""
    if not title:
        return title
    return UUID_PREFIX_PATTERN.sub('', title)


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
    
    print("=== 修复 Qdrant knowledge_texts ===")
    fix_collection(client, base_url, "knowledge_texts", "metadata.book_title")
    
    print("\n=== 修复 Qdrant knowledge_images ===")
    fix_collection(client, base_url, "knowledge_images", "book_title")
    
    print("\n=== 修复 Qdrant knowledge_images (metadata) ===")
    fix_collection(client, base_url, "knowledge_images", "metadata.book_title")
    
    client.close()


def fix_collection(client: httpx.Client, base_url: str, collection: str, payload_key: str):
    """修复单个集合中的 book_title"""
    
    # 获取所有需要更新的点
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
            
            # 处理嵌套的 key（如 metadata.book_title）
            keys = payload_key.split(".")
            value = payload
            for key in keys[:-1]:
                value = value.get(key, {})
            old_value = value.get(keys[-1])
            
            if old_value and UUID_PREFIX_PATTERN.match(old_value):
                new_value = clean_title(old_value)
                
                # 构建更新 payload
                new_payload = {}
                current = new_payload
                for key in keys[:-1]:
                    current[key] = {}
                    current = current[key]
                current[keys[-1]] = new_value
                
                points_to_update.append({
                    "id": point["id"],
                    "payload": new_payload
                })
        
        # 批量更新
        if points_to_update:
            # Qdrant set_payload API: POST /collections/{collection}/points/payload
            # 请求体: {"points": [id1, id2, ...], "payload": {...}}
            # 注意：这个 API 会将 payload 合并到现有 payload 中
            
            # 按 payload 结构分组（这里所有点的 payload 结构相同）
            update_payload = {
                "points": [p["id"] for p in points_to_update],
                "payload": points_to_update[0]["payload"]
            }
            
            r = client.post(
                f"{base_url}/collections/{collection}/points/payload",
                json=update_payload
            )
            
            if r.status_code == 200:
                total_updated += len(points_to_update)
                print(f"  已更新 {len(points_to_update)} 个点")
            else:
                print(f"  批量更新失败: {r.status_code} {r.text[:200]}")
                # 回退到逐个更新
                for p in points_to_update:
                    r = client.post(
                        f"{base_url}/collections/{collection}/points/{p['id']}/payload",
                        json={"payload": p["payload"]}
                    )
                    if r.status_code == 200:
                        total_updated += 1
                    else:
                        print(f"    更新失败 {p['id']}: {r.status_code}")
        
        offset = next_offset
        if not offset:
            break
    
    print(f"  总计更新: {total_updated} 个点")


def main():
    print("=== 修复 Qdrant book_title ===\n")
    fix_qdrant()
    print("\n=== 修复完成 ===")


if __name__ == "__main__":
    main()
