"""
印章管理 API
- CRUD
- 删除/重命名时同步 seal_content
- 关联作品查询
- 图片上传/删除
- 从 tubi_analyses 提取印章数据
"""
import os
import json
import re
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.auth import require_admin

router = APIRouter(prefix="/seals", tags=["seals"])

SEAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "seals")


# ============ 辅助函数 ============

def _remove_seal_from_content(content: str, seal_name: str) -> str:
    """从 seal_content 中移除指定印章名"""
    if not content or not seal_name:
        return content or ""
    # 去掉"作者印："前缀
    prefix = ""
    match = re.match(r'^(作者印[：:]\s*)', content)
    if match:
        prefix = match.group(1)
        content = content[len(prefix):]
    # 按顿号/逗号分割
    names = re.split(r'[、，,]', content)
    names = [n.strip() for n in names if n.strip() and n.strip() != seal_name]
    if not names:
        return ""
    return prefix + "、".join(names)


def _replace_seal_in_content(content: str, old_name: str, new_name: str) -> str:
    """在 seal_content 中替换印章名"""
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


# ============ 数据模型 ============

class SealCreate(BaseModel):
    name: str
    artist_id: Optional[int] = None
    artist_name: Optional[str] = None
    seal_type: Optional[str] = "名章"
    description: Optional[str] = ""

class SealUpdate(BaseModel):
    name: Optional[str] = None
    artist_id: Optional[int] = None
    artist_name: Optional[str] = None
    seal_type: Optional[str] = None
    description: Optional[str] = None
    merge_on_conflict: Optional[bool] = False

class BatchDeleteRequest(BaseModel):
    ids: List[int]


# ============ API 端点 ============

@router.get("")
async def list_seals(
    artist: Optional[str] = None,
    seal_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """列出所有印章"""
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
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, skip])

        rows = conn.execute(query, params).fetchall()

        # 一次性获取所有 seal_content，用于精确匹配统计
        all_contents = conn.execute(
            "SELECT seal_content FROM tubi_analyses WHERE seal_content IS NOT NULL AND seal_content != ''"
        ).fetchall()
        # 预处理：将每条 seal_content 拆分为印章名集合
        content_sets = []
        for c in all_contents:
            raw = c["seal_content"] or ""
            cleaned = re.sub(r'^作者印[：:]\s*', '', raw)
            names = set(n.strip() for n in re.split(r'[、，,]', cleaned) if n.strip())
            content_sets.append(names)

        seals = []
        for row in rows:
            seal = dict(row)
            if seal.get("images"):
                try:
                    seal["images"] = json.loads(seal["images"])
                except (json.JSONDecodeError, TypeError):
                    seal["images"] = []
            else:
                seal["images"] = []
            # 精确匹配统计使用频率
            seal_name = seal["name"]
            usage = sum(1 for ns in content_sets if seal_name in ns)
            seal["usage_count"] = usage
            seals.append(seal)

        # 按使用频率降序排序
        seals.sort(key=lambda s: s["usage_count"], reverse=True)

        count_query = "SELECT COUNT(*) FROM seals WHERE 1=1"
        count_params = []
        if artist and artist != "all":
            count_query += " AND artist_name LIKE ?"
            count_params.append(f"%{artist}%")
        if seal_type:
            count_query += " AND seal_type = ?"
            count_params.append(seal_type)
        total = conn.execute(count_query, count_params).fetchone()[0]

        return {"success": True, "seals": seals, "total": total}
    finally:
        conn.close()


@router.post("/batch-delete")
async def batch_delete_seals(req: BatchDeleteRequest, admin=Depends(require_admin)):
    """批量删除印章（同步清理所有作品的 seal_content）"""
    if not req.ids:
        raise HTTPException(status_code=400, detail="未选择任何印章")
    conn = get_db_connection()
    try:
        # 获取所有待删除印章
        placeholders = ",".join("?" * len(req.ids))
        seals = conn.execute(
            f"SELECT * FROM seals WHERE id IN ({placeholders})", req.ids
        ).fetchall()
        if not seals:
            raise HTTPException(status_code=404, detail="未找到指定印章")

        # 一次性获取所有 seal_content
        all_rows = conn.execute(
            "SELECT id, seal_content FROM tubi_analyses "
            "WHERE seal_content IS NOT NULL AND seal_content != ''"
        ).fetchall()

        total_updated = 0
        deleted_names = []
        for seal in seals:
            seal_name = seal["name"]
            deleted_names.append(seal_name)
            # 从所有作品的 seal_content 中移除该印章
            for row in all_rows:
                content = row["seal_content"] or ""
                if seal_name not in content:
                    continue
                new_content = _remove_seal_from_content(content, seal_name)
                if new_content != content:
                    conn.execute(
                        "UPDATE tubi_analyses SET seal_content = ? WHERE id = ?",
                        (new_content, row["id"])
                    )
                    total_updated += 1
            # 删除印章图片文件
            if seal["images"]:
                try:
                    images = json.loads(seal["images"])
                    for img_path in images:
                        full_path = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            img_path.lstrip("/")
                        )
                        if os.path.exists(full_path):
                            os.remove(full_path)
                except (json.JSONDecodeError, TypeError):
                    pass

        # 批量删除印章记录
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


# ⚠️ 此路由必须在 /{seal_id} 之前定义
@router.get("/{seal_id}/artworks")
async def get_seal_artworks(seal_id: int):
    """获取使用某印章的所有作品"""
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")

        seal_name = seal["name"]
        # 查找 seal_content 中包含该印章名的作品
        rows = conn.execute(
            "SELECT id, image_id, title, artist, year, seal_content, status, thumbnail_path "
            "FROM tubi_analyses WHERE seal_content LIKE ?",
            (f"%{seal_name}%",)
        ).fetchall()

        artworks = []
        for row in rows:
            # 精确匹配：检查印章名是否在分割后的列表中
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
    """获取单个印章详情"""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="印章不存在")
        seal = dict(row)
        if seal.get("images"):
            try:
                seal["images"] = json.loads(seal["images"])
            except (json.JSONDecodeError, TypeError):
                seal["images"] = []
        else:
            seal["images"] = []
        return {"success": True, "seal": seal}
    finally:
        conn.close()


@router.post("")
async def create_seal(seal: SealCreate):
    """创建印章"""
    conn = get_db_connection()
    try:
        now = datetime.now().isoformat()
        cursor = conn.execute(
            "INSERT INTO seals (name, artist_id, artist_name, seal_type, description, images, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (seal.name, seal.artist_id, seal.artist_name, seal.seal_type, seal.description, "[]", now, now)
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
    """更新印章（重命名时同步 seal_content）"""
    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="印章不存在")

        updates = {}
        if seal.name is not None:
            # 检查重名冲突
            if seal.name != existing["name"]:
                conflict = conn.execute(
                    "SELECT id FROM seals WHERE name = ? AND id != ?",
                    (seal.name, seal_id)
                ).fetchone()
                if conflict:
                    if seal.merge_on_conflict:
                        # 合并：删除当前印章，把 seal_content 中的旧名改为新名
                        old_name = existing["name"]
                        new_name = seal.name
                        # 更新所有作品的 seal_content
                        rows = conn.execute(
                            "SELECT id, seal_content FROM tubi_analyses WHERE seal_content LIKE ?",
                            (f"%{old_name}%",)
                        ).fetchall()
                        for row in rows:
                            new_content = _replace_seal_in_content(row["seal_content"], old_name, new_name)
                            conn.execute(
                                "UPDATE tubi_analyses SET seal_content = ? WHERE id = ?",
                                (new_content, row["id"])
                            )
                        # 删除当前印章
                        conn.execute("DELETE FROM seals WHERE id = ?", (seal_id,))
                        conn.commit()
                        return {"success": True, "message": "印章已合并", "merged": True}
                    else:
                        raise HTTPException(
                            status_code=409,
                            detail=f"印章名「{seal.name}」已存在，是否合并？"
                        )

            # 重命名：同步 seal_content
            old_name = existing["name"]
            new_name = seal.name
            if old_name != new_name:
                rows = conn.execute(
                    "SELECT id, seal_content FROM tubi_analyses WHERE seal_content LIKE ?",
                    (f"%{old_name}%",)
                ).fetchall()
                for row in rows:
                    new_content = _replace_seal_in_content(row["seal_content"], old_name, new_name)
                    conn.execute(
                        "UPDATE tubi_analyses SET seal_content = ? WHERE id = ?",
                        (new_content, row["id"])
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
async def delete_seal(seal_id: int, admin=Depends(require_admin)):
    """删除印章（同步清理 seal_content）"""
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")

        seal_name = seal["name"]

        # 清理所有作品中的 seal_content
        rows = conn.execute(
            "SELECT id, seal_content FROM tubi_analyses WHERE seal_content LIKE ?",
            (f"%{seal_name}%",)
        ).fetchall()
        updated_count = 0
        for row in rows:
            new_content = _remove_seal_from_content(row["seal_content"], seal_name)
            if new_content != row["seal_content"]:
                conn.execute(
                    "UPDATE tubi_analyses SET seal_content = ? WHERE id = ?",
                    (new_content, row["id"])
                )
                updated_count += 1

        # 删除印章图片文件
        if seal["images"]:
            try:
                images = json.loads(seal["images"])
                for img_path in images:
                    full_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        img_path.lstrip("/")
                    )
                    if os.path.exists(full_path):
                        os.remove(full_path)
            except (json.JSONDecodeError, TypeError):
                pass

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


@router.post("/{seal_id}/upload-image")
async def upload_seal_image(seal_id: int, file: UploadFile = File(...)):
    """上传印章图片"""
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")

        os.makedirs(SEAL_DIR, exist_ok=True)

        # 保存文件
        ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
        filename = f"seal_{seal_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
        filepath = os.path.join(SEAL_DIR, filename)
        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)

        # 更新数据库
        images = []
        if seal["images"]:
            try:
                images = json.loads(seal["images"])
            except (json.JSONDecodeError, TypeError):
                images = []
        img_url = f"/static/seals/{filename}"
        images.append(img_url)
        conn.execute(
            "UPDATE seals SET images = ?, updated_at = ? WHERE id = ?",
            (json.dumps(images, ensure_ascii=False), datetime.now().isoformat(), seal_id)
        )
        conn.commit()
        return {"success": True, "url": img_url, "images": images}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{seal_id}/images/{image_index}")
async def delete_seal_image(seal_id: int, image_index: int):
    """删除印章图片"""
    conn = get_db_connection()
    try:
        seal = conn.execute("SELECT * FROM seals WHERE id = ?", (seal_id,)).fetchone()
        if not seal:
            raise HTTPException(status_code=404, detail="印章不存在")

        images = []
        if seal["images"]:
            try:
                images = json.loads(seal["images"])
            except (json.JSONDecodeError, TypeError):
                images = []

        if image_index < 0 or image_index >= len(images):
            raise HTTPException(status_code=400, detail="图片索引无效")

        # 删除文件
        img_url = images[image_index]
        full_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            img_url.lstrip("/")
        )
        if os.path.exists(full_path):
            os.remove(full_path)

        images.pop(image_index)
        conn.execute(
            "UPDATE seals SET images = ?, updated_at = ? WHERE id = ?",
            (json.dumps(images, ensure_ascii=False), datetime.now().isoformat(), seal_id)
        )
        conn.commit()
        return {"success": True, "images": images}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/extract")
async def extract_seals_from_analyses():
    """从 tubi_analyses.seal_content 提取印章数据"""
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

            # 去掉"作者印："前缀
            content = re.sub(r'^作者印[：:]\s*', '', content)
            # 按顿号/逗号分割
            names = re.split(r'[、，,]', content)
            names = [n.strip() for n in names if n.strip()]

            for name in names:
                # 检查是否已存在
                existing = conn.execute(
                    "SELECT id FROM seals WHERE name = ?", (name,)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue

                # 获取 artist_id
                artist_id = None
                if artist_name:
                    artist_row = conn.execute(
                        "SELECT id FROM artists WHERE name LIKE ?", (f"%{artist_name}%",)
                    ).fetchone()
                    if artist_row:
                        artist_id = artist_row["id"]

                now = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO seals (name, artist_id, artist_name, seal_type, images, description, created_at, updated_at) "
                    "VALUES (?, ?, ?, '名章', '[]', '', ?, ?)",
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
    """按名称获取印章"""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM seals WHERE name = ?", (name,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="印章不存在")
        seal = dict(row)
        if seal.get("images"):
            try:
                seal["images"] = json.loads(seal["images"])
            except (json.JSONDecodeError, TypeError):
                seal["images"] = []
        else:
            seal["images"] = []
        return {"success": True, "seal": seal}
    finally:
        conn.close()
