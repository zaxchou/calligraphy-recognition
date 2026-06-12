#!/usr/bin/env python3
"""检查 bbox 数据状态"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import httpx
from app.core.config import get_settings

# 1. 检查 knowledge.db 中的 bbox
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== knowledge.db 中的 bbox 数据 ===")

# text_chunks 表
cursor.execute("SELECT COUNT(*) FROM text_chunks WHERE bbox IS NOT NULL AND bbox != 'null'")
text_with_bbox = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM text_chunks")
text_total = cursor.fetchone()[0]
print(f"text_chunks: {text_with_bbox}/{text_total} 有 bbox")

# extracted_images 表
cursor.execute("SELECT COUNT(*) FROM extracted_images WHERE bbox IS NOT NULL AND bbox != 'null'")
image_with_bbox = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM extracted_images")
image_total = cursor.fetchone()[0]
print(f"extracted_images: {image_with_bbox}/{image_total} 有 bbox")

# 样本数据
print("\n=== text_chunks bbox 样本 ===")
cursor.execute("SELECT id, bbox FROM text_chunks WHERE bbox IS NOT NULL AND bbox != 'null' LIMIT 3")
for row in cursor.fetchall():
    print(f"  ID: {row[0]}")
    print(f"  bbox: {row[1]}")

print("\n=== extracted_images bbox 样本 ===")
cursor.execute("SELECT id, bbox FROM extracted_images WHERE bbox IS NOT NULL AND bbox != 'null' LIMIT 3")
for row in cursor.fetchall():
    print(f"  ID: {row[0]}")
    print(f"  bbox: {row[1]}")

conn.close()

# 2. 检查 Qdrant 中的 bbox
settings = get_settings()
base_url = settings.QDRANT_URL.rstrip("/") if settings.QDRANT_URL else None

if base_url:
    headers = {}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY
    
    client = httpx.Client(timeout=10.0, headers=headers)
    
    print("\n=== Qdrant knowledge_texts 中的 bbox ===")
    r = client.post(
        f"{base_url}/collections/knowledge_texts/points/scroll",
        json={"limit": 3, "with_payload": True, "with_vector": False}
    )
    if r.status_code == 200:
        points = r.json().get("result", {}).get("points", [])
        for i, point in enumerate(points):
            payload = point.get("payload", {})
            bbox = payload.get("bbox")
            print(f"  [{i+1}] ID: {point['id']}")
            print(f"      bbox: {bbox}")
    
    print("\n=== Qdrant knowledge_images 中的 bbox ===")
    r = client.post(
        f"{base_url}/collections/knowledge_images/points/scroll",
        json={"limit": 3, "with_payload": True, "with_vector": False}
    )
    if r.status_code == 200:
        points = r.json().get("result", {}).get("points", [])
        for i, point in enumerate(points):
            payload = point.get("payload", {})
            bbox = payload.get("bbox")
            print(f"  [{i+1}] ID: {point['id']}")
            print(f"      bbox: {bbox}")
    
    client.close()

print("\n=== 检查完成 ===")
