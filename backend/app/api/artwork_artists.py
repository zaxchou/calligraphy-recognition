"""
作品-画家关联 API — /api/v1/artworks
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.auth import get_current_user, require_editor
from app.models.user import User

router = APIRouter(prefix="/artworks", tags=["作品-画家关联"])
logger = logging.getLogger(__name__)


class ArtworkArtistCreate(BaseModel):
    artist_id: int
    role: str = "author"
    sort_order: int = 0


@router.get("/{artwork_id}/artists")
async def get_artwork_artists(artwork_id: int):
    """获取作品的所有关联画家"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT aa.*, a.name as artist_name, a.alias, a.avatar_url
               FROM artwork_artists aa
               LEFT JOIN artists a ON aa.artist_id = a.id
               WHERE aa.artwork_id = ?
               ORDER BY aa.sort_order""",
            (artwork_id,),
        ).fetchall()
        return {"success": True, "artists": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/{artwork_id}/artists")
async def add_artwork_artist(
    artwork_id: int,
    req: ArtworkArtistCreate,
    user: User = Depends(get_current_user),
):
    """为作品添加画家关联"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT id FROM artists WHERE id = ?", (req.artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        existing = conn.execute(
            "SELECT id FROM artwork_artists WHERE artwork_id = ? AND artist_id = ?",
            (artwork_id, req.artist_id),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="该画家已关联到此作品")

        conn.execute(
            "INSERT INTO artwork_artists (artwork_id, artist_id, role, sort_order) VALUES (?, ?, ?, ?)",
            (artwork_id, req.artist_id, req.role, req.sort_order),
        )
        conn.commit()
        return {"success": True, "message": "画家关联已添加"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.put("/{artwork_id}/artists/{artist_id}")
async def update_artwork_artist(
    artwork_id: int,
    artist_id: int,
    req: ArtworkArtistCreate,
    user: User = Depends(get_current_user),
):
    """更新作品-画家关联（角色、排序）"""
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM artwork_artists WHERE artwork_id = ? AND artist_id = ?",
            (artwork_id, artist_id),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="关联不存在")

        conn.execute(
            "UPDATE artwork_artists SET role = ?, sort_order = ? WHERE artwork_id = ? AND artist_id = ?",
            (req.role, req.sort_order, artwork_id, artist_id),
        )
        conn.commit()
        return {"success": True, "message": "关联已更新"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{artwork_id}/artists/{artist_id}")
async def remove_artwork_artist(
    artwork_id: int,
    artist_id: int,
    user: User = Depends(get_current_user),
):
    """移除作品-画家关联"""
    conn = get_db_connection()
    try:
        conn.execute(
            "DELETE FROM artwork_artists WHERE artwork_id = ? AND artist_id = ?",
            (artwork_id, artist_id),
        )
        conn.commit()
        return {"success": True, "message": "关联已移除"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
