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
from app.core.auth import require_admin_role, require_editor, require_permission

router = APIRouter(prefix="/artists", tags=["artists"])


# ============ 数据模型 ============

class ArtistCreate(BaseModel):
    name: str
    alias: Optional[str] = ""
    dynasty: Optional[str] = ""
    hometown: Optional[str] = ""
    avatar_url: Optional[str] = ""
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    biography: Optional[str] = ""
    background: Optional[str] = ""
    specialties: Optional[str] = ""
    bio_events: Optional[str] = ""
    art_school: Optional[str] = ""
    masterpieces: Optional[str] = ""
    tags: Optional[str] = ""
    baidu_url: Optional[str] = ""
    featured: Optional[int] = 0
    enabled: Optional[int] = 1
    banner_url: Optional[str] = ""
    summary: Optional[str] = ""
    nationality: Optional[str] = ""
    occupation: Optional[str] = ""
    main_achievements: Optional[str] = ""
    representative_works_text: Optional[str] = ""
    art_style: Optional[str] = ""
    influence: Optional[str] = ""
    historical_evaluation: Optional[str] = ""
    character_relations: Optional[str] = ""
    anecdotes: Optional[str] = ""
    art_chronology: Optional[str] = ""
    published_works: Optional[str] = ""
    gallery_images: Optional[str] = ""
    references: Optional[str] = ""

class ArtistUpdate(BaseModel):
    name: Optional[str] = None
    alias: Optional[str] = None
    dynasty: Optional[str] = None
    hometown: Optional[str] = None
    avatar_url: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    biography: Optional[str] = None
    background: Optional[str] = None
    specialties: Optional[str] = None
    bio_events: Optional[str] = None
    art_school: Optional[str] = None
    masterpieces: Optional[str] = None
    tags: Optional[str] = None
    baidu_url: Optional[str] = None
    featured: Optional[int] = None
    enabled: Optional[int] = None
    banner_url: Optional[str] = None
    summary: Optional[str] = None
    nationality: Optional[str] = None
    occupation: Optional[str] = None
    main_achievements: Optional[str] = None
    representative_works_text: Optional[str] = None
    art_style: Optional[str] = None
    influence: Optional[str] = None
    historical_evaluation: Optional[str] = None
    character_relations: Optional[str] = None
    anecdotes: Optional[str] = None
    art_chronology: Optional[str] = None
    published_works: Optional[str] = None
    gallery_images: Optional[str] = None
    references: Optional[str] = None


# ============ API 端点 ============

@router.get("")
async def list_artists(
    dynasty: Optional[str] = None,
    school: Optional[str] = None,
    keyword: Optional[str] = None,
    featured: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    sort: str = "created_at",
):
    """列出所有画家，支持筛选、分页、排序"""
    conn = get_db_connection()
    try:
        conditions = []
        params = []

        if dynasty:
            conditions.append("dynasty = ?")
            params.append(dynasty)
        if school:
            conditions.append("art_school LIKE ?")
            params.append(f"%{school}%")
        if keyword:
            conditions.append("(name LIKE ? OR alias LIKE ? OR biography LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if featured is not None:
            conditions.append("featured = ?")
            params.append(1 if featured else 0)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        allowed_sorts = {"created_at", "updated_at", "birth_year", "name", "id"}
        if sort not in allowed_sorts:
            sort = "created_at"

        total = conn.execute(
            f"SELECT COUNT(*) FROM artists WHERE {where_clause}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM artists WHERE {where_clause} ORDER BY {sort} LIMIT ? OFFSET ?",
            (*params, page_size, offset)
        ).fetchall()

        artists = [dict(row) for row in rows]
        return {"success": True, "artists": artists, "total": total, "page": page, "page_size": page_size}
    finally:
        conn.close()


@router.get("/periods")
async def list_artist_periods():
    """获取所有画家的朝代列表（用于分类筛选）"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT dynasty FROM artists WHERE dynasty IS NOT NULL AND dynasty != '' ORDER BY dynasty"
        ).fetchall()
        periods = [r["dynasty"] for r in rows]
        return {"success": True, "periods": periods}
    finally:
        conn.close()


@router.get("/schools")
async def list_artist_schools():
    """获取所有画派列表"""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM art_schools ORDER BY name").fetchall()
        schools = [{"id": r["id"], "name": r["name"], "description": r["description"],
                     "dynasty": r["dynasty"], "origin": r["origin"]} for r in rows]
        return {"success": True, "schools": schools}
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

        artist = dict(row)
        name = artist["name"]

        artwork_count = conn.execute(
            "SELECT COUNT(*) FROM tubi_analyses WHERE artist = ?", (name,)
        ).fetchone()[0]
        artist["artwork_count"] = artwork_count

        lib_rows = conn.execute(
            "SELECT id FROM artwork_libraries WHERE artist_name = ?", (name,)
        ).fetchall()
        artist["related_libraries"] = [r["id"] for r in lib_rows]

        return {"success": True, "artist": artist}
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

        artist = dict(row)

        artwork_count = conn.execute(
            "SELECT COUNT(*) FROM tubi_analyses WHERE artist = ?", (name,)
        ).fetchone()[0]
        artist["artwork_count"] = artwork_count

        lib_rows = conn.execute(
            "SELECT id FROM artwork_libraries WHERE artist_name = ?", (name,)
        ).fetchall()
        artist["related_libraries"] = [r["id"] for r in lib_rows]

        return {"success": True, "artist": artist}
    finally:
        conn.close()


@router.post("")
async def create_artist(artist: ArtistCreate, editor=Depends(require_permission("content.upload"))):
    """创建画家"""
    conn = get_db_connection()
    try:
        # 检查是否已存在同名画家
        existing = conn.execute(
            "SELECT id FROM artists WHERE name = ?", (artist.name,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="画家已存在")

        now = datetime.now().isoformat()
        cursor = conn.execute(
            "INSERT INTO artists (name, alias, dynasty, hometown, avatar_url, birth_year, death_year, "
            "biography, background, specialties, bio_events, art_school, masterpieces, tags, baidu_url, "
            "featured, enabled, banner_url, summary, nationality, occupation, main_achievements, "
            "representative_works_text, art_style, influence, historical_evaluation, character_relations, "
            "anecdotes, art_chronology, published_works, gallery_images, references, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (artist.name, artist.alias, artist.dynasty, artist.hometown, artist.avatar_url,
             artist.birth_year, artist.death_year, artist.biography, artist.background,
             artist.specialties, artist.bio_events, artist.art_school, artist.masterpieces,
             artist.tags, artist.baidu_url, artist.featured, artist.enabled,
             artist.banner_url, artist.summary, artist.nationality, artist.occupation,
             artist.main_achievements, artist.representative_works_text, artist.art_style,
             artist.influence, artist.historical_evaluation, artist.character_relations,
             artist.anecdotes, artist.art_chronology, artist.published_works,
             artist.gallery_images, artist.references, now, now)
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
        for field in ["name", "alias", "dynasty", "hometown", "avatar_url", "birth_year",
                       "death_year", "biography", "background", "specialties", "bio_events",
                       "art_school", "masterpieces", "tags", "baidu_url", "featured", "enabled",
                       "banner_url", "summary", "nationality", "occupation", "main_achievements",
                       "representative_works_text", "art_style", "influence", "historical_evaluation",
                       "character_relations", "anecdotes", "art_chronology", "published_works",
                       "gallery_images", "references"]:
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
async def delete_artist(artist_id: int, admin=Depends(require_admin_role)):
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


@router.get("/{artist_id}/stats")
async def get_artist_stats(artist_id: int):
    """获取画家统计数据（含缓存）"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        name = artist["name"]

        cached = conn.execute(
            "SELECT stats_data FROM artist_stats_cache WHERE artist_id = ?", (artist_id,)
        ).fetchone()
        if cached:
            return {"success": True, "stats": json.loads(cached["stats_data"]), "cached": True}

        total = conn.execute("SELECT COUNT(*) FROM tubi_analyses WHERE artist = ?", (name,)).fetchone()[0]
        verified = conn.execute("SELECT COUNT(*) FROM tubi_analyses WHERE artist = ? AND inscription_verified = 1", (name,)).fetchone()[0]
        analyzed = conn.execute("SELECT COUNT(*) FROM tubi_analyses WHERE artist = ? AND status = 'analyzed'", (name,)).fetchone()[0]
        translated = conn.execute("SELECT COUNT(*) FROM tubi_analyses WHERE artist = ? AND inscription_modern IS NOT NULL AND inscription_modern != ''", (name,)).fetchone()[0]
        annotated = conn.execute("SELECT COUNT(*) FROM tubi_analyses WHERE artist = ? AND is_manual_annotated = 1", (name,)).fetchone()[0]
        seal_count = conn.execute("SELECT COUNT(*) FROM seals WHERE artist_name = ?", (name,)).fetchone()[0]
        album_count = conn.execute("SELECT COUNT(DISTINCT album_name) FROM tubi_analyses WHERE artist = ? AND album_name IS NOT NULL", (name,)).fetchone()[0]

        stats = {
            "total": total, "verified": verified, "analyzed": analyzed,
            "translated": translated, "annotated": annotated,
            "seal_count": seal_count, "album_count": album_count,
        }

        now = datetime.now().isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO artist_stats_cache (artist_id, stats_data, updated_at) VALUES (?, ?, ?)",
            (artist_id, json.dumps(stats, ensure_ascii=False), now)
        )
        conn.commit()

        return {"success": True, "stats": stats, "cached": False}
    finally:
        conn.close()


@router.get("/{artist_id}/works")
async def get_artist_works(
    artist_id: int,
    page: int = 1,
    page_size: int = 20,
):
    """获取画家的作品列表"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        name = artist["name"]
        offset = (page - 1) * page_size

        total = conn.execute(
            "SELECT COUNT(*) FROM tubi_analyses WHERE artist = ?", (name,)
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT id, image_id, title, year, period, thumbnail_path, inscription_percent, "
            "inscription_verified, status, created_at FROM tubi_analyses "
            "WHERE artist = ? ORDER BY year, id LIMIT ? OFFSET ?",
            (name, page_size, offset)
        ).fetchall()

        works = []
        for r in rows:
            fn = os.path.basename(r["thumbnail_path"].replace("\\", "/")) if r["thumbnail_path"] else ""
            works.append({
                "id": r["id"], "image_id": r["image_id"], "title": r["title"],
                "year": r["year"], "period": r["period"],
                "thumbnail_url": f"/static/thumbnails/{fn}" if fn else "",
                "inscription_verified": r["inscription_verified"], "status": r["status"],
            })

        return {"success": True, "works": works, "total": total, "page": page, "page_size": page_size}
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
    """AI一键查询画家信息并填充（百度百科优先，AI补充）"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        artist_name = artist["name"]
        updates = {}
        rules_created = False

        # 1. 尝试百度百科抓取
        try:
            from app.services.baidu_crawler import fetch_artist_from_baike
            baike = fetch_artist_from_baike(artist_name)
            if baike.get("success") and baike.get("data"):
                info = baike["data"]
                # 仅填充空字段
                if info.get("birth_year") and not artist["birth_year"]:
                    updates["birth_year"] = int(info["birth_year"])
                if info.get("death_year") and not artist["death_year"]:
                    updates["death_year"] = int(info["death_year"])
                if info.get("alias") and not artist["alias"]:
                    updates["alias"] = info["alias"][:100]
                if info.get("hometown") and not artist["hometown"]:
                    updates["hometown"] = info["hometown"][:100]
                if info.get("dynasty") and not artist["dynasty"]:
                    updates["dynasty"] = info["dynasty"][:50]
                if info.get("biography") and not artist["biography"]:
                    updates["biography"] = info["biography"]
                elif info.get("abstract") and not artist["biography"]:
                    updates["biography"] = info["abstract"]
                if info.get("avatar_url") and not artist["avatar_url"]:
                    updates["avatar_url"] = info["avatar_url"]
                if info.get("baidu_url") and not artist["baidu_url"]:
                    updates["baidu_url"] = info["baidu_url"]
                if info.get("masterpieces") and not artist["masterpieces"]:
                    updates["masterpieces"] = info["masterpieces"]
                if info.get("specialties") and not artist["specialties"]:
                    updates["specialties"] = info["specialties"][:200]
                if info.get("art_school") and not artist["art_school"]:
                    updates["art_school"] = info["art_school"]
                # 新增百科字段
                if info.get("summary") and not artist["summary"]:
                    updates["summary"] = info["summary"]
                if info.get("occupation") and not artist["occupation"]:
                    updates["occupation"] = info["occupation"]
                if info.get("main_achievements") and not artist["main_achievements"]:
                    updates["main_achievements"] = info["main_achievements"]
                if info.get("art_style") and not artist["art_style"]:
                    updates["art_style"] = info["art_style"]
                if info.get("character_relations") and not artist["character_relations"]:
                    updates["character_relations"] = info["character_relations"]
                if info.get("nationality") and not artist["nationality"]:
                    updates["nationality"] = info["nationality"]
                if info.get("influence") and not artist["influence"]:
                    updates["influence"] = info["influence"]
                if info.get("historical_evaluation") and not artist["historical_evaluation"]:
                    updates["historical_evaluation"] = info["historical_evaluation"]
                if info.get("anecdotes") and not artist["anecdotes"]:
                    updates["anecdotes"] = info["anecdotes"]
                if info.get("art_chronology") and not artist["art_chronology"]:
                    updates["art_chronology"] = info["art_chronology"]
                if info.get("published_works") and not artist["published_works"]:
                    updates["published_works"] = info["published_works"]
                if info.get("gallery_images") and not artist["gallery_images"]:
                    updates["gallery_images"] = info["gallery_images"]
                if info.get("banner_url") and not artist["banner_url"]:
                    updates["banner_url"] = info["banner_url"]
                if info.get("representative_works_text") and not artist["representative_works_text"]:
                    updates["representative_works_text"] = info["representative_works_text"]
                if info.get("references") and not artist["references"]:
                    updates["references"] = info["references"]
        except Exception as e:
            logger.warning("百度百科抓取失败: %s", e)

        # 2. AI补充（仅填充百度百科未覆盖的字段）
        if not updates.get("background") or not updates.get("specialties"):
            try:
                from app.services.qwen_llm_client import call_qwen_chat

                if artist["background"] and artist["specialties"] and artist["biography"]:
                    pass  # 已有足够信息，跳过AI
                else:
                    prompt = f"""请简要介绍画家{artist_name}的以下信息，用JSON格式返回：
{{
  "birth_year": 出生年份（整数，如不知道写null），
  "background": "背景简介（50字以内）",
  "specialties": "专长",
  "biography": "生平简介（100字以内）"
}}
只返回JSON，不要其他文字。"""

                    response = call_qwen_chat(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=500,
                    )
                    if "error" not in response:
                        result = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                        json_match = re.search(r'\{[^}]+\}', result, re.DOTALL)
                        if json_match:
                            ai_info = json.loads(json_match.group())
                            if ai_info.get("birth_year") and not updates.get("birth_year") and not artist["birth_year"]:
                                updates["birth_year"] = int(ai_info["birth_year"])
                            if ai_info.get("background") and not artist["background"]:
                                updates["background"] = ai_info["background"]
                            if ai_info.get("specialties") and not artist["specialties"]:
                                updates["specialties"] = ai_info["specialties"]
                            if ai_info.get("biography") and not updates.get("biography") and not artist["biography"]:
                                updates["biography"] = ai_info["biography"]
            except Exception as e:
                logger.warning("AI补充失败: %s", e)

        # 写入数据库
        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE artists SET {set_clause} WHERE id = ?",
                (*updates.values(), artist_id)
            )

        conn.commit()
        msg = "查询完成"
        if updates:
            msg += f"，已更新 {len(updates)} 个字段"
        else:
            msg += "，无需更新"
        return {"success": True, "message": msg, "updates": updates, "rules_created": rules_created}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
