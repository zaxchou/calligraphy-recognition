"""
画家信息管理 API
- CRUD（仅元数据：姓名/出生年/背景/专长/启用状态）
- AI一键查询填充（同时写 artists 表 + artist_rules 表）
- 画家规则独立管理：/api/v1/artist-rules
"""
import os
import json
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.auth import require_admin_role, require_editor, require_permission, get_current_user
from app.core.path_utils import get_static_url
from app.core.config import get_settings

router = APIRouter(prefix="/artists", tags=["artists"])
settings = get_settings()


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
    photos: Optional[str] = None
    references: Optional[str] = None


# ============ API 端点 ============

@router.get("")
async def list_artists(
    dynasty: Optional[str] = None,
    school: Optional[str] = None,
    keyword: Optional[str] = None,
    names: Optional[str] = None,
    featured: Optional[bool] = None,
    verified_only: bool = True,
    page: int = 1,
    page_size: int = 40,
    sort: str = "created_at",
):
    """列出所有画家，支持筛选、分页、排序（默认仅显示已认证画家）"""
    conn = get_db_connection()
    try:
        conditions = []
        params = []

        if verified_only:
            conditions.append("verified = 1")

        if dynasty:
            dynasties = [d.strip() for d in dynasty.split(",") if d.strip()]
            if dynasties:
                placeholders = ",".join(["?"] * len(dynasties))
                conditions.append(f"dynasty IN ({placeholders})")
                params.extend(dynasties)

        if school:
            schools = [s.strip() for s in school.split(",") if s.strip()]
            if schools:
                school_clauses = " OR ".join(["art_school LIKE ?"] * len(schools))
                conditions.append(f"({school_clauses})")
                params.extend([f"%{s}%" for s in schools])

        if keyword:
            conditions.append("(name LIKE ? OR alias LIKE ? OR biography LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if names:
            name_list = [n.strip() for n in names.split(",") if n.strip()]
            if name_list and len(name_list) < 500:
                placeholders = ",".join(["?"] * len(name_list))
                conditions.append(f"name IN ({placeholders})")
                params.extend(name_list)
        if featured is not None:
            conditions.append("featured = ?")
            params.append(1 if featured else 0)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        allowed_sorts = {"created_at", "updated_at", "birth_year", "name", "id"}
        sort_map = {"name": "name COLLATE NOCASE", "birth_year": "birth_year IS NULL, birth_year"}
        if sort in sort_map:
            sort_sql = sort_map[sort]
        elif sort not in allowed_sorts:
            sort_sql = "created_at"
        else:
            sort_sql = sort

        total = conn.execute(
            f"SELECT COUNT(*) FROM artists WHERE {where_clause}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""SELECT a.id, a.name, a.alias, a.dynasty, a.art_school,
                       a.birth_year, a.death_year, a.hometown,
                       a.avatar_url, a.summary, a.featured, a.verified,
                       a.created_at, a.updated_at,
                       COALESCE(t.cnt, 0) AS artwork_count
                FROM artists a
                LEFT JOIN (SELECT artist, COUNT(*) AS cnt FROM tubi_analyses GROUP BY artist) t
                  ON a.name = t.artist
                WHERE {where_clause}
                ORDER BY {sort_sql}
                LIMIT ? OFFSET ?""",
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


@router.get("/letter-index")
async def get_letter_index():
    """返回艺术家姓名列表（前端用pinyin-pro库分组）"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT name FROM artists WHERE verified = 1 AND name IS NOT NULL ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in rows]
        return {"success": True, "names": names}
    finally:
        conn.close()


@router.get("/stats-summary")
async def get_stats_summary():
    """返回各朝代/画派计数（用于侧边栏统计标签）"""
    conn = get_db_connection()
    try:
        dynasty_counts = {}
        rows = conn.execute(
            "SELECT dynasty, COUNT(*) as cnt FROM artists WHERE verified=1 AND dynasty IS NOT NULL AND dynasty!='' "
            "GROUP BY dynasty ORDER BY cnt DESC"
        ).fetchall()
        for r in rows:
            dynasty_counts[r["dynasty"]] = r["cnt"]

        total_verified = conn.execute(
            "SELECT COUNT(*) FROM artists WHERE verified=1"
        ).fetchone()[0]

        return {"success": True, "dynasty_counts": dynasty_counts, "total_verified": total_verified}
    finally:
        conn.close()


@router.post("/upload-image")
async def upload_artist_image(
    file: UploadFile = File(...),
    editor=Depends(require_editor),
):
    allowed = {"image/jpeg", "image/png", "image/bmp", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="只支持 JPG、PNG、BMP、WebP、GIF 格式")

    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename and "." in file.filename else ".jpg"
    filename = f"avatar_{file_id}{ext}"
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件大小超过10MB限制")
    with open(filepath, "wb") as f:
        f.write(content)
    await file.close()

    url = get_static_url(f"uploads/{filename}")
    return {"success": True, "url": url}


@router.post("/upload-photo")
async def upload_artist_photo(
    file: UploadFile = File(...),
    editor=Depends(require_editor),
):
    allowed = {"image/jpeg", "image/png", "image/bmp", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="只支持 JPG、PNG、BMP、WebP、GIF 格式")

    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename and "." in file.filename else ".jpg"
    ext = ext.lower()
    if ext == ".jpeg":
        ext = ".jpg"

    filename = f"photo_{file_id}{ext}"
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件大小超过10MB限制")
    with open(filepath, "wb") as f:
        f.write(content)
    await file.close()

    url = get_static_url(f"uploads/{filename}")

    thumb_url = url
    try:
        from PIL import Image
        import io
        img = Image.open(filepath)
        img.thumbnail((200, 200), Image.LANCZOS)
        thumb_name = f"photo_{file_id}_thumb.jpg"
        thumb_path = os.path.join(upload_dir, thumb_name)
        img.save(thumb_path, "JPEG", quality=75)
        thumb_url = get_static_url(f"uploads/{thumb_name}")
    except Exception:
        pass

    return {"success": True, "url": url, "thumb_url": thumb_url}


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
    """按名称获取画家（支持别名归一化：郑板桥→郑燮）"""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM artists WHERE name = ?", (name,)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM artists WHERE alias LIKE ? OR alias = ? LIMIT 1",
                (f"%{name}%", name),
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="画家不存在")

        artist = dict(row)
        canonical_name = artist["name"]

        artwork_count = conn.execute(
            "SELECT COUNT(*) FROM tubi_analyses WHERE artist = ?", (canonical_name,)
        ).fetchone()[0]
        artist["artwork_count"] = artwork_count

        lib_rows = conn.execute(
            "SELECT id FROM artwork_libraries WHERE artist_name = ?", (canonical_name,)
        ).fetchall()
        artist["related_libraries"] = [r["id"] for r in lib_rows]

        result = {"success": True, "artist": artist}
        if canonical_name != name:
            result["canonical_name"] = canonical_name
        return result
    finally:
        conn.close()


@router.post("")
async def create_artist(artist: ArtistCreate, user=Depends(get_current_user)):
    """创建画家（所有人可创建，编辑以上自动认证）"""
    conn = get_db_connection()
    try:
        # 检查是否已存在同名画家
        existing = conn.execute(
            "SELECT id FROM artists WHERE name = ?", (artist.name,)
        ).fetchone()
        if existing:
            conn.close()
            return {"success": True, "id": existing["id"], "message": "画家已存在", "existed": True}

        now = datetime.now().isoformat()
        is_verified = 1 if user.role in ("editor", "admin", "super_admin") else 0
        cursor = conn.execute(
            "INSERT INTO artists (name, alias, dynasty, hometown, avatar_url, birth_year, death_year, "
            "biography, background, specialties, bio_events, art_school, masterpieces, tags, "
            "featured, enabled, verified, banner_url, summary, nationality, occupation, main_achievements, "
            "representative_works_text, art_style, influence, historical_evaluation, character_relations, "
            "anecdotes, art_chronology, published_works, gallery_images, [references], created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (artist.name, artist.alias, artist.dynasty, artist.hometown, artist.avatar_url,
             artist.birth_year, artist.death_year, artist.biography, artist.background,
             artist.specialties, artist.bio_events, artist.art_school, artist.masterpieces,
             artist.tags, artist.featured, artist.enabled, is_verified,
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
                       "art_school", "masterpieces", "tags", "featured", "enabled", "verified",
                       "banner_url", "summary", "nationality", "occupation", "main_achievements",
                       "representative_works_text", "art_style", "influence", "historical_evaluation",
                       "character_relations", "anecdotes", "art_chronology", "published_works",
                       "gallery_images", "photos", "references"]:
            val = getattr(artist, field, None)
            if val is not None:
                updates[field] = val

        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            SQL_RESERVED = {"references"}
            quoted_keys = {k: f'[{k}]' if k in SQL_RESERVED else k for k in updates}
            set_clause = ", ".join(f"{quoted_keys[k]} = ?" for k in updates)
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


class TravelNotesUpdate(BaseModel):
    travel_notes: Optional[str] = None  # JSON string


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


@router.put("/by-name/{name}/travel-notes")
async def save_travel_notes(name: str, req: TravelNotesUpdate, editor=Depends(require_editor)):
    """保存行旅数据（手动编辑或AI生成后保存）"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT id, name FROM artists WHERE name = ?", (name,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        conn.execute(
            "UPDATE artists SET travel_notes = ?, updated_at = ? WHERE name = ?",
            (req.travel_notes, datetime.now().isoformat(), name)
        )
        conn.commit()
        return {"success": True, "message": "行旅数据已保存"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/by-name/{name}/travel-notes/generate")
async def generate_travel_notes(name: str, editor=Depends(require_editor)):
    """AI 根据年谱+作品列表生成结构化行旅数据"""
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE name = ?", (name,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        artist_dict = dict(artist)

        # 获取年谱
        chronology_raw = artist_dict.get("art_chronology", "[]")
        try:
            chronology = json.loads(chronology_raw) if isinstance(chronology_raw, str) else (chronology_raw or [])
        except Exception:
            chronology = []

        if not chronology or len(chronology) < 3:
            raise HTTPException(status_code=400, detail="年谱数据不足（需至少3条记录），请先完善年谱")

        # 获取作品列表
        artworks = conn.execute(
            "SELECT image_id, title, year, period, period_phase, thumbnail_path "
            "FROM tubi_analyses WHERE artist = ? ORDER BY year",
            (name,)
        ).fetchall()

        # 获取城市坐标库
        import os as _os
        cities_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
                                     "data", "cities.json")
        city_coords = {}
        try:
            with open(cities_path, "r", encoding="utf-8") as f:
                city_coords = json.load(f)
        except Exception:
            pass

        # 构建 prompt
        birth = artist_dict.get("birth_year") or ""
        death = artist_dict.get("death_year") or ""
        lifespan = f"{birth}-{death}" if birth and death else (f"{birth}" if birth else "")

        chrono_text = "\n".join([
            f"{e.get('year','?')} | {e.get('event','')} | {e.get('location','')} | {e.get('description','')}"
            for e in chronology[:80]
        ])

        paintings_text = "\n".join([
            f"- [{a['image_id']}] {a['title']} ({a['year'] or '年代不详'})"
            for a in artworks[:200]
        ])

        city_hint = json.dumps(city_coords, ensure_ascii=False) if city_coords else "无坐标库"
        # 如果坐标库过大（>5000字符），只保留华东/华北主要城市
        if len(city_hint) > 5000:
            important_regions = ['北京', '上海', '天津', '重庆',
                '南京', '苏州', '扬州', '杭州', '绍兴', '宁波', '无锡', '常州', '镇江', '南通', '徐州',
                '济南', '青岛', '西安', '洛阳', '开封', '郑州',
                '广州', '福州', '厦门', '南昌', '长沙', '武汉',
                '成都', '昆明', '贵阳', '沈阳', '长春', '哈尔滨',
                '合肥', '太原', '兰州', '银川', '西宁', '拉萨', '乌鲁木齐',
                '桂林', '南宁', '海口', '三亚',
                '大同', '保定', '邯郸', '张家口', '承德', '沧州',
                '淄博', '潍坊', '临沂', '泰安', '济宁', '聊城', '德州', '菏泽',
                '襄阳', '荆州', '宜昌', '黄冈',
                '岳阳', '衡阳', '株洲', '湘潭',
                '赣州', '九江', '景德镇',
                '泉州', '漳州',
                '佛山', '东莞', '珠海', '惠州',
                '遵义', '安顺',
                '大理', '丽江',
                '扬州', '淮安', '连云港', '盐城',
                '金华', '温州', '湖州', '嘉兴', '台州', '衢州',
                '芜湖', '安庆', '黄山', '宣城',
                '深圳', '中山', '江门', '湛江']
            reduced = {k: v for k, v in city_coords.items() if k in important_regions}
            city_hint = json.dumps(reduced, ensure_ascii=False) + f"\n（完整坐标库共{len(city_coords)}城，以上为主要城市，如需其他城市坐标请告知）"

        prompt = f"""你是一位中国美术史专家。请为画家「{name}」({lifespan}) 生成一份结构化的"翰墨行旅"数据。

## 年谱数据
{chrono_text}

## 作品列表（共 {len(artworks)} 幅，仅展示前200）
{paintings_text}

## 城市坐标库（必须使用，古地名需映射到现代标准城市名）
{city_hint}

## 任务
从年谱中提取该画家一生到访/居住过的所有城市，并为每个城市关联相关作品，按生命阶段划分3-5个有意义的时期。

## 输出格式（严格JSON，不要markdown代码块）
{{
  "periods": [
    {{"id": "p0", "label": "时期名称（如：早年求学、科举仕途、为官时期、罢官归隐、晚年）", "year_range": [起始年, 结束年], "order": 0}}
  ],
  "locations": [
    {{
      "name": "现代标准城市名（如：绍兴、杭州，必须来自坐标库或古地名→现代名映射）",
      "lat": 纬度（浮点数，从坐标库取）,
      "lng": 经度（浮点数，从坐标库取）,
      "periods": ["p0", "p1"],
      "summary": "基于年谱史实的100字以内概述，描述画家在此地的活动",
      "painting_ids": ["uuid1", "uuid2"],
      "events": [
        {{"year": 1521, "event": "出生", "description": "基于年谱的详细描述"}}
      ]
    }}
  ]
}}

## 严格要求
1. **绝不编造**：所有城市、事件、画作关联必须基于年谱和作品列表中的真实数据
2. **古地名映射**：古地名必须映射到坐标库中的现代标准城市名（如"山阴"→"绍兴"、"宣府"→"张家口"、"金陵"→"南京"）
3. **画作关联**：仅将画作关联到该画家确实在该城市的年份范围，±5年容差
4. **时期划分**：根据人生阶段合理划分，每时期有明确语义标签，不要重复标签
5. **坐标精确**：lat/lng必须直接从坐标库中取，不得估算
6. **summary不可编造**：仅基于年谱中的事件描述，不知道的不要写
7. 只返回JSON，不要任何额外文字"""

        # 调用 AI
        import logging
        _logger = logging.getLogger(__name__)
        try:
            from app.services.qwen_llm_client import call_qwen_chat
            _logger.info(f"Travel notes AI: calling LLM for {name}, prompt ~{len(prompt)} chars")
            response = call_qwen_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=8000,
            )
            if "error" in response:
                _logger.error(f"Travel notes AI error: {response['error']}")
                raise HTTPException(status_code=500, detail=f"AI调用失败: {response['error']}")

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                _logger.error(f"Travel notes AI: empty content, full response keys: {list(response.keys())}")
                raise HTTPException(status_code=500, detail="AI返回空内容")
            _logger.info(f"Travel notes AI: got {len(content)} chars response")
        except HTTPException:
            raise
        except Exception as e:
            _logger.error(f"Travel notes AI exception: {type(e).__name__}: {str(e)[:200]}")
            raise HTTPException(status_code=500, detail=f"AI调用异常: {str(e)[:200]}")

        # 解析 JSON
        parsed = _parse_travel_json(content)
        if not parsed:
            raise HTTPException(status_code=500, detail="AI返回的JSON解析失败，请重试")

        # 基础校验
        if not parsed.get("locations") or len(parsed["locations"]) == 0:
            raise HTTPException(status_code=500, detail="AI生成的城市列表为空")

        # 补充元数据
        parsed["generated_at"] = datetime.now().isoformat()
        parsed["model"] = "deepseek-v3"

        travel_json = json.dumps(parsed, ensure_ascii=False)

        # 保存到 DB
        conn.execute(
            "UPDATE artists SET travel_notes = ?, updated_at = ? WHERE name = ?",
            (travel_json, datetime.now().isoformat(), name)
        )
        conn.commit()

        return {"success": True, "travel_notes": parsed, "message": f"AI已生成{len(parsed['locations'])}个城市的行旅数据"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


def _parse_travel_json(content: str) -> dict:
    """解析 AI 返回的行旅 JSON"""
    content = content.strip()
    # 去除可能的 markdown 代码块
    for prefix in ["```json", "```"]:
        if content.startswith(prefix):
            content = content[len(prefix):]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


@router.post("/{artist_id}/ai-fill")
async def ai_fill_artist(artist_id: int, editor=Depends(require_editor)):
    conn = get_db_connection()
    try:
        artist = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,)).fetchone()
        if not artist:
            raise HTTPException(status_code=404, detail="画家不存在")

        artist_name = artist["name"]
        updates = {}

        baike_data = _fetch_baike_data(artist_name)

        if baike_data:
            updates = _merge_baike_updates(artist, baike_data)

        ai_data = _ai_generate_fields(artist_name, artist, baike_data)
        if ai_data:
            json_array_cols = {"art_chronology", "anecdotes", "character_relations",
                               "published_works", "references", "gallery_images",
                               "bio_events", "masterpieces", "tags"}
            for k, v in ai_data.items():
                if not v:
                    continue
                if k in ("featured", "enabled", "view_count"):
                    continue
                existing_val = artist[k]
                is_empty = (
                    existing_val is None or existing_val == "" or
                    (k in json_array_cols and (existing_val == "[]" or existing_val == "null"))
                )
                if k in ("birth_year", "death_year"):
                    if existing_val is None and isinstance(v, (int, float)):
                        if k not in updates or updates.get(k) is None:
                            updates[k] = int(v)
                elif k in json_array_cols:
                    if is_empty:
                        if k not in updates or not updates[k]:
                            updates[k] = v
                    else:
                        try:
                            new_arr = json.loads(v) if isinstance(v, str) else v
                            old_arr = json.loads(existing_val) if isinstance(existing_val, str) else (existing_val or [])
                            if isinstance(new_arr, list) and len(new_arr) > len(old_arr if isinstance(old_arr, list) else []):
                                if k not in updates:
                                    updates[k] = v
                        except Exception:
                            pass
                elif is_empty:
                    if k not in updates or not updates[k]:
                        updates[k] = v

        _filter_hallucinated_aliases(updates, artist_name)

        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            SQL_RESERVED = {"references"}
            quoted_keys = {k: f'[{k}]' if k in SQL_RESERVED else k for k in updates}
            set_clause = ", ".join(f"{quoted_keys[k]} = ?" for k in updates)
            conn.execute(
                f"UPDATE artists SET {set_clause} WHERE id = ?",
                (*updates.values(), artist_id)
            )
            conn.commit()

        msg = "查询完成"
        if updates:
            fields_done = ", ".join(updates.keys())
            msg = f"已更新 {len(updates)} 个字段：{fields_done}"
        else:
            msg += "，无需更新"
        return {"success": True, "message": msg, "updates": updates}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


def _fetch_baike_data(artist_name: str) -> dict:
    try:
        from app.services.baidu_crawler import fetch_artist_from_baike
        result = fetch_artist_from_baike(artist_name)
        if result.get("success") and result.get("data"):
            return result["data"]
    except Exception:
        pass

    try:
        import requests
        encoded = requests.utils.quote(artist_name)
        url = f"https://baike.baidu.com/item/{encoded}"
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html",
        }, timeout=3)
        if resp.status_code == 200 and len(resp.text) > 5000:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                data = {}
                meta_desc = soup.select_one("meta[name=description]")
                if meta_desc:
                    data["summary"] = meta_desc.get("content", "")[:2000]
                title_el = soup.select_one("title")
                if title_el:
                    title_text = title_el.get_text(strip=True)
                    data["name"] = title_text.replace("_百度百科", "")
                basic_items = soup.select(".basicInfo-item")
                for item in basic_items:
                    text = item.get_text(strip=True)
                    if "：" in text or ":" in text:
                        sep = "：" if "：" in text else ":"
                        key, val = text.split(sep, 1)
                        key = key.strip(); val = val.strip()
                        if "出生" in key or "生年" in key:
                            m = re.search(r'(\d{4})', val)
                            if m: data["birth_year"] = int(m.group(1))
                        elif "逝世" in key or "卒年" in key:
                            m = re.search(r'(\d{4})', val)
                            if m: data["death_year"] = int(m.group(1))
                        elif "字" == key or "号" == key:
                            old = data.get("alias", "")
                            data["alias"] = f"{old} {key}{val}".strip()
                        elif "籍贯" in key or "出生地" in key:
                            data["hometown"] = val[:100]
                        elif "朝代" in key or "时代" in key:
                            data["dynasty"] = val[:50]
                        elif "职业" in key:
                            data["occupation"] = val[:50]
                        elif "主要成就" in key:
                            data["main_achievements"] = val[:500]
                        elif "代表" in key:
                            parts = [p.strip() for p in re.split(r'[,，、]', val) if p.strip()]
                            if parts: data["masterpieces"] = json.dumps(parts[:6], ensure_ascii=False)
                if data.get("summary"):
                    data["biography"] = data["summary"]
                data["source"] = "scrape"
                return data
            except Exception:
                pass
    except Exception:
        pass

    return {}


def _filter_hallucinated_aliases(updates: dict, artist_name: str = ""):
    """剔除AI幻觉产生的抄袭式alias及李鱓特征数据"""
    if artist_name == "李鱓":
        return

    if "alias" in updates:
        alias_val = str(updates["alias"])
        if "复堂" in alias_val:
            del updates["alias"]

    hometown = str(updates.get("hometown", ""))
    birth = updates.get("birth_year")
    bio = str(updates.get("biography", ""))
    summary = str(updates.get("summary", ""))
    background = str(updates.get("background", ""))
    specialties = str(updates.get("specialties", ""))
    occupation = str(updates.get("occupation", ""))
    arts = str(updates.get("art_style", ""))
    achv = str(updates.get("main_achievements", ""))

    is_lishan_clone = False
    if hometown == "江苏兴化" and birth == 1686:
        is_lishan_clone = True
    for field in (bio, summary, background, specialties, occupation, arts, achv):
        if "复堂" in field or "懊道人" in field:
            is_lishan_clone = True
            break

    if is_lishan_clone:
        for key in ("hometown", "birth_year", "death_year", "biography", "summary",
                     "art_style", "main_achievements", "influence", "historical_evaluation",
                     "occupation", "nationality", "representative_works_text", "specialties",
                     "background"):
            updates.pop(key, None)


def _merge_baike_updates(artist, baike_data: dict) -> dict:
    updates = {}
    field_map = {
        "birth_year": "birth_year", "death_year": "death_year",
        "alias": "alias", "hometown": "hometown", "dynasty": "dynasty",
        "biography": "biography", "avatar_url": "avatar_url",
        "masterpieces": "masterpieces",
        "specialties": "specialties", "art_school": "art_school",
        "summary": "summary", "occupation": "occupation",
        "main_achievements": "main_achievements", "art_style": "art_style",
        "character_relations": "character_relations", "nationality": "nationality",
        "influence": "influence", "historical_evaluation": "historical_evaluation",
        "anecdotes": "anecdotes", "art_chronology": "art_chronology",
        "published_works": "published_works", "gallery_images": "gallery_images",
        "banner_url": "banner_url", "representative_works_text": "representative_works_text",
        "references": "references",
    }
    for baike_key, db_col in field_map.items():
        val = baike_data.get(baike_key)
        if val and not artist[db_col]:
            if db_col == "birth_year" and isinstance(val, (int, float)):
                updates[db_col] = int(val)
            elif db_col == "death_year" and isinstance(val, (int, float)):
                updates[db_col] = int(val)
            elif db_col == "alias":
                updates[db_col] = str(val)[:100]
            elif db_col in ("hometown", "dynasty"):
                updates[db_col] = str(val)[:50]
            elif db_col == "specialties":
                updates[db_col] = str(val)[:200]
            else:
                updates[db_col] = str(val)
    return updates


def _ai_generate_fields(artist_name: str, artist, baike_data: dict) -> dict:
    result = {}
    try:
        from app.services.qwen_llm_client import call_qwen_chat

        hint_parts = []
        if baike_data:
            for k in ("summary", "biography", "dynasty", "hometown", "birth_year", "death_year"):
                if baike_data.get(k):
                    hint_parts.append(f"{k}: {baike_data[k]}")
        hint_text = "\n".join(hint_parts) if hint_parts else "无已有数据"

        prompt_basic = f"""请为画家「{artist_name}」生成百科信息，用纯JSON返回（不要markdown代码块）。

已有部分信息作为参考：
{hint_text}

请返回以下JSON格式（字符串字段用中文填写，**未知的填null，严禁编造**）：
{{
  "alias": "字号（如：字元章，号梅花屋主；未知则填null，绝不要抄袭其他画家的字号）",
  "dynasty": "朝代（如：清）",
  "hometown": "籍贯（如：江苏兴化；未知填null）",
  "birth_year": 出生年份（整数，如：1686；未知填null）,
  "death_year": 卒年（整数，如：1762；未知填null）,
  "summary": "100字概述",
  "biography": "300字详细生平介绍",
  "art_style": "200字艺术特色，包括画风、用笔、用墨特点",
  "main_achievements": "100字主要成就",
  "influence": "150字后世影响",
  "historical_evaluation": "100字历史评价",
  "occupation": "职业（如：画家、书法家）",
  "nationality": "国籍（如：中国）",
  "representative_works_text": "代表作名称，逗号分隔",
  "specialties": "专长词条（如：写意花鸟、泼墨）",
  "anecdotes": [{{"title": "典故标题", "content": "典故详细内容"}}],
  "character_relations": [{{"name": "人物姓名", "relationship": "关系", "description": "关系描述"}}],
  "published_works": [{{"title": "著作名称", "publisher": "出版社", "year": "年份"}}]
}}

**重要**: alias、hometown 等信息若你确实不知道，务必填 null，绝不要抄袭示例文字或别的画家的信息。
anecdotes 列出尽可能多的著名轶事典故，不得少于5条。
birth_year 和 death_year 必须是整数（非字符串），未知则用 null。
只返回JSON，不要其他文字。"""
        response = call_qwen_chat(
            messages=[{"role": "user", "content": prompt_basic}],
            temperature=0.3, max_tokens=3000,
        )
        if "error" not in response:
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _parse_json_response(content)
            if parsed:
                result.update(parsed)

        prompt_chrono = f"""请为画家「{artist_name}」单独生成完整的艺术年谱（art_chronology）。

已有信息：{hint_text}

你需要穷尽你所知道的关于这位画家的全部生平与艺术事件，按年份排列。从出生年份开始，一直到去世年份，每一年至少一条记录。格式如下（纯JSON数组，不要markdown）：

[{{
  "year": "年份",
  "event": "事件标题",
  "location": "地点",
  "description": "详细描述该年活动，包括创作、仕途、交游、迁徙等全部细节"
}}]

要求：
- 必须覆盖画家的全部已知公开资料，有多少写多少，不得精简阉割
- 按年份从小到大排列
- 每一年至少一条，重要年份可以有2-3条
- 每条description至少30字
- 至少输出20条，多多益善

只返回JSON数组，不要其他任何文字。"""
        response2 = call_qwen_chat(
            messages=[{"role": "user", "content": prompt_chrono}],
            temperature=0.3, max_tokens=8000,
        )
        if "error" not in response2:
            content2 = response2.get("choices", [{}])[0].get("message", {}).get("content", "")
            content2 = content2.strip().lstrip("````json").lstrip("```").rstrip("```").strip()
            start = content2.find("[")
            end = content2.rfind("]")
            if start >= 0 and end > start:
                try:
                    chrono = json.loads(content2[start:end + 1])
                    if isinstance(chrono, list) and len(chrono) > 0:
                        result["art_chronology"] = json.dumps(chrono, ensure_ascii=False)
                except json.JSONDecodeError:
                    pass

        json_arrays = ["anecdotes", "character_relations", "published_works"]
        for field in json_arrays:
            if field in result and isinstance(result[field], list):
                result[field] = json.dumps(result[field], ensure_ascii=False)

    except Exception:
        pass
    return result


def _parse_json_response(content: str) -> dict:
    content = content.strip().lstrip("````json").lstrip("```").rstrip("```").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def invalidate_stats_cache(artist_name: str):
    try:
        conn = get_db_connection()
        try:
            conn.execute(
                "DELETE FROM artist_stats_cache WHERE artist_id IN (SELECT id FROM artists WHERE name = ?)",
                (artist_name,)
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
