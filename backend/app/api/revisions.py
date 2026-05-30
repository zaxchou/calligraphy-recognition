"""
作品版本历史 API — revisions
"""
import json
import logging
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user, require_editor
from app.models.user import User
from app.models.tiba_analysis import TibaAnalysis
from app.models.work_revision import WorkRevision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artworks", tags=["版本历史"])


def _resolve_artwork(db: Session, artwork_id: Union[str, int]) -> TibaAnalysis:
    """通过 id（数字）或 image_id（UUID）查找作品"""
    try:
        int_id = int(artwork_id)
        artwork = db.query(TibaAnalysis).filter(TibaAnalysis.id == int_id).first()
    except (ValueError, TypeError):
        artwork = None
    if not artwork:
        artwork = db.query(TibaAnalysis).filter(TibaAnalysis.image_id == str(artwork_id)).first()
    if not artwork:
        raise HTTPException(status_code=404, detail="作品不存在")
    return artwork


def build_snapshot(artwork: TibaAnalysis) -> dict:
    """从 TibaAnalysis 对象构建完整数据快照"""
    return {
        "title": artwork.title,
        "artist": artwork.artist,
        "year": artwork.year,
        "period": artwork.period,
        "notes": artwork.notes,
        "inscription_content": artwork.inscription_content,
        "inscription_modern": artwork.inscription_modern,
        "seal_content": artwork.seal_content,
        "material": artwork.material,
        "mounting_format": artwork.mounting_format,
        "current_location": artwork.current_location,
        "provenance": artwork.provenance,
        "style_tags": artwork.style_tags,
        "subject_tags": artwork.subject_tags,
        "technique_tags": artwork.technique_tags,
        "free_tags": artwork.free_tags,
        "inscription_author": artwork.inscription_author,
        "inscription_date": artwork.inscription_date,
        "artwork_width_cm": artwork.artwork_width_cm,
        "artwork_height_cm": artwork.artwork_height_cm,
        "analysis_note": artwork.analysis_note,
        "regions": artwork.regions,
    }


def create_revision(
    db: Session,
    artwork_id: int,
    operation_type: str,
    change_summary: Optional[str] = None,
    approved_by: Optional[int] = None,
    submitted_by: Optional[int] = None,
    change_request_id: Optional[int] = None,
) -> WorkRevision:
    """创建一条版本历史记录"""
    artwork = db.query(TibaAnalysis).filter(TibaAnalysis.id == artwork_id).first()
    if not artwork:
        raise ValueError(f"作品 {artwork_id} 不存在")

    last_rev = db.query(WorkRevision).filter(
        WorkRevision.artwork_id == artwork_id
    ).order_by(WorkRevision.revision_number.desc()).first()
    next_number = (last_rev.revision_number + 1) if last_rev else 1

    revision = WorkRevision(
        artwork_id=artwork_id,
        revision_number=next_number,
        snapshot=json.dumps(build_snapshot(artwork), ensure_ascii=False, default=str),
        change_summary=change_summary,
        operation_type=operation_type,
        approved_by=approved_by,
        submitted_by=submitted_by,
        change_request_id=change_request_id,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    logger.info("创建版本 %d (artwork_id=%s, type=%s)", next_number, artwork_id, operation_type)
    return revision


def _revision_to_response(r: WorkRevision) -> dict:
    return {
        "id": r.id,
        "artwork_id": r.artwork_id,
        "revision_number": r.revision_number,
        "snapshot": json.loads(r.snapshot) if isinstance(r.snapshot, str) else r.snapshot,
        "change_summary": r.change_summary,
        "operation_type": r.operation_type,
        "approved_by": r.approved_by,
        "submitted_by": r.submitted_by,
        "change_request_id": r.change_request_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/{artwork_id}/revisions")
async def list_revisions(
    artwork_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取作品的历史版本列表"""
    artwork = _resolve_artwork(db, artwork_id)

    revisions = db.query(WorkRevision).filter(
        WorkRevision.artwork_id == artwork.id
    ).order_by(WorkRevision.revision_number.desc()).limit(limit).all()

    return {
        "artwork_id": artwork.id,
        "image_id": artwork.image_id,
        "total": len(revisions),
        "revisions": [_revision_to_response(r) for r in revisions],
    }


@router.get("/{artwork_id}/revisions/{revision_id}")
async def get_revision(
    artwork_id: str,
    revision_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取某版本快照"""
    artwork = _resolve_artwork(db, artwork_id)

    revision = db.query(WorkRevision).filter(
        WorkRevision.id == revision_id,
        WorkRevision.artwork_id == artwork.id,
    ).first()
    if not revision:
        raise HTTPException(status_code=404, detail="版本不存在")

    return _revision_to_response(revision)


@router.post("/{artwork_id}/rollback/{revision_id}")
async def rollback_revision(
    artwork_id: str,
    revision_id: int,
    db: Session = Depends(get_db),
    editor=Depends(require_editor),
):
    """回滚到指定版本（仅 editor+）"""
    artwork = _resolve_artwork(db, artwork_id)
    user = db.query(User).filter(User.id == editor.id).first()

    revision = db.query(WorkRevision).filter(
        WorkRevision.id == revision_id,
        WorkRevision.artwork_id == artwork.id,
    ).first()
    if not revision:
        raise HTTPException(status_code=404, detail="版本不存在")

    snapshot = json.loads(revision.snapshot) if isinstance(revision.snapshot, str) else revision.snapshot
    if not isinstance(snapshot, dict):
        raise HTTPException(status_code=400, detail="快照数据格式错误")

    for field, value in snapshot.items():
        if hasattr(artwork, field):
            setattr(artwork, field, value)

    db.commit()

    new_revision = create_revision(
        db=db,
        artwork_id=artwork.id,
        operation_type="rollback",
        change_summary=f"回滚到版本 #{revision.revision_number}",
        approved_by=user.id,
        submitted_by=user.id,
    )

    logger.info("用户 %s 将作品 %s 回滚到版本 %d", user.id, artwork_id, revision.revision_number)
    return _revision_to_response(new_revision)
