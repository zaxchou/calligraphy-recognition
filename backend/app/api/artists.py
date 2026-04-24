"""
画家信息管理 API
- CRUD
- AI一键查询填充
"""
import os
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.database import get_db_connection

router = APIRouter(prefix="/artists", tags=["artists"])


# ============ 数据模型 ============

class ArtistCreate(BaseModel):
    name: str
    birth_year: Optional[int] = None
    background: Optional[str] = ""
    sentiment_note: Optional[str] = ""
    theme_note: Optional[str] = ""
    theme_aliases: Optional[str] = ""
    keyword_rules: Optional[str] = ""
    specialties: Optional[str] = ""
    enabled: Optional[int] = 1

class ArtistUpdate(BaseModel):
    name: Optional[str] = None
    birth_year: Optional[int] = None
    background: Optional[str] = None
    sentiment_note: Optional[str] = None
    theme_note: Optional[str] = None
    theme_aliases: Optional[str] = None
    keyword_rules: Optional[str] = None
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
async def create_artist(artist: ArtistCreate):
    """创建画家"""
    conn = get_db_connection()
    try:
        now = datetime.now().isoformat()
        cursor = conn.execute(
            "INSERT INTO artists (name, birth_year, background, sentiment_note, theme_note, "
            "theme_aliases, keyword_rules, specialties, enabled, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (artist.name, artist.birth_year, artist.background, artist.sentiment_note,
             artist.theme_note, artist.theme_aliases, artist.keyword_rules,
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
async def update_artist(artist_id: int, artist: ArtistUpdate):
    """更新画家"""
    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="画家不存在")

        updates = {}
        for field in ["name", "birth_year", "background", "sentiment_note", "theme_note",
                       "theme_aliases", "keyword_rules", "specialties", "enabled"]:
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
async def delete_artist(artist_id: int):
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
async def sync_artist_name(artist_id: int, req: SyncNameRequest):
    """同步画家姓名到所有相关作品"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        # 更新 tubi_analyses 中的 artist 字段
        result = conn.execute(
            "UPDATE tubi_analyses SET artist = ? WHERE artist = ?",
            (req.new_name, req.old_name)
        )
        updated = result.rowcount

        # 更新 seals 中的 artist_name 字段
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
async def ai_fill_artist(artist_id: int):
    """AI一键查询画家信息并填充"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        artist_name = artist["name"]

        # 调用 LLM 查询画家信息
        try:
            from openai import OpenAI
            from app.core.config import get_settings
            settings = get_settings()
            client = OpenAI(
                api_key=settings.QWEN_API_KEY,
                base_url=settings.QWEN_BASE_URL
            )
            prompt = f"""请简要介绍清代画家{artist_name}的以下信息，用JSON格式返回：
{{
  "birth_year": 出生年份（整数），
  "background": "背景简介（50字以内）",
  "sentiment_note": "情感倾向说明（如：晚年多悲凉之感）",
  "theme_note": "主题倾向说明（如：善画花鸟虫鱼）",
  "specialties": "专长（如：写意花鸟）"
}}
只返回JSON，不要其他文字。"""

            response = client.chat.completions.create(
                model="qwen-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            result = response.choices[0].message.content
            # 解析JSON
            import re
            json_match = re.search(r'\{[^}]+\}', result, re.DOTALL)
            if json_match:
                info = json.loads(json_match.group())
                updates = {}
                if info.get("birth_year") and not artist["birth_year"]:
                    updates["birth_year"] = int(info["birth_year"])
                if info.get("background") and not artist["background"]:
                    updates["background"] = info["background"]
                if info.get("sentiment_note") and not artist["sentiment_note"]:
                    updates["sentiment_note"] = info["sentiment_note"]
                if info.get("theme_note") and not artist["theme_note"]:
                    updates["theme_note"] = info["theme_note"]
                if info.get("specialties") and not artist["specialties"]:
                    updates["specialties"] = info["specialties"]

                if updates:
                    updates["updated_at"] = datetime.now().isoformat()
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    conn.execute(
                        f"UPDATE artists SET {set_clause} WHERE id = ?",
                        (*updates.values(), artist_id)
                    )
                    conn.commit()
                    return {"success": True, "message": "AI查询完成，信息已填充", "updates": updates}
                else:
                    return {"success": True, "message": "AI查询完成，无需更新"}
            else:
                return {"success": True, "message": "AI查询完成，但无法解析结果"}
        except ImportError:
            # qwen_service 不可用时，返回提示
            return {"success": False, "message": "AI服务不可用"}
        except Exception as e:
            return {"success": False, "message": f"AI查询失败: {str(e)}"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
