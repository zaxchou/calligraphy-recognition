from __future__ import annotations

import json
import os
from typing import Dict, Optional, Tuple

from app.core.config import get_settings
from app.modules.pantianshou_composition.knowledge_storage import ensure_knowledge_dirs
from app.modules.pantianshou_composition.storage import build_static_url

settings = get_settings()

_cache: Dict[str, Tuple[str, str]] | None = None


def _build_cache() -> Dict[str, Tuple[str, str]]:
    dirs = ensure_knowledge_dirs()
    base = dirs["base"]
    extracted_root = os.path.join(base, "extracted")
    base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
    out: Dict[str, Tuple[str, str]] = {}
    if not os.path.isdir(extracted_root):
        return out
    for root, _, files in os.walk(extracted_root):
        if "mapping.json" not in files:
            continue
        mapping_path = os.path.join(root, "mapping.json")
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f) or {}
        except Exception:
            continue
        for file_name, figure_id in mapping.items():
            if not file_name or not figure_id:
                continue
            img_path = os.path.join(root, os.path.basename(str(file_name)))
            if not os.path.exists(img_path):
                continue
            rel = os.path.relpath(img_path, base_data_dir)
            url = build_static_url(rel)
            out[str(figure_id)] = (img_path, url)
    return out


def figure_image_url(figure_id: str) -> Optional[str]:
    global _cache
    if not figure_id:
        return None
    if _cache is None:
        _cache = _build_cache()
    v = _cache.get(figure_id)
    return v[1] if v else None


def figure_image_path(figure_id: str) -> Optional[str]:
    global _cache
    if not figure_id:
        return None
    if _cache is None:
        _cache = _build_cache()
    v = _cache.get(figure_id)
    return v[0] if v else None
