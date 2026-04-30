#!/usr/bin/env python3
"""检查 Qdrant 中的数据状态"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.core.config import get_settings

settings = get_settings()
base_url = settings.QDRANT_URL.rstrip("/") if settings.QDRANT_URL else None

if not base_url:
    print("错误: QDRANT_URL 未配置")
    sys.exit(1)

headers = {}
if settings.QDRANT_API_KEY:
    headers["api-key"] = settings.QDRANT_API_KEY

client = httpx.Client(timeout=10.0, headers=headers)

# 1. 检查集合列表
print("=== Qdrant 集合列表 ===")
r = client.get(f"{base_url}/collections")
if r.status_code == 200:
    collections = r.json().get("result", {}).get("collections", [])
    for c in collections:
        print(f"  - {c['name']}")
else:
    print(f"  获取失败: {r.status_code}")

# 2. 检查 knowledge_texts 集合
print("\n=== knowledge_texts 集合 ===")
r = client.get(f"{base_url}/collections/knowledge_texts")
if r.status_code == 200:
    info = r.json().get("result", {})
    print(f"  向量维度: {info.get('config', {}).get('params', {}).get('vectors', {}).get('size', 'N/A')}")
    print(f"  点数量: {info.get('points_count', 'N/A')}")
else:
    print(f"  获取失败: {r.status_code}")

# 3. 检查 knowledge_images 集合
print("\n=== knowledge_images 集合 ===")
r = client.get(f"{base_url}/collections/knowledge_images")
if r.status_code == 200:
    info = r.json().get("result", {})
    print(f"  向量维度: {info.get('config', {}).get('params', {}).get('vectors', {}).get('size', 'N/A')}")
    print(f"  点数量: {info.get('points_count', 'N/A')}")
else:
    print(f"  获取失败: {r.status_code}")

# 4. 获取 knowledge_texts 中的样本数据
print("\n=== knowledge_texts 样本数据 (前3条) ===")
r = client.post(
    f"{base_url}/collections/knowledge_texts/points/scroll",
    json={"limit": 3, "with_payload": True, "with_vector": False}
)
if r.status_code == 200:
    points = r.json().get("result", {}).get("points", [])
    for i, point in enumerate(points):
        payload = point.get("payload", {})
        print(f"\n  [{i+1}] ID: {point['id']}")
        print(f"      book_id: {payload.get('book_id', 'N/A')}")
        print(f"      content: {payload.get('content', 'N/A')[:80]}...")
        print(f"      metadata.book_title: {payload.get('metadata', {}).get('book_title', 'N/A')}")
else:
    print(f"  获取失败: {r.status_code}")

# 5. 获取 knowledge_images 中的样本数据
print("\n=== knowledge_images 样本数据 (前3条) ===")
r = client.post(
    f"{base_url}/collections/knowledge_images/points/scroll",
    json={"limit": 3, "with_payload": True, "with_vector": False}
)
if r.status_code == 200:
    points = r.json().get("result", {}).get("points", [])
    for i, point in enumerate(points):
        payload = point.get("payload", {})
        print(f"\n  [{i+1}] ID: {point['id']}")
        print(f"      book_id: {payload.get('book_id', 'N/A')}")
        print(f"      book_title: {payload.get('book_title', 'N/A')}")
        print(f"      figure_id: {payload.get('figure_id', 'N/A')}")
else:
    print(f"  获取失败: {r.status_code}")

client.close()
print("\n=== 检查完成 ===")
