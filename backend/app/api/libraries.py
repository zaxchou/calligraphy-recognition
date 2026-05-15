"""
作品库 CRUD API — /api/v1/libraries
Phase 2: 作品库产品线
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.core.database import get_db
from app.core.auth import get_current_user, get_optional_user
from app.core.quota import check_library_quota
from app.models.artwork_library import ArtworkLibrary
from app.models.library_collaborator import LibraryCollaborator
from app.models.change_request import ChangeRequest
from app.models.tubi_analysis import TubiAnalysis
from app.models.user import User
from app.api.revisions import create_revision
from app.api.notifications import create_notification_for_review, notify_admins_of_pending

router = APIRouter(prefix="/libraries", tags=["作品库"])
logger = logging.getLogger(__name__)


# ── Pydantic schemas ──

class LibraryCreate(BaseModel):
    name: str
    artist_name: Optional[str] = None
    description: Optional[str] = None
    visibility: str = "private"  # public / private


class LibraryUpdate(BaseModel):
    name: Optional[str] = None
    artist_name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None


class LibraryResponse(BaseModel):
    id: int
    name: str
    artist_name: Optional[str] = None
    description: Optional[str] = None
    owner_id: int
    visibility: str
    artwork_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class LibraryDetailResponse(LibraryResponse):
    collaborators: List[dict] = []


class CollaboratorInfo(BaseModel):
    user_id: int
    nickname: Optional[str] = None
    role: str = "viewer"
    added_at: Optional[str] = None


# ── Helper ──

def _library_to_response(lib: ArtworkLibrary) -> dict:
    """将 ORM 对象转为字典（含时间戳字符串化）"""
    return {
        "id": lib.id,
        "name": lib.name,
        "artist_name": lib.artist_name,
        "description": lib.description,
        "owner_id": lib.owner_id,
        "visibility": lib.visibility,
        "artwork_count": lib.artwork_count or 0,
        "created_at": lib.created_at.isoformat() if lib.created_at else None,
        "updated_at": lib.updated_at.isoformat() if lib.updated_at else None,
    }


# ── API Endpoints ──

@router.post("")
async def create_library(
    req: LibraryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _q=Depends(check_library_quota),
):
    """创建作品库"""
    if req.visibility not in ("public", "private"):
        raise HTTPException(status_code=400, detail="visibility 必须是 public 或 private")

    lib = ArtworkLibrary(
        name=req.name,
        artist_name=req.artist_name,
        description=req.description,
        owner_id=user.id,
        visibility=req.visibility,
        artwork_count=0,
    )
    db.add(lib)
    db.commit()
    db.refresh(lib)
    logger.info(f"用户 {user.id} 创建了作品库 '{lib.name}' (id={lib.id})")
    return _library_to_response(lib)


@router.get("")
async def list_my_libraries(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """我的作品库列表"""
    libs = db.query(ArtworkLibrary).filter(
        ArtworkLibrary.owner_id == user.id
    ).order_by(ArtworkLibrary.updated_at.desc()).all()
    return [_library_to_response(lib) for lib in libs]


@router.get("/public")
async def list_public_libraries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """公共作品库列表（分页）"""
    offset = (page - 1) * page_size
    total = db.query(sqlfunc.count(ArtworkLibrary.id)).filter(
        ArtworkLibrary.visibility == "public"
    ).scalar()
    libs = db.query(ArtworkLibrary).filter(
        ArtworkLibrary.visibility == "public"
    ).order_by(ArtworkLibrary.updated_at.desc()).offset(offset).limit(page_size).all()

    return {
        "items": [_library_to_response(lib) for lib in libs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{library_id}")
async def get_library_detail(
    library_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """库详情（含协作者列表）"""
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")

    # 权限检查
    if lib.visibility != "public":
        if user is None:
            raise HTTPException(status_code=401, detail="请先登录")
        # 检查是否为 owner 或 collaborator
        is_collab = db.query(LibraryCollaborator).filter(
            LibraryCollaborator.library_id == library_id,
            LibraryCollaborator.user_id == user.id,
        ).first() is not None
        if lib.owner_id != user.id and not is_collab:
            raise HTTPException(status_code=403, detail="无权访问此作品库")

    # 获取协作者列表
    collaborators = []
    collab_records = db.query(LibraryCollaborator).filter(
        LibraryCollaborator.library_id == library_id
    ).all()
    for c in collab_records:
        collab_user = db.query(User).filter(User.id == c.user_id).first()
        collaborators.append({
            "user_id": c.user_id,
            "nickname": collab_user.nickname if collab_user else None,
            "avatar_url": collab_user.avatar_url if collab_user else None,
            "role": c.role,
            "added_at": c.added_at.isoformat() if c.added_at else None,
        })

    # 实际作品数（从 tubi_analyses 统计，确保准确）
    actual_count = db.query(sqlfunc.count(TubiAnalysis.id)).filter(
        TubiAnalysis.library_id == library_id
    ).scalar()

    result = _library_to_response(lib)
    result["artwork_count"] = actual_count
    result["collaborators"] = collaborators
    return result


@router.put("/{library_id}")
async def update_library(
    library_id: int,
    req: LibraryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新库信息（仅 owner 可操作）"""
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")
    if lib.owner_id != user.id:
        raise HTTPException(status_code=403, detail="仅库主可以修改作品库信息")

    if req.name is not None:
        lib.name = req.name
    if req.artist_name is not None:
        lib.artist_name = req.artist_name
    if req.description is not None:
        lib.description = req.description
    if req.visibility is not None:
        if req.visibility not in ("public", "private"):
            raise HTTPException(status_code=400, detail="visibility 必须是 public 或 private")
        lib.visibility = req.visibility

    db.commit()
    db.refresh(lib)
    logger.info(f"用户 {user.id} 更新了作品库 {library_id}")
    return _library_to_response(lib)


@router.delete("/{library_id}")
async def delete_library(
    library_id: int,
    cascade: bool = Query(False, description="是否级联删除库内所有作品"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除作品库（仅 owner 可操作）

    - cascade=false（默认）：仅当库内无作品时允许删除
    - cascade=true：删除库内所有作品再删除库
    """
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")
    if lib.owner_id != user.id:
        raise HTTPException(status_code=403, detail="仅库主可以删除作品库")

    artwork_count = db.query(sqlfunc.count(TubiAnalysis.id)).filter(
        TubiAnalysis.library_id == library_id
    ).scalar()

    if artwork_count > 0 and not cascade:
        raise HTTPException(
            status_code=409,
            detail=f"作品库内还有 {artwork_count} 件作品，请先移出或设置 cascade=true 级联删除"
        )

    if cascade and artwork_count > 0:
        # 级联删除：将作品从库中移除（设置 library_id=NULL）
        db.query(TubiAnalysis).filter(TubiAnalysis.library_id == library_id).update(
            {TubiAnalysis.library_id: None}
        )

    # 删除协作者记录
    db.query(LibraryCollaborator).filter(LibraryCollaborator.library_id == library_id).delete()
    # 删除库
    db.delete(lib)
    db.commit()
    logger.info(f"用户 {user.id} 删除了作品库 {library_id}")
    return {"success": True, "deleted_artworks": artwork_count if cascade else 0}


# ════════════════════════════════════════════════════════════════
# 协作者管理
# ════════════════════════════════════════════════════════════════

class CollaboratorAdd(BaseModel):
    user_id: Optional[int] = None
    openid: Optional[str] = None
    role: str = "viewer"  # viewer / editor / maintainer


@router.get("/{library_id}/collaborators")
async def list_collaborators(
    library_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取协作者列表"""
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")
    if lib.owner_id != user.id:
        # 协作者也可以查看协作者列表
        is_collab = db.query(LibraryCollaborator).filter(
            LibraryCollaborator.library_id == library_id,
            LibraryCollaborator.user_id == user.id,
        ).first() is not None
        if not is_collab:
            raise HTTPException(status_code=403, detail="无权查看协作者列表")

    collabs = db.query(LibraryCollaborator).filter(
        LibraryCollaborator.library_id == library_id
    ).all()

    result = []
    for c in collabs:
        cu = db.query(User).filter(User.id == c.user_id).first()
        result.append({
            "id": c.id,
            "user_id": c.user_id,
            "nickname": cu.nickname if cu else None,
            "avatar_url": cu.avatar_url if cu else None,
            "role": c.role,
            "added_at": c.added_at.isoformat() if c.added_at else None,
        })
    return {"collaborators": result}


@router.post("/{library_id}/collaborators")
async def add_collaborator(
    library_id: int,
    req: CollaboratorAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """邀请用户成为协作者（仅 owner 可操作）"""
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")
    if lib.owner_id != user.id:
        raise HTTPException(status_code=403, detail="仅库主可以管理协作者")

    # 查找目标用户
    target_user = None
    if req.user_id:
        target_user = db.query(User).filter(User.id == req.user_id).first()
    elif req.openid:
        target_user = db.query(User).filter(User.wechat_openid == req.openid).first()

    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="不能把自己添加为协作者")

    # 检查是否已是协作者
    existing = db.query(LibraryCollaborator).filter(
        LibraryCollaborator.library_id == library_id,
        LibraryCollaborator.user_id == target_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="该用户已是协作者")

    if req.role not in ("viewer", "editor", "maintainer"):
        raise HTTPException(status_code=400, detail="角色必须是 viewer/editor/maintainer")

    collab = LibraryCollaborator(
        library_id=library_id,
        user_id=target_user.id,
        role=req.role,
    )
    db.add(collab)
    db.commit()
    db.refresh(collab)
    logger.info(f"用户 {user.id} 添加 {target_user.id} 为库 {library_id} 的 {req.role}")
    return {
        "id": collab.id,
        "library_id": collab.library_id,
        "user_id": collab.user_id,
        "role": collab.role,
        "added_at": collab.added_at.isoformat() if collab.added_at else None,
    }


@router.delete("/{library_id}/collaborators/{collab_user_id}")
async def remove_collaborator(
    library_id: int,
    collab_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """移除协作者（仅 owner 可操作）"""
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")
    if lib.owner_id != user.id:
        raise HTTPException(status_code=403, detail="仅库主可以管理协作者")

    collab = db.query(LibraryCollaborator).filter(
        LibraryCollaborator.library_id == library_id,
        LibraryCollaborator.user_id == collab_user_id,
    ).first()
    if not collab:
        raise HTTPException(status_code=404, detail="协作者不存在")

    db.delete(collab)
    db.commit()
    logger.info(f"用户 {user.id} 移除了库 {library_id} 的协作者 {collab_user_id}")
    return {"success": True}


# ════════════════════════════════════════════════════════════════
# Wiki 变更请求
# ════════════════════════════════════════════════════════════════

class ChangeRequestCreate(BaseModel):
    artwork_id: int
    request_type: str  # edit_field / edit_inscription / adjust_region / add_field
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    change_summary: Optional[str] = None


class ChangeRequestReview(BaseModel):
    action: str  # approve / reject
    review_comment: Optional[str] = None


@router.get("/requests/all")
async def list_all_change_requests(
    status: str = Query("pending", description="筛选状态: pending/approved/rejected"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取所有画库的变更请求（不限 library_id）
    权限：仅 admin/super_admin 可查看全局列表
    """
    if user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权查看全局待审核列表")

    query = db.query(ChangeRequest).filter(ChangeRequest.status == status)
    query = query.order_by(ChangeRequest.created_at.desc()).limit(100)

    result = []
    for cr in query.all():
        artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == cr.artwork_id).first()
        lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == cr.library_id).first()
        submitter = db.query(User).filter(User.id == cr.submitter_id).first()
        result.append({
            "id": cr.id,
            "artwork_id": cr.artwork_id,
            "artwork_title": artwork.title if artwork else None,
            "library_id": cr.library_id,
            "library_name": lib.name if lib else None,
            "request_type": cr.request_type,
            "field_name": cr.field_name,
            "old_value": cr.old_value,
            "new_value": cr.new_value,
            "change_summary": cr.change_summary,
            "submitter_id": cr.submitter_id,
            "submitter_name": submitter.nickname if submitter else None,
            "status": cr.status,
            "created_at": cr.created_at.isoformat() if cr.created_at else None,
            "reviewed_at": cr.reviewed_at.isoformat() if cr.reviewed_at else None,
        })
    return {"requests": result}


@router.get("/{library_id}/requests")
async def list_change_requests(
    library_id: int,
    status: str = Query("pending", description="筛选状态: pending/approved/rejected"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """待审核列表（仅 owner/maintainer 可查看）"""
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")

    # 仅 owner 或 maintainer 可审核
    if lib.owner_id != user.id:
        is_maintainer = db.query(LibraryCollaborator).filter(
            LibraryCollaborator.library_id == library_id,
            LibraryCollaborator.user_id == user.id,
            LibraryCollaborator.role == "maintainer",
        ).first() is not None
        if not is_maintainer:
            raise HTTPException(status_code=403, detail="仅库主或 maintainer 可以审核变更请求")

    requests = db.query(ChangeRequest).filter(
        ChangeRequest.library_id == library_id,
        ChangeRequest.status == status,
    ).order_by(ChangeRequest.created_at.desc()).all()

    result = []
    for r in requests:
        submitter = db.query(User).filter(User.id == r.submitter_id).first()
        artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == r.artwork_id).first()
        result.append({
            "id": r.id,
            "artwork_id": r.artwork_id,
            "artwork_title": artwork.title if artwork else None,
            "request_type": r.request_type,
            "field_name": r.field_name,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "change_summary": r.change_summary,
            "submitter_id": r.submitter_id,
            "submitter_name": submitter.nickname if submitter else None,
            "submitter_avatar": submitter.avatar_url if submitter else None,
            "status": r.status,
            "review_comment": r.review_comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        })
    return {"requests": result}


@router.post("/{library_id}/requests")
async def submit_change_request(
    library_id: int,
    req: ChangeRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """提交变更请求（任何登录用户可对公开库提交）"""
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == library_id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="作品库不存在")

    # 公开库任何人都可以提交变更；私有库仅协作者
    if lib.visibility != "public":
        if lib.owner_id != user.id:
            is_collab = db.query(LibraryCollaborator).filter(
                LibraryCollaborator.library_id == library_id,
                LibraryCollaborator.user_id == user.id,
            ).first() is not None
            if not is_collab:
                raise HTTPException(status_code=403, detail="无权提交变更请求")

    # 验证 request_type
    valid_types = ("edit_field", "edit_inscription", "adjust_region", "add_field")
    if req.request_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"request_type 必须是 {valid_types} 之一")

    # 强制编辑摘要
    if not req.change_summary or not req.change_summary.strip():
        raise HTTPException(status_code=400, detail="请填写修改说明（change_summary）")

    # 验证 artwork 存在且属于该库
    artwork = db.query(TubiAnalysis).filter(
        TubiAnalysis.id == req.artwork_id,
        TubiAnalysis.library_id == library_id,
    ).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在或不属于该库")

    cr = ChangeRequest(
        library_id=library_id,
        artwork_id=req.artwork_id,
        request_type=req.request_type,
        field_name=req.field_name,
        old_value=req.old_value,
        new_value=req.new_value,
        change_summary=req.change_summary,
        submitter_id=user.id,
        status="pending",
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    logger.info(f"用户 {user.id} 提交了库 {library_id} 的变更请求 {cr.id}")

    # 通知管理员
    try:
        notify_admins_of_pending(cr.id, db)
    except Exception as _notif_e:
        logger.warning("通知管理员失败（不影响提交）: %s", _notif_e)

    return {
        "id": cr.id,
        "artwork_id": cr.artwork_id,
        "request_type": cr.request_type,
        "field_name": cr.field_name,
        "status": cr.status,
        "created_at": cr.created_at.isoformat() if cr.created_at else None,
    }


@router.post("/requests/{request_id}/review")
async def review_change_request(
    request_id: int,
    req: ChangeRequestReview,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """审核变更请求（approve/reject）

    - approve: 自动更新 artwork 对应字段
    - reject: 标记为 rejected
    """
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == request_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="变更请求不存在")
    if cr.status != "pending":
        raise HTTPException(status_code=409, detail="该请求已被审核")

    # 权限：库 owner / maintainer / 作品 owner / admin
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == cr.library_id).first()
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == cr.artwork_id).first()
    can_review = False
    if lib and lib.owner_id == user.id:
        can_review = True
    elif lib and db.query(LibraryCollaborator).filter(
        LibraryCollaborator.library_id == cr.library_id,
        LibraryCollaborator.user_id == user.id,
        LibraryCollaborator.role == "maintainer",
    ).first() is not None:
        can_review = True
    elif artwork and artwork.owner_id == user.id:
        can_review = True
    elif user.role in ("admin", "super_admin"):
        can_review = True
    if not can_review:
        raise HTTPException(status_code=403, detail="仅库主/maintainer/作品所有者/管理员可以审核变更请求")

    if req.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action 必须是 approve 或 reject")

    cr.reviewer_id = user.id
    cr.review_comment = req.review_comment
    from datetime import datetime as dt
    cr.reviewed_at = dt.now()

    if req.action == "approve":
        cr.status = "approved"

        # 自动应用变更到 artwork
        artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == cr.artwork_id).first()
        if artwork and cr.request_type in ("edit_field", "add_field"):
            if cr.field_name and cr.new_value is not None:
                # 安全白名单：只允许更新特定字段
                safe_fields = {
                    "title", "artist", "year", "period", "notes",
                    "material", "mounting_format", "current_location", "provenance",
                    "style_tags", "subject_tags", "technique_tags", "free_tags",
                    "inscription_author", "inscription_date",
                    "artwork_width_cm", "artwork_height_cm",
                }
                if cr.field_name in safe_fields:
                    # 类型转换
                    value = cr.new_value
                    if cr.field_name == "year":
                        try:
                            value = int(cr.new_value)
                        except (ValueError, TypeError):
                            pass
                    elif cr.field_name in ("artwork_width_cm", "artwork_height_cm"):
                        try:
                            value = float(cr.new_value)
                        except (ValueError, TypeError):
                            pass
                    setattr(artwork, cr.field_name, value)
                    db.commit()
                    logger.info(f"变更请求 {cr.id} 已批准: {cr.field_name} = {value}")

        elif artwork and cr.request_type == "edit_inscription":
            if cr.new_value is not None:
                artwork.inscription_content = cr.new_value
                db.commit()

        elif artwork and cr.request_type == "adjust_region":
            if cr.new_value is not None:
                import json as _json
                try:
                    new_regions = _json.loads(cr.new_value) if isinstance(cr.new_value, str) else cr.new_value
                    artwork.regions = new_regions
                    db.commit()
                except Exception:
                    logger.warning(f"变更请求 {cr.id}: adjust_region JSON 解析失败")

    else:
        cr.status = "rejected"

    db.commit()
    db.refresh(cr)

    # 审核通过时创建版本快照
    if req.action == "approve" and artwork:
        try:
            create_revision(
                db=db,
                artwork_id=cr.artwork_id,
                operation_type="approve",
                change_summary=cr.change_summary or f"审核通过: {cr.field_name or cr.request_type}",
                approved_by=user.id,
                submitted_by=cr.submitter_id,
                change_request_id=cr.id,
            )
        except Exception as _rev_e:
            logger.warning("创建版本快照失败（不影响审核）: %s", _rev_e)

    # 通知提交者
    try:
        create_notification_for_review(cr.id, req.action, user.id, db)
    except Exception as _notif_e:
        logger.warning("创建通知失败（不影响审核）: %s", _notif_e)

    # 审核通过时加贡献积分
    if req.action == "approve" and cr.submitter_id and cr.submitter_id != user.id:
        try:
            submitter = db.query(User).filter(User.id == cr.submitter_id).first()
            if submitter:
                submitter.score = (submitter.score or 0) + 3
                db.commit()
                logger.info("用户 %s 贡献积分 +3（审核通过 cr=%d）", cr.submitter_id, cr.id)
        except Exception as _score_e:
            logger.warning("加积分失败（不影响审核）: %s", _score_e)

    logger.info(f"用户 {user.id} {req.action}了变更请求 {cr.id}")
    return {
        "id": cr.id,
        "artwork_id": cr.artwork_id,
        "status": cr.status,
        "review_comment": cr.review_comment,
        "reviewed_at": cr.reviewed_at.isoformat() if cr.reviewed_at else None,
    }
