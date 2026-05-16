"""
画家编辑审核 API — /api/v1/artists/change-requests
"""
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from app.core.database import get_db_connection
from app.core.auth import get_current_user, require_editor
from app.models.user import User

router = APIRouter(prefix="/artists", tags=["画家编辑审核"])
logger = logging.getLogger(__name__)


@router.post("/{artist_id}/change-requests")
async def submit_artist_change_request(
    artist_id: int,
    field_name: str = Query(...),
    old_value: str = Query(default=""),
    new_value: str = Query(...),
    change_summary: str = Query(default=""),
    user: User = Depends(get_current_user),
):
    """提交画家信息修改建议"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        # editor 及以上直接修改
        if user.role in ("editor", "admin", "super_admin"):
            safe_fields = [
                "name", "alias", "dynasty", "hometown", "birth_year", "death_year",
                "avatar_url", "biography", "bio_events", "art_school", "masterpieces",
                "tags", "baidu_url", "featured", "background", "specialties",
            ]
            if field_name not in safe_fields:
                raise HTTPException(status_code=400, detail=f"不允许修改字段: {field_name}")

            now = datetime.now().isoformat()
            conn.execute(
                f"UPDATE artists SET {field_name} = ?, updated_at = ? WHERE id = ?",
                (new_value, now, artist_id),
            )
            conn.commit()
            return {"success": True, "message": "已直接更新", "direct_update": True}

        # 普通用户提交审核
        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO artist_change_requests
               (artist_id, request_type, field_name, old_value, new_value, change_summary, submitter_id, status, created_at)
               VALUES (?, 'edit_field', ?, ?, ?, ?, ?, 'pending', ?)""",
            (artist_id, field_name, old_value, new_value, change_summary, user.id, now),
        )
        conn.commit()
        return {"success": True, "message": "修改建议已提交，等待管理员审核"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{artist_id}/change-requests")
async def list_artist_change_requests(
    artist_id: int,
    status: str = Query(default="pending"),
):
    """获取某个画家的变更请求列表"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT acr.*, u.nickname as submitter_name
               FROM artist_change_requests acr
               LEFT JOIN users u ON acr.submitter_id = u.id
               WHERE acr.artist_id = ? AND acr.status = ?
               ORDER BY acr.created_at DESC""",
            (artist_id, status),
        ).fetchall()
        return {"success": True, "requests": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/change-requests/my")
async def list_my_artist_change_requests(
    user: User = Depends(get_current_user),
):
    """我的画家信息修改提交历史"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT acr.*, a.name as artist_name
               FROM artist_change_requests acr
               LEFT JOIN artists a ON acr.artist_id = a.id
               WHERE acr.submitter_id = ?
               ORDER BY acr.created_at DESC LIMIT 100""",
            (user.id,),
        ).fetchall()
        return {"success": True, "requests": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/change-requests/{request_id}/review")
async def review_artist_change_request(
    request_id: int,
    action: str = Query(..., description="approve 或 reject"),
    review_comment: str = Query(default=""),
    user: User = Depends(require_editor),
):
    """审核画家信息修改建议"""
    conn = get_db_connection()
    try:
        cr = conn.execute(
            "SELECT * FROM artist_change_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if not cr:
            raise HTTPException(status_code=404, detail="变更请求不存在")
        if cr["status"] != "pending":
            raise HTTPException(status_code=409, detail="该请求已被审核")

        now = datetime.now().isoformat()

        if action == "approve":
            field = cr["field_name"]
            new_val = cr["new_value"]
            conn.execute(
                f"UPDATE artists SET {field} = ?, updated_at = ? WHERE id = ?",
                (new_val, now, cr["artist_id"]),
            )

        conn.execute(
            "UPDATE artist_change_requests SET status = ?, reviewer_id = ?, review_comment = ?, reviewed_at = ? WHERE id = ?",
            (action, user.id, review_comment, now, request_id),
        )
        conn.commit()
        return {"success": True, "message": f"变更请求已{action == 'approve' and '批准' or '驳回'}"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
