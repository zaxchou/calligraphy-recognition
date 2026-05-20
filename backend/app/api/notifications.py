"""
通知 API — notifications
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.models.change_request import ChangeRequest
from app.models.tubi_analysis import TubiAnalysis
from app.models.artwork_library import ArtworkLibrary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["通知"])


def create_notification_for_review(cr_id: int, action: str, reviewer_id: int, db: Session):
    """审核通过/拒绝后创建通知给提交者"""
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()
    if not cr:
        return
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == cr.artwork_id).first()
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == cr.library_id).first()
    artwork_title = artwork.title or artwork.filename or f"作品#{cr.artwork_id}" if artwork else "作品"

    if action == "approve":
        notif_type = "cr_approved"
        title = f"你的修改建议已通过"
        body = f"你对「{artwork_title}」的修改建议已被审核通过并生效。"
    else:
        notif_type = "cr_rejected"
        title = f"你的修改建议已被驳回"
        body = f"你对「{artwork_title}」的修改建议未被采纳。"

    if cr.submitter_id and cr.submitter_id != reviewer_id:
        notif = Notification(
            user_id=cr.submitter_id,
            type=notif_type,
            title=title,
            body=body,
            reference_type="change_request",
            reference_id=cr_id,
        )
        db.add(notif)
        db.commit()
        logger.info("已创建通知: user=%s type=%s cr=%d", cr.submitter_id, notif_type, cr_id)


def notify_admins_of_pending(cr_id: int, db: Session):
    """新提交时通知所有 admin/editor"""
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()
    if not cr:
        return
    artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == cr.artwork_id).first()
    lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == cr.library_id).first()
    artwork_title = artwork.title or artwork.filename or f"作品#{cr.artwork_id}" if artwork else "作品"
    lib_name = lib.name if lib else "画库"

    admins = db.query(User).filter(User.role.in_(["admin", "super_admin"])).all()
    for admin in admins:
        if admin.id == cr.submitter_id:
            continue
        notif = Notification(
            user_id=admin.id,
            type="cr_pending",
            title="新的修改建议待审核",
            body=f"用户对「{artwork_title}」（{lib_name}）提交了修改建议。",
            reference_type="change_request",
            reference_id=cr_id,
        )
        db.add(notif)
    db.commit()
    logger.info("已通知 %d 位管理员（cr=%d）", len(admins), cr_id)


def _notif_to_response(n: Notification) -> dict:
    return {
        "id": n.id,
        "user_id": n.user_id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "reference_type": n.reference_type,
        "reference_id": n.reference_id,
        "is_read": bool(n.is_read),
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
async def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取我的通知列表（未读在前）"""
    notifs = db.query(Notification).filter(
        Notification.user_id == user.id,
    ).order_by(Notification.is_read.asc(), Notification.created_at.desc()).limit(100).all()

    return {
        "total": len(notifs),
        "notifications": [_notif_to_response(n) for n in notifs],
    }


@router.get("/unread-count")
async def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """未读通知数量"""
    count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == 0,
    ).count()
    return {"count": count}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """标记已读"""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="通知不存在")

    notif.is_read = 1
    db.commit()
    return {"success": True}


@router.put("/read-all")
async def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全部标记已读"""
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == 0,
    ).update({"is_read": 1})
    db.commit()
    return {"success": True}


@router.get("/my/contributions")
async def my_contributions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """我的贡献列表——我提交的所有修改建议"""
    crs = db.query(ChangeRequest).filter(
        ChangeRequest.submitter_id == user.id,
    ).order_by(ChangeRequest.created_at.desc()).limit(100).all()

    result = []
    for cr in crs:
        artwork = db.query(TubiAnalysis).filter(TubiAnalysis.id == cr.artwork_id).first()
        lib = db.query(ArtworkLibrary).filter(ArtworkLibrary.id == cr.library_id).first()
        result.append({
            "id": cr.id,
            "artwork_id": cr.artwork_id,
            "artwork_title": artwork.title if artwork else None,
            "library_name": lib.name if lib else None,
            "request_type": cr.request_type,
            "field_name": cr.field_name,
            "old_value": cr.old_value,
            "new_value": cr.new_value,
            "change_summary": cr.change_summary,
            "status": cr.status,
            "review_comment": cr.review_comment,
            "created_at": cr.created_at.isoformat() if cr.created_at else None,
            "reviewed_at": cr.reviewed_at.isoformat() if cr.reviewed_at else None,
        })
    return {"contributions": result}
