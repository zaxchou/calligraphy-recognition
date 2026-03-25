import json
import os
from typing import Optional
from typing import Tuple

from app.core.config import get_settings

settings = get_settings()


def ensure_composition_dirs() -> dict:
    base_upload = os.path.join(settings.UPLOAD_DIR, "composition")
    base_data = os.path.dirname(settings.UPLOAD_DIR)
    base_static = os.path.join(base_data, "composition")
    overlay_dir = os.path.join(base_static, "overlays")
    reports_dir = os.path.join(base_static, "reports")
    pdf_dir = os.path.join(base_static, "pdfs")

    os.makedirs(base_upload, exist_ok=True)
    os.makedirs(overlay_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)

    return {
        "upload_dir": base_upload,
        "overlay_dir": overlay_dir,
        "reports_dir": reports_dir,
        "pdf_dir": pdf_dir,
    }


def build_static_url(path_under_data: str) -> str:
    return f"/static/{path_under_data.replace(os.sep, '/')}"


def save_upload_bytes(task_id: str, filename: str, content: bytes) -> Tuple[str, str]:
    dirs = ensure_composition_dirs()
    ext = os.path.splitext(filename)[1].lower() or ".png"
    safe_ext = ext if len(ext) <= 8 else ".png"

    upload_path = os.path.join(dirs["upload_dir"], f"{task_id}{safe_ext}")
    with open(upload_path, "wb") as f:
        f.write(content)

    base_data = os.path.dirname(settings.UPLOAD_DIR)
    rel = os.path.relpath(upload_path, base_data)
    original_url = build_static_url(rel)
    return upload_path, original_url


def get_report_json_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["reports_dir"], f"{task_id}.json")


def get_pdf_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["pdf_dir"], f"{task_id}.pdf")


def get_heatmap_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["overlay_dir"], f"{task_id}_heatmap.png")


def get_upload_meta_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["reports_dir"], f"{task_id}_meta.json")


def write_upload_meta(task_id: str, file_name: str) -> str:
    p = get_upload_meta_path(task_id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"file_name": file_name}, f, ensure_ascii=False)
    return p


def read_upload_meta(task_id: str) -> Optional[str]:
    p = get_upload_meta_path(task_id)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        v = data.get("file_name")
        return str(v) if v else None
    except Exception:
        return None
