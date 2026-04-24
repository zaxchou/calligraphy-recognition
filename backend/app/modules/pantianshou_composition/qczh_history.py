"""
起承转合分析 — 历史记录存储模块
==================================
使用 JSON 文件存储分析历史，支持查询、单删、批量删除。
存储位置: data/qczh_history.json
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import DATA_DIR

logger = logging.getLogger(__name__)

# 文件锁：防止并发读写 JSON 文件导致数据丢失
_history_lock = threading.Lock()


def _history_path() -> str:
    """历史记录文件路径"""
    return os.path.join(DATA_DIR, "qczh_history.json")


def _load_all() -> List[Dict[str, Any]]:
    """读取全部历史记录"""
    with _history_lock:
        path = _history_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("读取历史记录失败: %s", e)
            return []


def _save_all(records: List[Dict[str, Any]]) -> None:
    """写入全部历史记录"""
    with _history_lock:
        path = _history_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)


def save_record(
    *,
    preview_image: str,
    arrows: list,
    arrow_labels: list,
    llm_analysis: str,
    path_type: str,
    points: dict,
    model: str,
    width: int,
    height: int,
    material_type: str = "",
    growth_direction: str = "",
    has_inscription: bool = True,
    inscription_edge: str = "",
    seal_positions: list | None = None,
    image_file_name: str = "",
) -> Dict[str, Any]:
    """
    保存一条分析记录。返回完整的记录 dict。
    preview_image 应为 data:image/jpeg;base64,... 格式。
    """
    record = {
        "id": uuid.uuid4().hex[:16],
        "created_at": datetime.now().isoformat(),
        "width": width,
        "height": height,
        "preview_image": preview_image,
        "arrows": arrows,
        "arrow_labels": arrow_labels,
        "llm_analysis": llm_analysis,
        "path_type": path_type,
        "points": points,
        "model": model,
        "material_type": material_type,
        "growth_direction": growth_direction,
        "has_inscription": has_inscription,
        "inscription_edge": inscription_edge,
        "seal_positions": seal_positions or [],
        "image_file_name": image_file_name,
    }

    records = _load_all()
    # 新记录插入到最前面
    records.insert(0, record)
    # 限制最多保存 200 条
    if len(records) > 200:
        records = records[:200]
    _save_all(records)

    logger.info("起承转合历史记录已保存: %s", record["id"])
    return record


def list_records(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    查询历史记录列表。
    返回不包含 preview_image（太大），仅包含缩略信息。
    """
    records = _load_all()
    total = len(records)
    page = records[offset:offset + limit]

    # 列表不返回 preview_image，太大了
    items = []
    for r in page:
        items.append({
            "id": r["id"],
            "created_at": r["created_at"],
            "width": r["width"],
            "height": r["height"],
            "path_type": r.get("path_type", ""),
            "model": r.get("model", ""),
            "material_type": r.get("material_type", ""),
            "image_file_name": r.get("image_file_name", ""),
        })

    return {"total": total, "items": items, "limit": limit, "offset": offset}


def get_record(record_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 获取完整记录（含 preview_image）"""
    records = _load_all()
    for r in records:
        if r["id"] == record_id:
            return r
    return None


def delete_record(record_id: str) -> bool:
    """删除单条记录"""
    records = _load_all()
    new_records = [r for r in records if r["id"] != record_id]
    if len(new_records) == len(records):
        return False
    _save_all(new_records)
    logger.info("起承转合历史记录已删除: %s", record_id)
    return True


def delete_records(record_ids: List[str]) -> int:
    """批量删除记录，返回删除数量"""
    ids_set = set(record_ids)
    records = _load_all()
    new_records = [r for r in records if r["id"] not in ids_set]
    deleted = len(records) - len(new_records)
    if deleted > 0:
        _save_all(new_records)
        logger.info("起承转合批量删除 %d 条记录", deleted)
    return deleted


def clear_all() -> int:
    """清空所有历史记录，返回删除数量"""
    records = _load_all()
    count = len(records)
    _save_all([])
    logger.info("起承转合清空全部 %d 条历史记录", count)
    return count
