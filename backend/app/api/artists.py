"""
画家信息管理 API
- CRUD（仅元数据：姓名/出生年/背景/专长/启用状态）
- AI一键查询填充（同时写 artists 表 + artist_rules 表）
- 画家规则独立管理：/api/v1/artist-rules
"""
import os
import json
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.auth import require_admin, require_editor

router = APIRouter(prefix="/artists", tags=["artists"])


# ============ 数据模型 ============

class ArtistCreate(BaseModel):
    name: str
    birth_year: Optional[int] = None
    background: Optional[str] = ""
    specialties: Optional[str] = ""
    enabled: Optional[int] = 1

class ArtistUpdate(BaseModel):
    name: Optional[str] = None
    birth_year: Optional[int] = None
    background: Optional[str] = None
    specialties: Optional[str] = None
    enabled: Optional[int] = None


# ============ API 端点 ============

@router.get("")
async def list_artists():
    """列出所有画家"""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM artists ORDER BY id").fetchall()
        artists = [dict(row) for row in rows]
        return {"success": True, "artists": artists}
    finally:
        conn.close()


@router.get("/{artist_id}")
async def get_artist(artist_id: int):
    """获取单个画家"""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="画家不存在")
        return {"success": True, "artist": dict(row)}
    finally:
        conn.close()


@router.get("/by-name/{name}")
async def get_artist_by_name(name: str):
    """按名称获取画家"""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM artists WHERE name = ?", (name,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="画家不存在")
        return {"success": True, "artist": dict(row)}
    finally:
        conn.close()


@router.post("")
async def create_artist(artist: ArtistCreate, editor=Depends(require_editor)):
    """创建画家"""
    conn = get_db_connection()
    try:
        now = datetime.now().isoformat()
        cursor = conn.execute(
            "INSERT INTO artists (name, birth_year, background, specialties, enabled, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (artist.name, artist.birth_year, artist.background,
             artist.specialties, artist.enabled, now, now)
        )
        conn.commit()
        return {"success": True, "id": cursor.lastrowid, "message": "画家创建成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.put("/{artist_id}")
async def update_artist(artist_id: int, artist: ArtistUpdate, editor=Depends(require_editor)):
    """更新画家"""
    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="画家不存在")

        updates = {}
        for field in ["name", "birth_year", "background", "specialties", "enabled"]:
            val = getattr(artist, field, None)
            if val is not None:
                updates[field] = val

        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE artists SET {set_clause} WHERE id = ?",
                (*updates.values(), artist_id)
            )
            conn.commit()

        return {"success": True, "message": "画家更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{artist_id}")
async def delete_artist(artist_id: int, admin=Depends(require_admin)):
    """删除画家"""
    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="画家不存在")

        conn.execute("DELETE FROM artists WHERE id = ?", (artist_id,))
        conn.commit()
        return {"success": True, "message": "画家已删除"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


class SyncNameRequest(BaseModel):
    old_name: str
    new_name: str


@router.post("/{artist_id}/sync-name")
async def sync_artist_name(artist_id: int, req: SyncNameRequest, editor=Depends(require_editor)):
    """同步画家姓名到所有相关作品"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        result = conn.execute(
            "UPDATE tubi_analyses SET artist = ? WHERE artist = ?",
            (req.new_name, req.old_name)
        )
        updated = result.rowcount

        result2 = conn.execute(
            "UPDATE seals SET artist_name = ? WHERE artist_name = ?",
            (req.new_name, req.old_name)
        )
        seal_updated = result2.rowcount

        conn.commit()
        return {
            "success": True,
            "message": f"姓名已同步：{updated} 个作品、{seal_updated} 个印章已更新"
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{artist_id}/ai-fill")
async def ai_fill_artist(artist_id: int, editor=Depends(require_editor)):
    """AI一键查询画家信息并填充（元数据→artists表，规则→artist_rules表）"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        artist_name = artist["name"]

        try:
            from app.services.qwen_llm_client import call_qwen_chat

            has_rules = conn.execute(
                "SELECT id FROM artist_rules WHERE artist_name = ?", (artist_name,)
            ).fetchone()

            if has_rules:
                prompt = f"""请简要介绍清代画家{artist_name}的以下信息，用JSON格式返回：
{{
  "birth_year": 出生年份（整数），
  "background": "背景简介（50字以内）",
  "specialties": "专长（如：写意花鸟）"
}}
只返回JSON，不要其他文字。"""
            else:
                prompt = f"""请简要介绍画家{artist_name}的以下信息，用JSON格式返回：
{{
  "birth_year": 出生年份（整数），
  "background": "背景简介（50字以内）",
  "specialties": "专长（如：写意花鸟）",
  "sentiment_note": "情感倾向说明（如：晚年多悲凉之感，50字以内）",
  "theme_note": "主题倾向说明（如：善画花鸟虫鱼，50字以内）",
  "emotion_baseline": 情感基线值（-1.0~1.0之间的浮点数）
}}
只返回JSON，不要其他文字。"""

            response = call_qwen_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            if "error" in response:
                return {"success": False, "message": f"AI调用失败: {response['error']}"}
            result = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            json_match = re.search(r'\{[^}]+\}', result, re.DOTALL)
            if json_match:
                info = json.loads(json_match.group())

                artist_updates = {}
                if info.get("birth_year") and not artist["birth_year"]:
                    artist_updates["birth_year"] = int(info["birth_year"])
                if info.get("background") and not artist["background"]:
                    artist_updates["background"] = info["background"]
                if info.get("specialties") and not artist["specialties"]:
                    artist_updates["specialties"] = info["specialties"]

                if artist_updates:
                    artist_updates["updated_at"] = datetime.now().isoformat()
                    set_clause = ", ".join(f"{k} = ?" for k in artist_updates)
                    conn.execute(
                        f"UPDATE artists SET {set_clause} WHERE id = ?",
                        (*artist_updates.values(), artist_id)
                    )

                rules_created = False
                if not has_rules and (info.get("sentiment_note") or info.get("emotion_baseline") is not None):
                    now = datetime.now().isoformat()
                    conn.execute(
                        """INSERT OR IGNORE INTO artist_rules (
                            artist_name, emotion_baseline, life_stages, sentiment_note,
                            theme_note, theme_exceptions, expected_theme_distribution,
                            expected_sentiment_distribution, rules_version, created_at, updated_at
                        ) VALUES (?, ?, '[]', ?, ?, '{}', '{}', '{}', '5.5-ai', ?, ?)""",
                        (
                            artist_name,
                            float(info.get("emotion_baseline", 0.0)),
                            info.get("sentiment_note", ""),
                            info.get("theme_note", ""),
                            now, now
                        )
                    )
                    rules_created = True

                conn.commit()

                msg = "AI查询完成"
                if artist_updates:
                    msg += "，元数据已填充"
                if rules_created:
                    msg += "，规则包已创建"
                if not artist_updates and not rules_created:
                    msg += "，无需更新"
                return {"success": True, "message": msg, "updates": artist_updates, "rules_created": rules_created}
            else:
                return {"success": True, "message": "AI查询完成，但无法解析结果"}
        except Exception as e:
            return {"success": False, "message": f"AI查询失败: {str(e)}"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
