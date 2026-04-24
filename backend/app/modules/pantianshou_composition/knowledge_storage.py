from __future__ import annotations

import os
import uuid
import zipfile
from typing import List, Tuple

from app.core.config import get_settings
from app.modules.pantianshou_composition.storage import build_static_url

settings = get_settings()


def ensure_knowledge_dirs() -> dict:
    base_data = os.path.dirname(settings.UPLOAD_DIR)
    base = os.path.join(base_data, "knowledge")
    books_dir = os.path.join(base, "books")
    batches_dir = os.path.join(base, "batches")
    os.makedirs(books_dir, exist_ok=True)
    os.makedirs(batches_dir, exist_ok=True)
    return {"base": base, "books_dir": books_dir, "batches_dir": batches_dir, "base_data": base_data}


def save_book_upload(filename: str, content: bytes) -> Tuple[str, str]:
    dirs = ensure_knowledge_dirs()
    ext = os.path.splitext(filename)[1].lower() or ".pdf"
    safe_ext = ext if len(ext) <= 8 else ".pdf"
    book_id = uuid.uuid4().hex
    path = os.path.join(dirs["books_dir"], f"{book_id}{safe_ext}")
    with open(path, "wb") as f:
        f.write(content)
    rel = os.path.relpath(path, dirs["base_data"])
    return path, build_static_url(rel)


def save_ingest_files(files: List[Tuple[str, bytes]]) -> Tuple[str, str]:
    dirs = ensure_knowledge_dirs()
    batch_id = uuid.uuid4().hex
    batch_dir = os.path.join(dirs["batches_dir"], batch_id)
    os.makedirs(batch_dir, exist_ok=True)
    for name, content in files:
        safe_name = os.path.basename(name) or uuid.uuid4().hex
        out_path = os.path.join(batch_dir, safe_name)
        with open(out_path, "wb") as f:
            f.write(content)
    return batch_id, batch_dir


def extract_zip_if_needed(batch_dir: str) -> str:
    entries = [p for p in os.listdir(batch_dir) if not p.startswith(".")]
    if len(entries) != 1:
        return batch_dir
    only = entries[0]
    if not only.lower().endswith(".zip"):
        return batch_dir
    zip_path = os.path.join(batch_dir, only)
    extracted = os.path.join(batch_dir, "extracted")
    os.makedirs(extracted, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extracted)
    return extracted

