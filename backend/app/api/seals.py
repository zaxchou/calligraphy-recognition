"""
印章管理 API
- CRUD
- 删除/重命名时同步 seal_content
- 关联作品查询
- 图片上传/删除/更新描述
- 从 tubi_analyses 提取印章数据
"""
import os
import json
import re
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from pydantic import BaseModel
from app.core.database import get_db_connection
from app.core.auth import require_admin_role

router = APIRouter(prefix="/seals", tags=["seals"])

SEAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "seals")
SEAL_THUMB_DIR = os.path.join(SEAL_DIR, "thumbs")

# 日志
import logging
logger = logging.getLogger(__name__)


def _create_seal_thumbnail(image_path: str, thumb_path: str, max_size: int = 200):
    """生成印章缩略图，保持宽高比，最长边不超过 max_size"""
    try:
        from PIL import Image, ImageOps
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            img.save(thumb_path, "JPEG", quality=85, optimize=True)
    except Exception as e:
        logger.warning(f"印章缩略图生成失败: {e}")


# ============ 辅助函数 ============

def _remove_seal_from_content(content: str, seal_name: str) -> str:
    if not content or not seal_name:
        return content or ""
    prefix = ""
    match = re.match(r'^(作者印[：:]\s*)', content)
    if match:
        prefix = match.group(1)
        content = content[len(prefix):]
    names = re.split(r'[、，,]', content)
    names = [n.strip() for n in names if n.strip() and n.strip() != seal_name]
    if not names:
        return ""
    return prefix + "、".join(names)


def _replace_seal_in_content(content: str, old_name: str, new_name: str) -> str:
    if not content or not old_name:
        return content or ""
    prefix = ""
    match = re.match(r'^(作者印[：:]\s*)', content)
    if match:
        prefix = match.group(1)
        content = content[len(prefix):]
    names = re.split(r'[、，,]', content)
    names = [new_name if n.strip() == old_name else n.strip() for n in names if n.strip()]
    return prefix + "、".join(names)


def _get_seal_images(conn, seal_id: int) -> list:
    rows = conn.execute(
        "SELECT id, path, thumbnail_path, description, sort_order FROM seal_images WHERE seal_id = ? ORDER BY sort_order, id",
        (seal_id,)
    ).fetchall()
    result = []
    for r in rows:
        path = r["path"]
        if path:
            fname = os.path.basename(path)
            full = os.path.join(SEAL_DIR, fname)
            if not os.path.exists(full):
                continue
        result.append({
            "id": r["id"],
            "path": path,
            "thumb_url": r["thumbnail_path"] if r["thumbnail_path"] else path,
            "description": r["description"] or "",
            "sort_order": r["sort_order"]
        })
    return result


def _delete_seal_image_files(conn, seal_id: int):
    rows = conn.execute("SELECT path, thumbnail_path FROM seal_images WHERE seal_id = ?", (seal_id,)).fetchall()
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for r in rows:
        for p in [r["path"], r["thumbnail_path"]]:
            if p:
                full_path = os.path.join(base, p.lstrip("/"))
                if os.path.exists(full_path):
                    os.remove(full_path)


# ============ 数据模型 ============

class SealCreate(BaseModel):
    name: str
    artist_id: Optional[int] = None
    artist_name: Optional[str] = None
    seal_type: Optional[str] = "名章"
    description: Optional[str] = ""
    source: Optional[str] = ""

class SealUpdate(BaseModel):
    name: Optional[str] = None
    artist_id: Optional[int] = None
    artist_name: Optional[str] = None
    seal_type: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    merge_on_conflict: Optional[bool] = False
    emotion_score: Optional[float] = None
    emotion_category: Optional[str] = None
    emotion_desc: Optional[str] = None

class BatchDeleteRequest(BaseModel):
    ids: List[int]

class SealImageUpdate(BaseModel):
    description: Optional[str] = None
    sort_order: Optional[int] = None


# ============ API 端点 ============

@router.get("")
async def list_seals(
    artist: Optional[str] = None,
    seal_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    conn = get_db_connection()
    try:
        query = "SELECT * FROM seals WHERE 1=1"
        params = []
        if artist and artist != "all":
            query += " AND artist_name LIKE ?"
            params.append(f"%{artist}%")
        if seal_type:
            query += " AND seal_type = ?"
            params.append(seal_type)

        rows = conn.execute(query, params).fetchall()

        # usage_count：指定 artist 时只统计该作者作品，否则全局
        if artist and artist != "all":
            all_contents = conn.execute(
                "SELECT seal_content FROM tubi_analyses "
                "WHERE artist LIKE ? AND seal_content IS NOT NULL AND seal_content != ''",
                (f"%{artist}%",)
            ).fetchall()
        else:
            all_contents = conn.execute(
                "SELECT seal_content FROM tubi_analyses WHERE seal_content IS NOT NULL AND seal_content != ''"
            ).fetchall()
        content_sets = []
        for c in all_contents:
            raw = c["seal_content"] or ""
            cleaned = re.sub(r'^作者印[：:]\s*', '', raw)
            names = set(n.strip() for n in re.split(r'[、，,]', cleaned) if n.strip())
            content_sets.append(names)

        seals = []
        for row in rows:
            seal = dict(row)
            seal["images"] = _get_seal_images(conn, seal["id"])
            seal_name = seal["name"]
            usage = sum(1 for ns in content_sets if seal_name in ns)
            seal["usage_count"] = usage
            seals.append(seal)

        seals.sort(key=lambda s: s["usage_count"], reverse=True)

        total = len(seals)
        paginated = seals[skip:skip + limit]

        return {"success": True, "seals": paginated, "total": total}
    finally:
        conn.close()


@router.get("/by-name/{name}")
async def get_seal_by_name(
    name: str,
    artist: Optional[str] = None,
):
    conn = get_db_connection()
    try:
        query = "SELECT * FROM seals WHERE name = ?"
        params = [name]
        if artist and artist != "all":
            query += " AND artist_name LIKE ?"
            params.append(f"%{artist}%")

        seal = conn.execute(query, params).fetchone()
        if not seal:
            # 不带 artist 再试一次
            seal = conn.execute("SELECT * FROM seals WHERE name = ?", [name]).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail=f"印章 '{name}' 不存在")

        seal = dict(seal)
        seal["images"] = _get_seal_images(conn, seal["id"])
        return {"success": True, "seal": seal}
    finally:
        conn.close()


@router.post("/batch-delete")
async def batch_delete_seals(req: BatchDeleteRequest, admin=Depends(require_admin_role)):
    if not req.ids:
        raise HTTPException(status_code=400, detail="未选择任何印章")
    conn = get_db_connection()
    try:
        placeholders = ",".join("?" * len(req.ids))
        seals = conn.execute(
            f"SELECT * FROM seals WHERE id IN ({placeholders})", req.ids
        ).fetchall()
        if not seals:
            raise HTTPException(status_code=404, detail="未找到指定印章")

        all_rows = conn.execute(
            "SELECT id, seal_content FROM tubi_analyses "
            "WHERE seal_content IS NOT NULL AND seal_content != ''"
        ).fetchall()

        total_updated = 0
        deleted_names = []
        for seal in seals:
            seal_name = seal["name"]
            deleted_names.append(seal_name)
            for row_obj in all_rows:
                content = row_obj["seal_content"] or ""
                if seal_name not in content:
                    continue
                new_content = _remove_seal_from_content(content, seal_name)
                if new_content != content:
                    conn.execute(
                        "UPDATE tubi_analyses SET seal_content = ? WHERE id = ?",
                        (new_content, row_obj["id"])
                    )
                    total_updated += 1
            _delete_seal_image_files(conn, seal["id"])
            conn.execute("DELETE FROM seal_images WHERE seal_id = ?", (seal["id"],))

        conn.execute(
            f"DELETE FROM seals WHERE id IN ({placeholders})", req.ids
        )
        conn.commit()
        return {
            "success": True,
            "message": f"已删除 {len(seals)} 个印章（{', '.join(deleted_names)}），{total_updated} 个作品的印章内容已更新",
            "deleted_count": len(seals),
            "updated_count": total_updated
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{seal_id}/artworks")
async def get_seal_artworks(seal_id: int):
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")

        seal_name = seal["name"]
        rows = conn.execute(
            "SELECT id, image_id, title, artist, year, seal_content, status, thumbnail_path "
            "FROM tubi_analyses WHERE seal_content LIKE ?",
            (f"%{seal_name}%",)
        ).fetchall()

        artworks = []
        for row in rows:
            content = row["seal_content"] or ""
            names = re.split(r'[、，,]', re.sub(r'^作者印[：:]\s*', '', content))
            names = [n.strip() for n in names if n.strip()]
            if seal_name in names:
                artworks.append(dict(row))

        return {"success": True, "artworks": artworks, "count": len(artworks)}
    finally:
        conn.close()


@router.get("/{seal_id}")
async def get_seal(seal_id: int):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="印章不存在")
        seal = dict(row)
        seal["images"] = _get_seal_images(conn, seal["id"])
        return {"success": True, "seal": seal}
    finally:
        conn.close()


@router.post("")
async def create_seal(seal: SealCreate):
    conn = get_db_connection()
    try:
        now = datetime.now().isoformat()
        cursor = conn.execute(
            "INSERT INTO seals (name, artist_id, artist_name, seal_type, description, source, images, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (seal.name, seal.artist_id, seal.artist_name, seal.seal_type, seal.description, seal.source or "", "[]", now, now)
        )
        conn.commit()
        return {"success": True, "id": cursor.lastrowid, "message": "印章创建成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.put("/{seal_id}")
async def update_seal(seal_id: int, seal: SealUpdate):
    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="印章不存在")

        updates = {}
        if seal.name is not None:
            if seal.name != existing["name"]:
                conflict = conn.execute(
                    "SELECT id FROM seals WHERE name = ? AND id != ?",
                    (seal.name, seal_id)
                ).fetchone()
                if conflict:
                    if seal.merge_on_conflict:
                        old_name = existing["name"]
                        new_name = seal.name
                        rows = conn.execute(
                            "SELECT id, seal_content FROM tubi_analyses WHERE seal_content LIKE ?",
                            (f"%{old_name}%",)
                        ).fetchall()
                        for row_obj in rows:
                            new_content = _replace_seal_in_content(row_obj["seal_content"], old_name, new_name)
                            conn.execute(
                                "UPDATE tubi_analyses SET seal_content = ? WHERE id = ?",
                                (new_content, row_obj["id"])
                            )
                        _delete_seal_image_files(conn, seal_id)
                        conn.execute("DELETE FROM seal_images WHERE seal_id = ?", (seal_id,))
                        conn.execute("DELETE FROM seals WHERE id = ?", (seal_id,))
                        conn.commit()
                        return {"success": True, "message": "印章已合并", "merged": True}
                    else:
                        raise HTTPException(
                            status_code=409,
                            detail=f"印章名「{seal.name}」已存在，是否合并？"
                        )

            old_name = existing["name"]
            new_name = seal.name
            if old_name != new_name:
                rows = conn.execute(
                    "SELECT id, seal_content FROM tubi_analyses WHERE seal_content LIKE ?",
                    (f"%{old_name}%",)
                ).fetchall()
                for row_obj in rows:
                    new_content = _replace_seal_in_content(row_obj["seal_content"], old_name, new_name)
                    conn.execute(
                        "UPDATE tubi_analyses SET seal_content = ? WHERE id = ?",
                        (new_content, row_obj["id"])
                    )
            updates["name"] = seal.name

        if seal.artist_id is not None:
            updates["artist_id"] = seal.artist_id
        if seal.artist_name is not None:
            updates["artist_name"] = seal.artist_name
        if seal.seal_type is not None:
            updates["seal_type"] = seal.seal_type
        if seal.description is not None:
            updates["description"] = seal.description
        if seal.source is not None:
            updates["source"] = seal.source
        if seal.emotion_score is not None:
            updates["emotion_score"] = seal.emotion_score
        if seal.emotion_category is not None:
            updates["emotion_category"] = seal.emotion_category
        if seal.emotion_desc is not None:
            updates["emotion_desc"] = seal.emotion_desc

        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE seals SET {set_clause} WHERE id = ?",
                (*updates.values(), seal_id)
            )

        conn.commit()
        return {"success": True, "message": "印章更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{seal_id}")
async def delete_seal(seal_id: int, admin=Depends(require_admin_role)):
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")

        seal_name = seal["name"]

        rows = conn.execute(
            "SELECT id, seal_content FROM tubi_analyses WHERE seal_content LIKE ?",
            (f"%{seal_name}%",)
        ).fetchall()
        updated_count = 0
        for row_obj in rows:
            new_content = _remove_seal_from_content(row_obj["seal_content"], seal_name)
            if new_content != row_obj["seal_content"]:
                conn.execute(
                    "UPDATE tubi_analyses SET seal_content = ? WHERE id = ?",
                    (new_content, row_obj["id"])
                )
                updated_count += 1

        _delete_seal_image_files(conn, seal["id"])
        conn.execute("DELETE FROM seal_images WHERE seal_id = ?", (seal["id"],))
        conn.execute("DELETE FROM seals WHERE id = ?", (seal_id,))
        conn.commit()
        return {
            "success": True,
            "message": f"印章「{seal_name}」已删除，{updated_count} 个作品的印章内容已更新",
            "updated_count": updated_count
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{seal_id}/images")
async def upload_seal_image(seal_id: int, file: UploadFile = File(...), description: str = Form("")):
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")

        os.makedirs(SEAL_DIR, exist_ok=True)

        ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
        import random
        filename = f"seal_{seal_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.randint(1000,9999)}{ext}"
        filepath = os.path.join(SEAL_DIR, filename)
        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)

        img_url = f"/static/seals/{filename}"

        thumb_filename = f"thumb_{filename.rsplit('.', 1)[0]}.jpg"
        thumb_path = os.path.join(SEAL_THUMB_DIR, thumb_filename)
        _create_seal_thumbnail(filepath, thumb_path)
        thumb_url = f"/static/seals/thumbs/{thumb_filename}" if os.path.exists(thumb_path) else ""

        next_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM seal_images WHERE seal_id = ?", (seal_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO seal_images (seal_id, path, thumbnail_path, description, sort_order) VALUES (?, ?, ?, ?, ?)",
            (seal_id, img_url, thumb_url, description, next_order)
        )
        conn.execute(
            "UPDATE seals SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), seal_id)
        )
        conn.commit()
        images = _get_seal_images(conn, seal_id)
        return {"success": True, "url": img_url, "images": images}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.put("/{seal_id}/images/{image_id}")
async def update_seal_image(seal_id: int, image_id: int, data: SealImageUpdate):
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")
        img = conn.execute("SELECT * FROM seal_images WHERE id = ? AND seal_id = ?", (image_id, seal_id)).fetchone()
        if not img:
            raise HTTPException(status_code=404, detail="图片不存在")

        if data.description is not None:
            conn.execute("UPDATE seal_images SET description = ? WHERE id = ?", (data.description, image_id))
        if data.sort_order is not None:
            conn.execute("UPDATE seal_images SET sort_order = ? WHERE id = ?", (data.sort_order, image_id))
        conn.execute(
            "UPDATE seals SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), seal_id)
        )
        conn.commit()
        return {"success": True, "images": _get_seal_images(conn, seal_id)}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{seal_id}/images/{image_id}")
async def delete_seal_image(seal_id: int, image_id: int):
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")
        img = conn.execute("SELECT * FROM seal_images WHERE id = ? AND seal_id = ?", (image_id, seal_id)).fetchone()
        if not img:
            raise HTTPException(status_code=404, detail="图片不存在")

        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        for p in [img["path"], img["thumbnail_path"]]:
            if p:
                full_path = os.path.join(base, p.lstrip("/"))
                if os.path.exists(full_path):
                    os.remove(full_path)

        conn.execute("DELETE FROM seal_images WHERE id = ?", (image_id,))
        conn.execute(
            "UPDATE seals SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), seal_id)
        )
        conn.commit()
        return {"success": True, "images": _get_seal_images(conn, seal_id)}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/extract")
async def extract_seals_from_analyses():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, seal_content, artist FROM tubi_analyses "
            "WHERE seal_content IS NOT NULL AND seal_content != ''"
        ).fetchall()

        extracted = 0
        skipped = 0
        for row in rows:
            content = row["seal_content"] or ""
            artist_name = row["artist"] or ""

            content = re.sub(r'^作者印[：:]\s*', '', content)
            names = re.split(r'[、，,]', content)
            names = [n.strip() for n in names if n.strip()]

            for name in names:
                existing = conn.execute(
                    "SELECT id FROM seals WHERE name = ?", (name,)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue

                artist_id = None
                if artist_name:
                    artist_row = conn.execute(
                        "SELECT id FROM artists WHERE name LIKE ?", (f"%{artist_name}%",)
                    ).fetchone()
                    if artist_row:
                        artist_id = artist_row["id"]

                now = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO seals (name, artist_id, artist_name, seal_type, images, description, source, created_at, updated_at) "
                    "VALUES (?, ?, ?, '名章', '[]', '', '', ?, ?)",
                    (name, artist_id, artist_name, now, now)
                )
                extracted += 1

        conn.commit()
        return {
            "success": True,
            "message": f"提取完成：新增 {extracted} 个印章，跳过 {skipped} 个已存在",
            "extracted": extracted,
            "skipped": skipped
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/by-name/{name}")
async def get_seal_by_name(name: str):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM seals WHERE name = ?", (name,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="印章不存在")
        seal = dict(row)
        seal["images"] = _get_seal_images(conn, seal["id"])
        return {"success": True, "seal": seal}
    finally:
        conn.close()
