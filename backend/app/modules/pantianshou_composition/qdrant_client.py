from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

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


def _request(method: str, path: str, json: Dict[str, Any] | None = None, timeout: float = 10.0) -> Dict[str, Any] | None:
    url = _url(path)
    if not url:
        return None
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.request(method, url, json=json, headers=_headers())
            r.raise_for_status()
            if not r.content:
                return {}
            return r.json()
    except Exception:
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
        with httpx.Client(timeout=5.0) as client:
            r = client.post(url, json=payload, headers=_headers())
            r.raise_for_status()
            data = r.json()
            return data.get("result") or []
    except Exception:
        return []


def search_rules(vector: List[float], limit: int = 5, rule_type: str | None = None) -> List[Dict[str, Any]]:
    flt = None
    if rule_type:
        flt = {"must": [{"key": "type", "match": {"value": rule_type}}]}
    return _search("composition_rules", vector, limit=limit, query_filter=flt)


def search_cases(vector: List[float], limit: int = 3) -> List[Dict[str, Any]]:
    flt = {"must": [{"key": "source", "match": {"value": "uploaded_images"}}]}
    return _search("composition_cases", vector, limit=limit, query_filter=flt)


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
