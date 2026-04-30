from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if getattr(settings, "QDRANT_API_KEY", ""):
        headers["api-key"] = settings.QDRANT_API_KEY
    return headers


def _base_url() -> str | None:
    url = getattr(settings, "QDRANT_URL", "") or ""
    return url.rstrip("/") if url else None


def _url(path: str) -> str | None:
    base = _base_url()
    if not base:
        return None
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


# 共享 httpx.Client，复用 TCP 连接（避免每次请求都创建新连接）
_shared_client: Optional[httpx.Client] = None


def _get_client(timeout: float = 10.0) -> httpx.Client:
    """获取共享的 httpx.Client"""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        )
        logger.debug("创建共享 Qdrant httpx.Client")
    return _shared_client


def _request(method: str, path: str, json: Dict[str, Any] | None = None, timeout: float = 10.0) -> Dict[str, Any] | None:
    url = _url(path)
    if not url:
        logger.warning("Qdrant URL 未配置，跳过请求: %s %s", method, path)
        return None
    try:
        client = _get_client(timeout)
        r = client.request(method, url, json=json, headers=_headers())
        r.raise_for_status()
        if not r.content:
            return {}
        return r.json()
    except httpx.HTTPStatusError as e:
        logger.error("Qdrant HTTP 错误: %s %s → %d %s", method, path, e.response.status_code, e.response.text[:200])
        return None
    except httpx.ConnectError as e:
        logger.error("Qdrant 连接失败: %s %s → %s", method, path, e)
        return None
    except httpx.TimeoutException as e:
        logger.error("Qdrant 请求超时: %s %s → %s", method, path, e)
        return None
    except Exception as e:
        logger.error("Qdrant 未知错误: %s %s → %s", method, path, e)
        return None


def _search(collection: str, vector: List[float], limit: int = 5, query_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    base = _base_url()
    if not base:
        return []

    payload: Dict[str, Any] = {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
        "with_vector": False,
    }
    if query_filter:
        payload["filter"] = query_filter

    url = f"{base}/collections/{collection}/points/search"
    try:
        client = _get_client(5.0)
        r = client.post(url, json=payload, headers=_headers())
        r.raise_for_status()
        data = r.json()
        return data.get("result") or []
    except httpx.HTTPStatusError as e:
        logger.error("Qdrant 搜索失败 [%s]: %d %s", collection, e.response.status_code, e.response.text[:200])
        return []
    except httpx.ConnectError as e:
        logger.error("Qdrant 连接失败 [%s]: %s", collection, e)
        return []
    except httpx.TimeoutException as e:
        logger.error("Qdrant 搜索超时 [%s]: %s", collection, e)
        return []
    except Exception as e:
        logger.error("Qdrant 搜索未知错误 [%s]: %s", collection, e)
        return results


def scroll_by_filter(
    collection: str,
    query_filter: Dict[str, Any],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    base = _base_url()
    if not base:
        return []
    url = f"{base}/collections/{collection}/points/scroll"
    try:
        client = _get_client(5.0)
        r = client.post(url, json={
            "filter": query_filter,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }, headers=_headers())
        r.raise_for_status()
        data = r.json()
        return data.get("result", {}).get("points", [])
    except Exception as e:
        logger.error("Qdrant scroll 失败 [%s]: %s", collection, e)
        return []


def search_rules(vector: List[float], limit: int = 5, rule_type: str | None = None) -> List[Dict[str, Any]]:
    # DEPRECATED: composition_rules collection is no longer maintained.
    # Rule matching uses rule_matcher.py (local keyword logic) instead.
    flt = None
    if rule_type:
        flt = {"must": [{"key": "type", "match": {"value": rule_type}}]}
    return _search("composition_rules", vector, limit=limit, query_filter=flt)


def search_cases(vector: List[float], limit: int = 3) -> List[Dict[str, Any]]:
    return _search(KNOWLEDGE_IMAGES_COLLECTION, vector, limit=limit)


def ensure_collection(collection: str, vector_size: int = 512, recreate: bool = False) -> bool:
    if not _base_url():
        return False
    if not recreate:
        exists = _request("GET", f"/collections/{collection}", timeout=5.0)
        if exists is not None:
            return True
    _request("DELETE", f"/collections/{collection}", timeout=10.0)
    created = _request(
        "PUT",
        f"/collections/{collection}",
        json={
            "vectors": {
                "size": int(vector_size),
                "distance": "Cosine",
            }
        },
        timeout=20.0,
    )
    return created is not None


def upsert_points(collection: str, points: List[Dict[str, Any]], wait: bool = True) -> bool:
    if not points:
        return True
    path = f"/collections/{collection}/points"
    if wait:
        path = f"{path}?wait=true"
    data = _request(
        "PUT",
        path,
        json={"points": points},
        timeout=30.0,
    )
    if data is None:
        return False
    return True


def search_collection(
    collection: str,
    vector: List[float],
    limit: int = 5,
    query_filter: Optional[Dict[str, Any]] = None,
    score_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Generic vector search on any collection.

    Args:
        collection: Collection name.
        vector: Query vector.
        limit: Max results.
        query_filter: Optional Qdrant filter (must/must_not/should).
        score_threshold: Minimum similarity score.

    Returns:
        List of search result dicts (score + payload).
    """
    results = _search(collection, vector, limit=limit, query_filter=query_filter)
    if score_threshold is not None:
        results = [r for r in results if r.get("score", 0) >= score_threshold]
    return results


def scroll_collection(
    collection: str,
    limit: int = 100,
    offset: Optional[str] = None,
    with_payload: bool = True,
    with_vector: bool = False,
) -> Dict[str, Any]:
    """Scroll (paginate) through all points in a collection.

    Returns:
        Dict with "points" (list) and "next_page_offset" (str or None).
    """
    payload: Dict[str, Any] = {
        "limit": limit,
        "with_payload": with_payload,
        "with_vector": with_vector,
    }
    if offset:
        payload["offset"] = offset
    url = f"{_base_url()}/collections/{collection}/points/scroll"
    if not _base_url():
        logger.warning("Qdrant URL 未配置，scroll 失败: %s", collection)
        return {"points": [], "next_page_offset": None}
    try:
        client = _get_client(10.0)
        r = client.post(url, json=payload, headers=_headers())
        r.raise_for_status()
        return r.json().get("result", {"points": [], "next_page_offset": None})
    except httpx.HTTPStatusError as e:
        logger.error("Qdrant scroll 失败 [%s]: %d %s", collection, e.response.status_code, e.response.text[:200])
        return {"points": [], "next_page_offset": None}
    except Exception as e:
        logger.error("Qdrant scroll 未知错误 [%s]: %s", collection, e)
        return {"points": [], "next_page_offset": None}


def count_collection(collection: str) -> int:
    """Return the number of points in a collection."""
    data = _request("GET", f"/collections/{collection}", timeout=5.0)
    if data and "result" in data:
        return data["result"].get("points_count", 0)
    return 0


def list_collections() -> List[str]:
    """List all collection names."""
    data = _request("GET", "/collections", timeout=5.0)
    if data and "result" in data:
        return [c.get("name", "") for c in data["result"].get("collections", [])]
    return []


def delete_collection(collection: str) -> bool:
    """Delete a collection entirely."""
    data = _request("DELETE", f"/collections/{collection}", timeout=10.0)
    return data is not None


def delete_points(collection: str, point_ids: List[str]) -> bool:
    """Delete specific points from a collection."""
    if not point_ids:
        return True
    
    base = _base_url()
    if not base:
        logger.warning("Qdrant URL 未配置，delete_points 失败")
        return False
    
    try:
        client = _get_client(10.0)
        url = f"{base}/collections/{collection}/points/delete"
        payload = {"points": point_ids}
        r = client.post(url, json=payload, headers=_headers())
        r.raise_for_status()
        logger.info("删除 %d 个向量点 [%s]", len(point_ids), collection)
        return True
    except Exception as e:
        logger.error("删除向量点失败 [%s]: %s", collection, e)
        return False


# ==================== 知识库专用集合操作 ====================

KNOWLEDGE_TEXTS_COLLECTION = "knowledge_texts"
KNOWLEDGE_IMAGES_COLLECTION = "knowledge_images"
KNOWLEDGE_TABLES_COLLECTION = "knowledge_tables"  # 新增表格集合

# multimodal-embedding-v1 输出 1024 维向量
KNOWLEDGE_VECTOR_SIZE = 1024


def ensure_knowledge_collections() -> bool:
    """确保知识库集合存在，不存在则创建."""
    texts_ok = ensure_collection(KNOWLEDGE_TEXTS_COLLECTION, vector_size=KNOWLEDGE_VECTOR_SIZE)
    images_ok = ensure_collection(KNOWLEDGE_IMAGES_COLLECTION, vector_size=KNOWLEDGE_VECTOR_SIZE)
    tables_ok = ensure_collection(KNOWLEDGE_TABLES_COLLECTION, vector_size=KNOWLEDGE_VECTOR_SIZE)  # 新增表格集合
    return texts_ok and images_ok and tables_ok


def upsert_text_chunks(chunks: List[Dict[str, Any]], book_id: str) -> bool:
    """批量插入/更新文本块向量.
    
    Args:
        chunks: 文本块列表，每项包含 id, vector, content, metadata
        book_id: 书籍ID，用于过滤
    """
    if not chunks:
        return True
    
    points = []
    for chunk in chunks:
        point = {
            "id": chunk["id"],
            "vector": chunk["vector"],
            "payload": {
                "book_id": book_id,
                "content": chunk["content"],
                "chapter": chunk.get("chapter", ""),
                "page_start": chunk.get("page_start", 0),
                "page_end": chunk.get("page_end", 0),
                "chunk_index": chunk.get("chunk_index", 0),
                "metadata": chunk.get("metadata", {}),
            }
        }
        points.append(point)
    
    return upsert_points(KNOWLEDGE_TEXTS_COLLECTION, points)


def upsert_images(images: List[Dict[str, Any]], book_id: str) -> bool:
    """批量插入/更新图像向量.
    
    Args:
        images: 图像列表，每项包含 id, vector, payload 等
        book_id: 书籍ID
    """
    if not images:
        return True
    
    points = []
    for img in images:
        # 如果调用方已经构建了完整 payload（如 knowledge_ingest_v2.py），直接使用
        if "payload" in img and isinstance(img["payload"], dict):
            # 确保 book_id 一致
            img["payload"]["book_id"] = book_id
            point = {
                "id": img["id"],
                "vector": img["vector"],
                "payload": img["payload"],
            }
        else:
            # 兼容旧调用方式：从顶层字段构建 payload
            point = {
                "id": img["id"],
                "vector": img["vector"],
                "payload": {
                    "book_id": book_id,
                    "caption": img.get("caption", ""),
                    "page_number": img.get("page_number", 0),
                    "bbox": img.get("bbox", {}),
                    "image_path": img.get("image_path", ""),
                    "related_chunk_ids": img.get("related_chunk_ids", []),
                    "metadata": img.get("metadata", {}),
                }
            }
        points.append(point)
    
    return upsert_points(KNOWLEDGE_IMAGES_COLLECTION, points)


def search_knowledge_texts(
    vector: List[float],
    book_ids: Optional[List[str]] = None,
    limit: int = 10,
    score_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """搜索知识库文本.
    
    Args:
        vector: 查询向量
        book_ids: 限定搜索的书籍ID列表，None表示搜索全部
        limit: 返回结果数量
        score_threshold: 最低相似度阈值
    """
    query_filter = None
    if book_ids:
        query_filter = {
            "must": [
                {"key": "book_id", "match": {"any": book_ids}}
            ]
        }
    
    return search_collection(
        KNOWLEDGE_TEXTS_COLLECTION,
        vector,
        limit=limit,
        query_filter=query_filter,
        score_threshold=score_threshold
    )


def search_knowledge_images(
    vector: List[float],
    book_ids: Optional[List[str]] = None,
    limit: int = 10,
    score_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """搜索知识库图像."""
    query_filter = None
    if book_ids:
        query_filter = {
            "must": [
                {"key": "book_id", "match": {"any": book_ids}}
            ]
        }
    
    return search_collection(
        KNOWLEDGE_IMAGES_COLLECTION,
        vector,
        limit=limit,
        query_filter=query_filter,
        score_threshold=score_threshold
    )


def upsert_tables(tables: List[Dict[str, Any]], book_id: str) -> bool:
    """批量插入/更新表格向量.
    
    Args:
        tables: 表格列表，每项包含 id, vector, content, metadata
        book_id: 书籍ID，用于过滤
    """
    if not tables:
        return True
    
    points = []
    for table in tables:
        point = {
            "id": table["id"],
            "vector": table["vector"],
            "payload": {
                "book_id": book_id,
                "content": table["content"],
                "chapter": table.get("chapter", ""),
                "page_start": table.get("page_start", 0),
                "page_end": table.get("page_end", 0),
                "table_index": table.get("table_index", 0),
                "metadata": table.get("metadata", {}),
            }
        }
        points.append(point)
    
    return upsert_points(KNOWLEDGE_TABLES_COLLECTION, points)


def search_knowledge_tables(
    vector: List[float],
    book_ids: Optional[List[str]] = None,
    limit: int = 10,
    score_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """搜索知识库表格.
    
    Args:
        vector: 查询向量
        book_ids: 限定搜索的书籍ID列表，None表示搜索全部
        limit: 返回结果数量
        score_threshold: 最低相似度阈值
    """
    query_filter = None
    if book_ids:
        query_filter = {
            "must": [
                {"key": "book_id", "match": {"any": book_ids}}
            ]
        }
    
    return search_collection(
        KNOWLEDGE_TABLES_COLLECTION,
        vector,
        limit=limit,
        query_filter=query_filter,
        score_threshold=score_threshold
    )


def delete_book_vectors(book_id: str) -> bool:
    """删除某本书的所有向量数据."""
    # 删除文本向量
    filter_payload = {
        "must": [
            {"key": "book_id", "match": {"value": book_id}}
        ]
    }
    
    base = _base_url()
    if not base:
        return False
    
    try:
        client = _get_client(10.0)
        # 删除文本
        client.post(
            f"{base}/collections/{KNOWLEDGE_TEXTS_COLLECTION}/points/delete",
            json={"filter": filter_payload},
            headers=_headers()
        )
        
        # 删除图像
        client.post(
            f"{base}/collections/{KNOWLEDGE_IMAGES_COLLECTION}/points/delete",
            json={"filter": filter_payload},
            headers=_headers()
        )
        
        # 删除表格
        client.post(
            f"{base}/collections/{KNOWLEDGE_TABLES_COLLECTION}/points/delete",
            json={"filter": filter_payload},
            headers=_headers()
        )
        return True
    except Exception as e:
        logger.error("Qdrant 删除书籍向量失败 [book_id=%s]: %s", book_id, e)
        return False


def get_book_vector_count(book_id: str) -> Dict[str, int]:
    """获取某本书的向量统计."""
    filter_payload = {
        "must": [
            {"key": "book_id", "match": {"value": book_id}}
        ]
    }
    
    base = _base_url()
    if not base:
        return {"texts": 0, "images": 0, "tables": 0}
    
    try:
        client = _get_client(5.0)
        # 统计文本
        r1 = client.post(
            f"{base}/collections/{KNOWLEDGE_TEXTS_COLLECTION}/points/count",
            json={"filter": filter_payload},
            headers=_headers()
        )
        text_count = r1.json().get("result", {}).get("count", 0) if r1.status_code == 200 else 0
        
        # 统计图像
        r2 = client.post(
            f"{base}/collections/{KNOWLEDGE_IMAGES_COLLECTION}/points/count",
            json={"filter": filter_payload},
            headers=_headers()
        )
        image_count = r2.json().get("result", {}).get("count", 0) if r2.status_code == 200 else 0
        
        # 统计表格
        r3 = client.post(
            f"{base}/collections/{KNOWLEDGE_TABLES_COLLECTION}/points/count",
            json={"filter": filter_payload},
            headers=_headers()
        )
        table_count = r3.json().get("result", {}).get("count", 0) if r3.status_code == 200 else 0
        
        return {"texts": text_count, "images": image_count, "tables": table_count}
    except Exception as e:
        logger.error("Qdrant 获取书籍向量统计失败 [book_id=%s]: %s", book_id, e)
        return {"texts": 0, "images": 0, "tables": 0}
