"""
画家认领 API — /api/v1/artist-claims + /api/v1/admin/artist-claims

Phase 3: 编者认领画家制 —— 认领后可全权管理该画家的作品。
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user, require_admin_role
from app.models.user import User
from app.models.artist_claim import ArtistClaim

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Pydantic schemas ──

class ClaimApply(BaseModel):
    artist_name: str
    claim_type: str = "wiki"  # wiki / full
    apply_reason: Optional[str] = None

    @field_validator("claim_type")
    @classmethod
    def validate_claim_type(cls, v: str) -> str:
        if v not in ("wiki", "full"):
            raise ValueError("claim_type 必须是 wiki 或 full")
        return v

    @field_validator("artist_name")
    @classmethod
    def validate_artist_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("画家名称不能为空")
        return v


class ClaimReview(BaseModel):
    action: str  # approve / reject
    review_comment: Optional[str] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("approve", "reject"):
            raise ValueError("action 必须是 approve 或 reject")
        return v


def _claim_to_dict(claim: ArtistClaim) -> dict:
    return {
        "id": claim.id,
        "user_id": claim.user_id,
        "artist_name": claim.artist_name,
        "claim_type": claim.claim_type,
        "status": claim.status,
        "apply_reason": claim.apply_reason,
        "reviewed_by": claim.reviewed_by,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "reviewed_at": claim.reviewed_at.isoformat() if claim.reviewed_at else None,
    }


# ════════════════════════════════════════════════════════════════
# 用户端: 我的认领
# ════════════════════════════════════════════════════════════════

@router.post("/artist-claims")
async def apply_artist_claim(
    req: ClaimApply,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    申请认领画家。

    规则：
    - editor 及以上角色才能申请
    - 同一用户对同一画家只能有一条认领记录
    - 初始状态为 pending
    """
    if user.role not in ("editor", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="编者及以上角色才能认领画家，请先升级")

    artist_name = req.artist_name.strip()

    # 检查是否已有认领记录
    existing = db.query(ArtistClaim).filter(
        ArtistClaim.user_id == user.id,
        ArtistClaim.artist_name == artist_name,
    ).first()
    if existing:
        if existing.status == "rejected":
            # 被拒后可重新申请
            existing.status = "pending"
            existing.claim_type = req.claim_type
            existing.apply_reason = req.apply_reason
            existing.reviewed_by = None
            existing.reviewed_at = None
            existing.created_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            logger.info(f"用户 {user.id} 重新申请认领画家「{artist_name}」")
            return {"success": True, "claim": _claim_to_dict(existing), "message": "已重新提交认领申请"}
        raise HTTPException(status_code=409, detail=f"您已有该画家的认领记录（{existing.status}）")

    claim = ArtistClaim(
        user_id=user.id,
        artist_name=artist_name,
        claim_type=req.claim_type,
        apply_reason=req.apply_reason,
        status="pending",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    logger.info(f"用户 {user.id} 申请认领画家「{artist_name}」({req.claim_type})")
    return {"success": True, "claim": _claim_to_dict(claim), "message": "认领申请已提交，请等待审核"}


@router.get("/artist-claims")
async def list_my_claims(
    status: Optional[str] = Query(None, description="筛选: pending/approved/rejected"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """我的认领列表"""
    q = db.query(ArtistClaim).filter(ArtistClaim.user_id == user.id)
    if status:
        q = q.filter(ArtistClaim.status == status)
    claims = q.order_by(ArtistClaim.created_at.desc()).all()
    return {"claims": [_claim_to_dict(c) for c in claims]}


# ════════════════════════════════════════════════════════════════
# 管理端: 审核认领
# ════════════════════════════════════════════════════════════════

@router.get("/admin/artist-claims")
async def list_all_claims(
    status: Optional[str] = Query(None, description="筛选: pending/approved/rejected"),
    artist_name: Optional[str] = Query(None, description="按画家名筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """所有认领记录（admin+）"""
    q = db.query(ArtistClaim)
    if status:
        q = q.filter(ArtistClaim.status == status)
    if artist_name:
        q = q.filter(ArtistClaim.artist_name.like(f"%{artist_name}%"))

    total = q.count()
    offset = (page - 1) * page_size
    claims = q.order_by(ArtistClaim.created_at.desc()).offset(offset).limit(page_size).all()

    items = []
    for c in claims:
        claim_user = db.query(User).filter(User.id == c.user_id).first()
        item = _claim_to_dict(c)
        item["applicant"] = {
            "id": claim_user.id if claim_user else None,
            "nickname": claim_user.nickname if claim_user else None,
            "phone": claim_user.phone if claim_user else None,
        }
        if c.reviewed_by:
            reviewer = db.query(User).filter(User.id == c.reviewed_by).first()
            item["reviewer"] = {"id": reviewer.id, "nickname": reviewer.nickname} if reviewer else None
        items.append(item)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/admin/artist-claims/{claim_id}/review")
async def review_artist_claim(
    claim_id: int,
    req: ClaimReview,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """审核认领申请（admin+）

    - approve: 批准认领，编者可全权管理该画家
    - reject: 拒绝认领，附审核意见
    """
    claim = db.query(ArtistClaim).filter(ArtistClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="认领记录不存在")
    if claim.status != "pending":
        raise HTTPException(status_code=409, detail="该认领已审核过")

    claim.status = "approved" if req.action == "approve" else "rejected"
    claim.reviewed_by = admin.id
    claim.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(claim)

    logger.info(f"管理员 {admin.id} {req.action}了用户 {claim.user_id} 对「{claim.artist_name}」的认领")

    return {"success": True, "claim": _claim_to_dict(claim), "message": f"认领已{'批准' if req.action == 'approve' else '拒绝'}"}


@router.get("/artist-claims/my-artists")
async def list_my_artists(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取我已认领的画家列表（用于权限判断和UI展示）"""
    if user.role not in ("editor", "admin", "super_admin"):
        return {"artists": []}

    q = db.query(ArtistClaim).filter(
        ArtistClaim.user_id == user.id,
        ArtistClaim.status == "approved",
    )

    # super_admin/admin 可以管理所有画家
    if user.role in ("super_admin", "admin"):
        claims = q.all()
    else:
        claims = q.all()

    return {
        "artists": [
            {"artist_name": c.artist_name, "claim_type": c.claim_type}
            for c in claims
        ]
    }
