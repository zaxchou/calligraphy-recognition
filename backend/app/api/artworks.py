"""
作品 CRUD API — /api/v1/libraries/{id}/artworks + /api/v1/artworks/{id}
Phase 2: 作品库产品线 — 作品管理与子资源（著录/拍卖）
"""
import logging
import os
import uuid
import json
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

import redis as redis_lib

from app.core.config import get_settings
from app.core.database import get_db
from app.core.auth import get_current_user, get_optional_user
from app.core.quota import check_ai_quota
from app.core.path_utils import get_static_url, normalize_path
from app.models.tubi_analysis import TubiAnalysis
from app.models.tubi_job import TubiJob
from app.models.artwork_library import ArtworkLibrary
from app.models.library_collaborator import LibraryCollaborator
from app.models.literature_reference import LiteratureReference
from app.models.auction_record import AuctionRecord
from app.models.research_note import ResearchNote
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(tags=["作品管理"])

UPLOAD_DIR = settings.UPLOAD_DIR
THUMBNAIL_DIR = settings.TUBI_THUMBNAIL_DIR

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Pydantic schemas ──

class ArtworkCreate(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    year: Optional[int] = None
    period: Optional[str] = None
    notes: Optional[str] = None
    material: Optional[str] = None
    mounting_format: Optional[str] = None
    current_location: Optional[str] = None
    provenance: Optional[str] = None
    style_tags: Optional[str] = None
    subject_tags: Optional[str] = None
    technique_tags: Optional[str] = None
    free_tags: Optional[str] = None
    inscription_author: Optional[str] = None
    inscription_date: Optional[str] = None
    visibility: str = "public"


class ArtworkUpdate(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    year: Optional[int] = None
    period: Optional[str] = None
    notes: Optional[str] = None
    material: Optional[str] = None
    mounting_format: Optional[str] = None
    current_location: Optional[str] = None
    provenance: Optional[str] = None
    style_tags: Optional[str] = None
    subject_tags: Optional[str] = None
    technique_tags: Optional[str] = None
    free_tags: Optional[str] = None
    inscription_author: Optional[str] = None
    inscription_date: Optional[str] = None
    visibility: Optional[str] = None
    artwork_width_cm: Optional[float] = None
    artwork_height_cm: Optional[float] = None
    tags: Optional[str] = None


class LiteratureCreate(BaseModel):
    reference_type: str = "citation"
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    page: Optional[str] = None
    notes: Optional[str] = None


class AuctionCreate(BaseModel):
    auction_house: Optional[str] = None
    sale_date: Optional[str] = None
    lot_number: Optional[str] = None
    estimate_low: Optional[float] = None
    estimate_high: Optional[float] = None
    hammer_price: Optional[float] = None
    currency: str = "CNY"
    notes: Optional[str] = None


# ── Helpers ──

def _artwork_to_dict(a: TubiAnalysis) -> dict:
    """TubiAnalysis 转为字典"""
    def _ts(v):
        return v.isoformat() if v else None

    return {
        "id": a.id,
        "image_id": a.image_id,
        "filename": a.filename,
        "filepath": a.filepath,
        "url": _get_image_url(a.filepath),
        "title": a.title,
        "artist": a.artist,
        "year": a.year,
        "period": a.period,
        "notes": a.notes,
        "image_width": a.image_width,
        "image_height": a.image_height,
        "inscription_percent": a.inscription_percent,
        "painting_percent": a.painting_percent,
        "blank_percent": a.blank_percent,
        "regions": a.regions,
        "position_analysis": a.position_analysis,
        "analysis_note": a.analysis_note,
        "inscription_content": a.inscription_content,
        "inscription_modern": a.inscription_modern,
        "annotated_image_path": a.annotated_image_path,
        "thumbnail_path": a.thumbnail_path,
        "thumbnail_url": _get_thumbnail_url(a.thumbnail_path),
        "status": a.status,
        "period_phase": a.period_phase,
        "char_count": a.char_count,
        "word_count": a.word_count,
        "theme_tags": a.theme_tags,
        "content_analysis": a.content_analysis,
        "inscription_verified": a.inscription_verified,
        "seal_content": a.seal_content,
        "material_tags": a.material_tags,
        "error_code": a.error_code,
        "artwork_width_cm": a.artwork_width_cm,
        "artwork_height_cm": a.artwork_height_cm,
        "album_name": a.album_name,
        "album_index": a.album_index,
        "tags": a.tags,
        "owner_id": a.owner_id,
        "library_id": a.library_id,
        "visibility": a.visibility,
        "created_by": a.created_by,
        "material": a.material,
        "mounting_format": a.mounting_format,
        "current_location": a.current_location,
        "provenance": a.provenance,
        "style_tags": a.style_tags,
        "subject_tags": a.subject_tags,
        "technique_tags": a.technique_tags,
        "free_tags": a.free_tags,
        "inscription_author": a.inscription_author,
        "inscription_date": a.inscription_date,
        "created_at": _ts(a.created_at),
        "updated_at": _ts(a.updated_at),
    }


def _strip_data_prefix(p: str) -> str:
    """去掉路径中的 data/ 前缀（StaticFiles 挂载点 = data/）"""
    p = normalize_path(p)
    if p.startswith('data/'):
        p = p[5:]
    return p


def _get_image_url(filepath: Optional[str]) -> Optional[str]:
    if not filepath:
        return None
    return get_static_url(_strip_data_prefix(filepath))


def _get_thumbnail_url(thumbnail_path: Optional[str]) -> Optional[str]:
    if not thumbnail_path:
        return None
    return get_static_url(_strip_data_prefix(thumbnail_path))


def _check_library_write_access(lib: ArtworkLibrary, user: User, db: Session) -> None:
    """检查用户是否有库的写入权限（owner 或 editor/maintainer 协作者）"""
    if lib.owner_id == user.id:
        return
    collab = db.query(LibraryCollaborator).filter(
        LibraryCollaborator.library_id == lib.id,
        LibraryCollaborator.user_id == user.id,
        LibraryCollaborator.role.in_(["editor", "maintainer"]),
    ).first()
    if not collab:
        raise HTTPException(status_code=403, detail="无权操作此作品库（需要 editor 或以上权限）")


def _check_artwork_write_access(artwork: TubiAnalysis, user: User, db: Session) -> None:
    """检查用户是否有作品的写入权限"""
    if artwork.owner_id == user.id:
        return
    if artwork.library_id:
        lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == artwork.library_id).first()
        if lib:
            _check_library_write_access(lib, user, db)
            return
    raise HTTPException(status_code=403, detail="无权操作此作品")


def _update_artwork_count(library_id: int, db: Session) -> None:
    """更新作品库的 artwork_count"""
    count = db.query(sqlfunc.count(TubiAnalysis.id)).filter(
        TubiAnalysis.library_id == library_id
    ).scalar()
    db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).update(
        {ArtworkLibrary.artwork_count: count}
    )


# ── 缩略图生成 ──

def create_thumbnail_simple(image_path: str, thumbnail_path: str, max_size: int = 300):
    """简化缩略图：缩放至 max_size 以内"""
    from PIL import Image, ImageOps
    try:
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
            img.save(thumbnail_path, "JPEG", quality=85)
    except Exception as e:
        logger.warning(f"缩略图生成失败: {e}")


# ════════════════════════════════════════════════════════════════
# 作品 CRUD
# ════════════════════════════════════════════════════════════════

@router.post("/libraries/{library_id}/artworks")
async def upload_artwork(
    library_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    artist: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    period: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    material: Optional[str] = Form(None),
    mounting_format: Optional[str] = Form(None),
    current_location: Optional[str] = Form(None),
    provenance: Optional[str] = Form(None),
    style_tags: Optional[str] = Form(None),
    subject_tags: Optional[str] = Form(None),
    technique_tags: Optional[str] = Form(None),
    free_tags: Optional[str] = Form(None),
    inscription_author: Optional[str] = Form(None),
    inscription_date: Optional[str] = Form(None),
    visibility: str = Form("public"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传作品到指定作品库"""
    # 检查库存在且有权写入
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")
    _check_library_write_access(lib, user, db)

    # 文件类型校验
    if file.content_type not in ("image/jpeg", "image/png", "image/bmp", "image/webp"):
        raise HTTPException(status_code=400, detail="只支持 JPG、PNG、BMP、WebP 格式")

    # 保存文件
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    filename = f"{file_id}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    thumbnail_filename = f"{file_id}_thumb.jpg"
    thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)

    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

    # 流式写入
    size = 0
    try:
        with open(filepath, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise ValueError("too_large")
                f.write(chunk)
    except ValueError:
        try:
            os.remove(filepath)
        except Exception:
            pass
        raise HTTPException(status_code=413, detail="文件大小超过50MB限制")
    finally:
        await file.close()

    # 获取图片尺寸 + 生成缩略图
    image_width = 0
    image_height = 0
    try:
        from PIL import Image, ImageOps
        with Image.open(filepath) as img:
            img = ImageOps.exif_transpose(img)
            image_width, image_height = img.size
        create_thumbnail_simple(filepath, thumbnail_path)
    except Exception as e:
        logger.warning(f"获取图片尺寸/缩略图失败: {e}")

    # 创建数据库记录
    artwork = TubiAnalysis(
        image_id=file_id,
        filename=file.filename,
        filepath=normalize_path(filepath),
        title=title,
        artist=artist,
        year=year,
        period=period,
        notes=notes,
        image_width=image_width,
        image_height=image_height,
        thumbnail_path=normalize_path(thumbnail_path),
        status="uploaded",
        owner_id=user.id,
        library_id=library_id,
        visibility=visibility,
        created_by=user.nickname,
        material=material,
        mounting_format=mounting_format,
        current_location=current_location,
        provenance=provenance,
        style_tags=style_tags,
        subject_tags=subject_tags,
        technique_tags=technique_tags,
        free_tags=free_tags,
        inscription_author=inscription_author,
        inscription_date=inscription_date,
    )
    db.add(artwork)
    db.commit()
    db.refresh(artwork)

    # 更新作品数量
    _update_artwork_count(library_id, db)
    db.commit()

    logger.info(f"用户 {user.id} 上传作品到库 {library_id}: {artwork.id}")
    return _artwork_to_dict(artwork)


@router.get("/libraries/{library_id}/artworks")
async def list_artworks(
    library_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", description="排序字段: created_at/artist/year"),
    order: str = Query("desc", description="排序方向: asc/desc"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """库内作品列表（分页+排序）"""
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")

    # 权限检查
    if lib.visibility != "public":
        if user is None:
            raise HTTPException(status_code=401, detail="请先登录")
        is_collab = db.query(LibraryCollaborator).filter(
            LibraryCollaborator.library_id == library_id,
            LibraryCollaborator.user_id == user.id,
        ).first() is not None
        if lib.owner_id != user.id and not is_collab:
            raise HTTPException(status_code=403, detail="无权访问此作品库")

    # 排序
    sort_col = TubiAnalysis.created_at
    if sort_by == "artist":
        sort_col = TubiAnalysis.artist
    elif sort_by == "year":
        sort_col = TubiAnalysis.year

    if order == "asc":
        order_func = sort_col.asc()
    else:
        order_func = sort_col.desc()

    offset = (page - 1) * page_size
    total = db.query(sqlfunc.count(TubiAnalysis.id)).filter(
        TubiAnalysis.library_id == library_id
    ).scalar()

    artworks = db.query(TubiAnalysis).filter(
        TubiAnalysis.library_id == library_id
    ).order_by(order_func).offset(offset).limit(page_size).all()

    items = []
    for a in artworks:
        d = _artwork_to_dict(a)
        d["thumbnail_url"] = _get_thumbnail_url(a.thumbnail_path)
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/artworks/{artwork_id}")
async def get_artwork_detail(
    artwork_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """作品详情（含著录、拍卖记录、研究笔记、AI分析结果）"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")

    # 权限检查
    if artwork.visibility != "public":
        if user is None:
            raise HTTPException(status_code=401, detail="请先登录")
        if artwork.owner_id != user.id:
            # 检查是否为库 owner/collaborator
            if artwork.library_id:
                lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == artwork.library_id).first()
                if lib:
                    is_collab = lib.owner_id == user.id or db.query(LibraryCollaborator).filter(
                        LibraryCollaborator.library_id == lib.id,
                        LibraryCollaborator.user_id == user.id,
                    ).first() is not None
                    if not is_collab:
                        raise HTTPException(status_code=403, detail="无权查看此作品")
                else:
                    raise HTTPException(status_code=403, detail="无权查看此作品")
            else:
                raise HTTPException(status_code=403, detail="无权查看此作品")

    result = _artwork_to_dict(artwork)
    result["thumbnail_url"] = _get_thumbnail_url(artwork.thumbnail_path)

    # 著录列表
    lit_refs = db.query(LiteratureReference).filter(
        LiteratureReference.artwork_id == artwork_id
    ).order_by(LiteratureReference.created_at.desc()).all()
    result["literature_references"] = [
        {
            "id": r.id,
            "reference_type": r.reference_type,
            "title": r.title,
            "author": r.author,
            "year": r.year,
            "publisher": r.publisher,
            "page": r.page,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in lit_refs
    ]

    # 拍卖记录
    auctions = db.query(AuctionRecord).filter(
        AuctionRecord.artwork_id == artwork_id
    ).order_by(AuctionRecord.created_at.desc()).all()
    result["auction_records"] = [
        {
            "id": r.id,
            "auction_house": r.auction_house,
            "sale_date": r.sale_date,
            "lot_number": r.lot_number,
            "estimate_low": r.estimate_low,
            "estimate_high": r.estimate_high,
            "hammer_price": r.hammer_price,
            "currency": r.currency,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in auctions
    ]

    # 研究笔记（仅公开+用户自己的私有笔记）
    if user:
        notes = db.query(ResearchNote).filter(
            ResearchNote.artwork_id == artwork_id,
            (ResearchNote.visibility == "public") | (ResearchNote.user_id == user.id)
        ).order_by(ResearchNote.created_at.desc()).all()
    else:
        notes = db.query(ResearchNote).filter(
            ResearchNote.artwork_id == artwork_id,
            ResearchNote.visibility == "public"
        ).order_by(ResearchNote.created_at.desc()).all()

    result["research_notes"] = [
        {
            "id": n.id,
            "user_id": n.user_id,
            "title": n.title,
            "content": n.content,
            "visibility": n.visibility,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }
        for n in notes
    ]

    # 库信息
    if artwork.library_id:
        lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == artwork.library_id).first()
        if lib:
            result["library"] = {
                "id": lib.id,
                "name": lib.name,
                "visibility": lib.visibility,
            }

    return result


@router.put("/artworks/{artwork_id}")
async def update_artwork(
    artwork_id: int,
    req: ArtworkUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新作品元数据（仅 owner/collaborator）"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")
    _check_artwork_write_access(artwork, user, db)

    update_fields = req.dict(exclude_unset=True)
    for key, value in update_fields.items():
        if hasattr(artwork, key):
            setattr(artwork, key, value)

    db.commit()
    db.refresh(artwork)
    logger.info(f"用户 {user.id} 更新了作品 {artwork_id}")
    return _artwork_to_dict(artwork)


@router.delete("/artworks/{artwork_id}")
async def delete_artwork(
    artwork_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除作品（仅 owner）"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")

    # 仅 owner 可删除（协作者不行）
    if artwork.owner_id != user.id:
        raise HTTPException(status_code=403, detail="仅作品所有者可以删除")

    library_id = artwork.library_id

    # 删除关联数据
    db.query(LiteratureReference).filter(LiteratureReference.artwork_id == artwork_id).delete()
    db.query(AuctionRecord).filter(AuctionRecord.artwork_id == artwork_id).delete()
    db.query(ResearchNote).filter(ResearchNote.artwork_id == artwork_id).delete()

    db.delete(artwork)
    db.commit()

    # 更新作品数量
    if library_id:
        _update_artwork_count(library_id, db)
        db.commit()

    logger.info(f"用户 {user.id} 删除了作品 {artwork_id}")
    return {"success": True}


# ════════════════════════════════════════════════════════════════
# 著录引用 CRUD
# ════════════════════════════════════════════════════════════════

@router.post("/artworks/{artwork_id}/literature")
async def add_literature(
    artwork_id: int,
    req: LiteratureCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """添加著录引用"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")
    _check_artwork_write_access(artwork, user, db)

    ref = LiteratureReference(
        artwork_id=artwork_id,
        reference_type=req.reference_type,
        title=req.title,
        author=req.author,
        year=req.year,
        publisher=req.publisher,
        page=req.page,
        notes=req.notes,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return {
        "id": ref.id,
        "artwork_id": ref.artwork_id,
        "reference_type": ref.reference_type,
        "title": ref.title,
        "author": ref.author,
        "year": ref.year,
        "publisher": ref.publisher,
        "page": ref.page,
        "notes": ref.notes,
        "created_at": ref.created_at.isoformat() if ref.created_at else None,
    }


@router.delete("/artworks/{artwork_id}/literature/{ref_id}")
async def delete_literature(
    artwork_id: int,
    ref_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除著录引用"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")
    _check_artwork_write_access(artwork, user, db)

    ref = db.query(LiteratureReference).filter(
        LiteratureReference.id == ref_id,
        LiteratureReference.artwork_id == artwork_id,
    ).first()
    if not ref:
        raise HTTPException(status_code=404, detail="著录记录不存在")

    db.delete(ref)
    db.commit()
    return {"success": True}


# ════════════════════════════════════════════════════════════════
# 拍卖记录 CRUD
# ════════════════════════════════════════════════════════════════

@router.post("/artworks/{artwork_id}/auctions")
async def add_auction(
    artwork_id: int,
    req: AuctionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """添加拍卖记录"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")
    _check_artwork_write_access(artwork, user, db)

    rec = AuctionRecord(
        artwork_id=artwork_id,
        auction_house=req.auction_house,
        sale_date=req.sale_date,
        lot_number=req.lot_number,
        estimate_low=req.estimate_low,
        estimate_high=req.estimate_high,
        hammer_price=req.hammer_price,
        currency=req.currency,
        notes=req.notes,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {
        "id": rec.id,
        "artwork_id": rec.artwork_id,
        "auction_house": rec.auction_house,
        "sale_date": rec.sale_date,
        "lot_number": rec.lot_number,
        "estimate_low": rec.estimate_low,
        "estimate_high": rec.estimate_high,
        "hammer_price": rec.hammer_price,
        "currency": rec.currency,
        "notes": rec.notes,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


@router.delete("/artworks/{artwork_id}/auctions/{rec_id}")
async def delete_auction(
    artwork_id: int,
    rec_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除拍卖记录"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")
    _check_artwork_write_access(artwork, user, db)

    rec = db.query(AuctionRecord).filter(
        AuctionRecord.id == rec_id,
        AuctionRecord.artwork_id == artwork_id,
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="拍卖记录不存在")

    db.delete(rec)
    db.commit()
    return {"success": True}


# ════════════════════════════════════════════════════════════════
# 研究笔记 CRUD
# ════════════════════════════════════════════════════════════════

class NoteCreate(BaseModel):
    title: Optional[str] = None
    content: str
    visibility: str = "private"


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    visibility: Optional[str] = None


@router.post("/artworks/{artwork_id}/notes")
async def create_note(
    artwork_id: int,
    req: NoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """为作品写研究笔记"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")

    # 公开库任何人都可写，私有库仅 owner/collaborator
    if artwork.visibility == "public":
        pass  # 任何登录用户都可以
    else:
        _check_artwork_write_access(artwork, user, db)

    if req.visibility not in ("public", "private"):
        raise HTTPException(status_code=400, detail="visibility 必须是 public 或 private")

    note = ResearchNote(
        user_id=user.id,
        artwork_id=artwork_id,
        title=req.title,
        content=req.content,
        visibility=req.visibility,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "user_id": note.user_id,
        "artwork_id": note.artwork_id,
        "title": note.title,
        "content": note.content,
        "visibility": note.visibility,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


@router.get("/artworks/{artwork_id}/notes")
async def list_notes(
    artwork_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """获取作品研究笔记列表（仅公开 + 用户自己的）"""
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")

    if user:
        notes = db.query(ResearchNote).filter(
            ResearchNote.artwork_id == artwork_id,
            (ResearchNote.visibility == "public") | (ResearchNote.user_id == user.id)
        ).order_by(ResearchNote.created_at.desc()).all()
    else:
        notes = db.query(ResearchNote).filter(
            ResearchNote.artwork_id == artwork_id,
            ResearchNote.visibility == "public"
        ).order_by(ResearchNote.created_at.desc()).all()

    # 附上作者信息
    user_cache = {}
    def _get_user(uid):
        if uid not in user_cache:
            u = db.query(User).filter(User.id == uid).first()
            user_cache[uid] = u
        return user_cache[uid]

    return {
        "notes": [
            {
                "id": n.id,
                "user_id": n.user_id,
                "author_name": (_get_user(n.user_id).nickname if _get_user(n.user_id) else None),
                "author_avatar": (_get_user(n.user_id).avatar_url if _get_user(n.user_id) else None),
                "artwork_id": n.artwork_id,
                "title": n.title,
                "content": n.content,
                "visibility": n.visibility,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
            }
            for n in notes
        ]
    }


@router.get("/notes/{note_id}")
async def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """获取单条笔记详情"""
    note = db.query(ResearchNote).filter(ResearchNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")

    if note.visibility == "private":
        if user is None or note.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权查看此笔记")

    author = db.query(User).filter(User.id == note.user_id).first()
    return {
        "id": note.id,
        "user_id": note.user_id,
        "author_name": author.nickname if author else None,
        "author_avatar": author.avatar_url if author else None,
        "artwork_id": note.artwork_id,
        "title": note.title,
        "content": note.content,
        "visibility": note.visibility,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


@router.put("/notes/{note_id}")
async def update_note(
    note_id: int,
    req: NoteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """编辑笔记（仅作者）"""
    note = db.query(ResearchNote).filter(ResearchNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.user_id != user.id:
        raise HTTPException(status_code=403, detail="仅笔记作者可以编辑")

    if req.title is not None:
        note.title = req.title
    if req.content is not None:
        note.content = req.content
    if req.visibility is not None:
        if req.visibility not in ("public", "private"):
            raise HTTPException(status_code=400, detail="visibility 必须是 public 或 private")
        note.visibility = req.visibility

    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "user_id": note.user_id,
        "artwork_id": note.artwork_id,
        "title": note.title,
        "content": note.content,
        "visibility": note.visibility,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除笔记（仅作者）"""
    note = db.query(ResearchNote).filter(ResearchNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    if note.user_id != user.id:
        raise HTTPException(status_code=403, detail="仅笔记作者可以删除")

    db.delete(note)
    db.commit()
    return {"success": True}


# ════════════════════════════════════════════════════════════════
# AI 分析关联
# ════════════════════════════════════════════════════════════════

_QUEUE_KEY_PENDING = "tubi:queue:pending"
_QUEUE_KEY_PROCESSING = "tubi:queue:processing"


def _get_redis():
    """获取 Redis 连接（超时快速失败）"""
    conn = redis_lib.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.5,
        retry_on_timeout=False,
    )
    conn.ping()
    return conn


@router.post("/artworks/{artwork_id}/analyze")
async def trigger_artwork_analysis(
    artwork_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _q=Depends(check_ai_quota),
):
    """
    触发 AI 题跋分析。

    复用现有 tubi_worker 的分析流水线（区域检测 + OCR + LLM 分析）。
    返回分析任务状态，可通过 GET /artworks/{id}/analysis 轮询进度。
    """
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")
    _check_artwork_write_access(artwork, user, db)

    image_id = artwork.image_id
    if not image_id:
        raise HTTPException(status_code=400, detail="作品缺少 image_id，无法分析")

    # 已在分析中
    if artwork.status == "analyzing":
        return JSONResponse(status_code=202, content={
            "success": True,
            "data": {
                "artwork_id": artwork_id,
                "image_id": image_id,
                "status": "analyzing",
                "via": "already_processing",
            }
        })

    # 设置为排队状态
    artwork.status = "queued"
    db.commit()

    # 更新或创建 TubiJob 记录
    job = db.query(TubiJob).filter(TubiJob.image_id == image_id).first()
    if job:
        job.status = "queued"
        job.last_error = None
        job.error_code = None
    else:
        job = TubiJob(image_id=image_id, status="queued")
        db.add(job)
    db.commit()

    # 尝试 Redis 入队；失败则依赖 DB 轮询模式
    via = "db"
    try:
        conn = _get_redis()
        conn.lpush(_QUEUE_KEY_PENDING, image_id)
        via = "redis"
    except Exception as redis_err:
        logger.warning("Redis 不可用，已降级到 DB 队列: %s", redis_err)
        try:
            artwork.analysis_note = "Redis不可用，已降级到DB队列模式"
            db.commit()
        except Exception:
            pass

    logger.info(f"用户 {user.id} 触发作品 {artwork_id} (image_id={image_id}) AI分析")

    return JSONResponse(status_code=202, content={
        "success": True,
        "data": {
            "artwork_id": artwork_id,
            "image_id": image_id,
            "status": "queued",
            "via": via,
            "enqueued": True,
        }
    })


@router.get("/artworks/{artwork_id}/analysis")
async def get_artwork_analysis(
    artwork_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    获取作品 AI 分析状态和结果。

    返回当前分析状态（uploaded/queued/analyzing/analyzed/error）
    以及分析完成后的各项数据（content_analysis, regions, inscription 等）。
    """
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == artwork_id).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")

    # 权限检查
    if artwork.visibility != "public":
        if user is None:
            raise HTTPException(status_code=401, detail="请先登录")
        if artwork.owner_id != user.id:
            if artwork.library_id:
                lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == artwork.library_id).first()
                if lib:
                    is_collab = lib.owner_id == user.id or db.query(LibraryCollaborator).filter(
                        LibraryCollaborator.library_id == lib.id,
                        LibraryCollaborator.user_id == user.id,
                    ).first() is not None
                    if not is_collab:
                        raise HTTPException(status_code=403, detail="无权查看此作品的分析")
                else:
                    raise HTTPException(status_code=403, detail="无权查看此作品的分析")
            else:
                raise HTTPException(status_code=403, detail="无权查看此作品的分析")

    # 获取队列信息（Redis 可用时）
    queue_info = {}
    try:
        conn = _get_redis()
        pending_list = conn.lrange(_QUEUE_KEY_PENDING, 0, -1)
        queue_info["pending_count"] = len(pending_list)
        queue_info["position"] = (
            len(pending_list) - pending_list.index(artwork.image_id)
            if artwork.image_id and artwork.image_id in pending_list else 0
        )
        queue_info["processing_count"] = conn.llen(_QUEUE_KEY_PROCESSING) or 0
    except Exception:
        queue_info = None

    # 解析 content_analysis JSON
    content_analysis = None
    if artwork.content_analysis:
        try:
            content_analysis = json.loads(artwork.content_analysis) if isinstance(artwork.content_analysis, str) else artwork.content_analysis
        except Exception:
            content_analysis = artwork.content_analysis

    return {
        "success": True,
        "data": {
            "artwork_id": artwork_id,
            "image_id": artwork.image_id,
            "status": artwork.status,
            "error_code": artwork.error_code,
            "analysis_note": artwork.analysis_note,
            # 分析结果
            "inscription_percent": artwork.inscription_percent,
            "painting_percent": artwork.painting_percent,
            "blank_percent": artwork.blank_percent,
            "regions": artwork.regions,
            "position_analysis": artwork.position_analysis,
            "inscription_content": artwork.inscription_content,
            "inscription_modern": artwork.inscription_modern,
            "inscription_verified": artwork.inscription_verified,
            "seal_content": artwork.seal_content,
            "content_analysis": content_analysis,
            "period_phase": artwork.period_phase,
            "char_count": artwork.char_count,
            "word_count": artwork.word_count,
            "theme_tags": artwork.theme_tags,
            # 队列信息
            "queue_info": queue_info,
        }
    }
