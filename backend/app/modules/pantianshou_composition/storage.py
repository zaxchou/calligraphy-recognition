import json
import os
from typing import Optional
from typing import Tuple

from app.core.config import get_settings

settings = get_settings()

# 图片处理配置
MAX_IMAGE_DIMENSION = 1920  # 最大边长限制
THUMBNAIL_SIZE = 400  # 缩略图尺寸
JPEG_QUALITY = 85  # JPEG压缩质量


def ensure_composition_dirs() -> dict:
    base_upload = os.path.join(settings.UPLOAD_DIR, "composition")
    base_data = os.path.dirname(settings.UPLOAD_DIR)
    base_static = os.path.join(base_data, "composition")
    overlay_dir = os.path.join(base_static, "overlays")
    reports_dir = os.path.join(base_static, "reports")
    pdf_dir = os.path.join(base_static, "pdfs")
    thumbs_dir = os.path.join(base_static, "thumbs")  # 缩略图目录

    os.makedirs(base_upload, exist_ok=True)
    os.makedirs(overlay_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)

    return {
        "upload_dir": base_upload,
        "overlay_dir": overlay_dir,
        "reports_dir": reports_dir,
        "pdf_dir": pdf_dir,
        "thumbs_dir": thumbs_dir,
    }


def _base_data_dir() -> str:
    """返回 data 目录的绝对路径（UPLOAD_DIR 的父目录）。"""
    return os.path.dirname(settings.UPLOAD_DIR)


def to_rel_path(abs_path: str) -> str:
    """将绝对路径转为相对于 data 目录的相对路径，用于数据库存储。"""
    if not abs_path:
        return abs_path
    try:
        return os.path.relpath(abs_path, _base_data_dir())
    except ValueError:
        # 不同盘符无法转相对路径，原样返回
        return abs_path


def to_abs_path(rel_path: str) -> str:
    """将相对路径转为绝对路径，用于文件系统访问。"""
    if not rel_path:
        return rel_path
    if os.path.isabs(rel_path):
        # 兼容旧数据：已经是绝对路径的，先尝试转相对再转绝对（修复盘符变更）
        try:
            rel = os.path.relpath(rel_path, _base_data_dir())
            return os.path.join(_base_data_dir(), rel)
        except ValueError:
            return rel_path
    return os.path.join(_base_data_dir(), rel_path)


def build_static_url(path_under_data: str) -> str:
    return f"/static/{path_under_data.replace(os.sep, '/')}"


def _process_and_save_image(img, save_path: str, max_dim: int = MAX_IMAGE_DIMENSION, quality: int = JPEG_QUALITY) -> Tuple[int, int]:
    """处理并保存图片：限制尺寸、压缩质量。返回 (width, height)。"""
    import cv2
    h, w = img.shape[:2]
    
    # 如果图片太大，等比例缩小
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        w, h = new_w, new_h
    
    # 保存为JPEG以减小体积
    ext = os.path.splitext(save_path)[1].lower()
    if ext in ['.jpg', '.jpeg']:
        cv2.imwrite(save_path, img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    else:
        # PNG也尝试压缩，但使用默认设置
        cv2.imwrite(save_path, img)
    
    return w, h


def _create_thumbnail(img, save_path: str, thumb_size: int = THUMBNAIL_SIZE) -> Tuple[int, int]:
    """创建缩略图。返回 (width, height)。"""
    import cv2
    h, w = img.shape[:2]
    
    # 计算缩略图尺寸（保持比例）
    if w > h:
        new_w = thumb_size
        new_h = int(h * thumb_size / w)
    else:
        new_h = thumb_size
        new_w = int(w * thumb_size / h)
    
    thumb = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    cv2.imwrite(save_path, thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
    
    return new_w, new_h


def save_upload_bytes(task_id: str, filename: str, content: bytes) -> Tuple[str, str, str, str]:
    """保存上传图片，返回 (原图路径, 原图URL, 缩略图路径, 缩略图URL)。"""
    import cv2
    import numpy as np
    
    dirs = ensure_composition_dirs()
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    # 统一使用.jpg扩展名以获得更好的压缩
    safe_ext = ".jpg"
    
    # 解码图片
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解码图片")
    
    # 保存优化后的原图
    upload_path = os.path.join(dirs["upload_dir"], f"{task_id}{safe_ext}")
    _process_and_save_image(img, upload_path, MAX_IMAGE_DIMENSION, JPEG_QUALITY)
    
    # 生成缩略图
    thumb_path = os.path.join(dirs["thumbs_dir"], f"{task_id}.jpg")
    _create_thumbnail(img, thumb_path, THUMBNAIL_SIZE)
    
    base_data = os.path.dirname(settings.UPLOAD_DIR)
    
    rel_original = os.path.relpath(upload_path, base_data)
    original_url = build_static_url(rel_original)
    
    rel_thumb = os.path.relpath(thumb_path, base_data)
    thumb_url = build_static_url(rel_thumb)
    
    return upload_path, original_url, thumb_path, thumb_url


def get_report_json_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["reports_dir"], f"{task_id}.json")


def get_pdf_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["pdf_dir"], f"{task_id}.pdf")


def get_heatmap_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["overlay_dir"], f"{task_id}_heatmap.png")


def get_arrow_overlay_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["overlay_dir"], f"{task_id}_arrow.png")


def get_upload_meta_path(task_id: str) -> str:
    dirs = ensure_composition_dirs()
    return os.path.join(dirs["reports_dir"], f"{task_id}_meta.json")


def write_upload_meta(task_id: str, file_name: str, thumb_url: Optional[str] = None) -> str:
    p = get_upload_meta_path(task_id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"file_name": file_name, "thumb_url": thumb_url}, f, ensure_ascii=False)
    return p


def read_upload_meta(task_id: str) -> Tuple[Optional[str], Optional[str]]:
    """返回 (file_name, thumb_url)。"""
    p = get_upload_meta_path(task_id)
    if not os.path.exists(p):
        return None, None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        file_name = data.get("file_name")
        thumb_url = data.get("thumb_url")
        return str(file_name) if file_name else None, thumb_url
    except Exception:
        return None, None
