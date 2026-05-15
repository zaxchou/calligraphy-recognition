"""
管理后台 API — /api/v1/admin

所有端点均需管理员 JWT 角色（admin / super_admin）。
不再依赖旧的 X-Admin-Key 方式。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.core.auth import require_admin_role, require_super_admin, get_user_permissions, ALL_PERMISSION_KEYS
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.models.tubi_analysis import TubiAnalysis
from app.models.artist_claim import ArtistClaim
from app.models.role_permission import RolePermission

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["管理后台"])


# ── Pydantic schemas ──

class UserOut(BaseModel):
    id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    subscription_tier: str
    subscription_expires_at: Optional[str] = None
    storage_used_bytes: int = 0
    ai_calls_this_month: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class UserUpdateIn(BaseModel):
    nickname: Optional[str] = None
    role: Optional[str] = None
    subscription_tier: Optional[str] = None
    is_banned: Optional[bool] = None
    ai_calls_this_month: Optional[int] = None


class SubscriptionOut(BaseModel):
    user_id: int
    nickname: Optional[str] = None
    subscription_tier: str
    subscription_expires_at: Optional[str] = None
    created_at: Optional[str] = None


class SubscriptionCreateIn(BaseModel):
    user_id: int
    tier: str  # free / pro / premium
    duration_days: int = 30


class StatsOut(BaseModel):
    total_users: int
    total_artworks: int
    total_libraries: int
    total_storage_bytes: int
    ai_calls_today: int


class ConfigOut(BaseModel):
    free_ai_calls_per_month: int
    paid_ai_calls_per_month: int
    free_storage_bytes: int
    paid_storage_bytes: int
    free_library_limit: int
    ai_model: str


# ── Helper ──

def _user_to_dict(u: User) -> dict:
    return {
        "id": u.id,
        "uid": u.uid,
        "nickname": u.nickname,
        "avatar_url": u.avatar_url,
        "email": u.email,
        "phone": u.phone,
        "role": u.role,
        "subscription_tier": u.subscription_tier,
        "subscription_expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
        "storage_used_bytes": u.storage_used_bytes or 0,
        "ai_calls_this_month": u.ai_calls_this_month or 0,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


# ── 用户管理 ──

@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="按昵称/邮箱搜索"),
    role: Optional[str] = Query(None, description="按角色筛选"),
    tier: Optional[str] = Query(None, description="按订阅等级筛选"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """用户列表（分页+搜索+筛选）"""
    q = db.query(User)

    if search:
        like = f"%{search}%"
        q = q.filter(
            (User.nickname.like(like)) | (User.email.like(like))
        )
    if role:
        q = q.filter(User.role == role)
    if tier:
        q = q.filter(User.subscription_tier == tier)

    total = q.count()
    offset = (page - 1) * page_size
    users = q.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    return {
        "items": [_user_to_dict(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """修改用户角色/订阅/封禁状态。
    不允许修改自己的角色。
    """
    if user_id == admin.id and body.role is not None:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")

    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.nickname is not None:
        u.nickname = body.nickname

    if body.role is not None:
        valid_roles = {"super_admin", "admin", "editor", "reader", "guest", "banned"}
        if body.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"无效角色，可选: {valid_roles}")
        # 不允许降级站长
        if user_id == 1 and body.role != "super_admin":
            raise HTTPException(status_code=400, detail="不能修改站长的角色")
        u.role = body.role

    if body.subscription_tier is not None:
        valid_tiers = {"free", "pro", "premium"}
        if body.subscription_tier not in valid_tiers:
            raise HTTPException(status_code=400, detail=f"无效订阅等级，可选: {valid_tiers}")
        u.subscription_tier = body.subscription_tier

    if body.is_banned is not None:
        if body.is_banned:
            u.role = "banned"
        elif u.role == "banned":
            u.role = "reader"  # 解封恢复为 reader

    if body.ai_calls_this_month is not None:
        u.ai_calls_this_month = body.ai_calls_this_month

    db.commit()
    db.refresh(u)
    logger.info("管理员 %d 更新了用户 %d: role=%s tier=%s", admin.id, user_id, u.role, u.subscription_tier)
    return _user_to_dict(u)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """删除用户。禁止删除自己和站长（uid=1）。"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if user_id == 1:
        raise HTTPException(status_code=400, detail="不能删除站长账号")

    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    nickname = u.nickname
    db.delete(u)
    db.commit()
    logger.info("管理员 %d 删除了用户 %d (%s)", admin.id, user_id, nickname)
    return {"ok": True, "message": f"用户「{nickname}」已删除"}


# ── 全局统计 ──

@router.get("/stats", response_model=StatsOut)
def get_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """全局统计：总用户数、总作品数、今日AI调用、总存储用量"""
    total_users = db.query(sqlfunc.count(User.id)).scalar() or 0
    total_artworks = db.query(sqlfunc.count(TubiAnalysis.id)).scalar() or 0
    total_libraries = 0  # Phase 3: artwork_libraries 表已废弃
    total_storage = db.query(sqlfunc.sum(User.storage_used_bytes)).scalar() or 0
    ai_today = db.query(sqlfunc.sum(User.ai_calls_this_month)).scalar() or 0

    return StatsOut(
        total_users=total_users,
        total_artworks=total_artworks,
        total_libraries=total_libraries,
        total_storage_bytes=total_storage,
        ai_calls_today=ai_today,
    )


# ── 订阅管理 ──

@router.get("/subscriptions")
def list_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tier: Optional[str] = Query(None, description="按订阅等级筛选"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """订阅列表（从 users 表查询订阅数据）"""
    q = db.query(User).filter(User.subscription_expires_at.isnot(None))

    if tier:
        q = q.filter(User.subscription_tier == tier)

    total = q.count()
    offset = (page - 1) * page_size
    users = q.order_by(User.subscription_expires_at.desc()).offset(offset).limit(page_size).all()

    items = []
    for u in users:
        items.append({
            "user_id": u.id,
            "nickname": u.nickname,
            "subscription_tier": u.subscription_tier,
            "subscription_expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/subscriptions")
def create_subscription(
    body: SubscriptionCreateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """手动为用户开通/续期订阅"""
    valid_tiers = {"free", "pro", "premium"}
    if body.tier not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"无效订阅等级，可选: {valid_tiers}")

    u = db.query(User).filter(User.id == body.user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    now = datetime.now(timezone.utc)
    # 如果已有未过期订阅，在现有到期时间基础上叠加
    if u.subscription_expires_at and u.subscription_expires_at > now:
        new_expires = u.subscription_expires_at + timedelta(days=body.duration_days)
    else:
        new_expires = now + timedelta(days=body.duration_days)

    u.subscription_tier = body.tier
    u.subscription_expires_at = new_expires
    db.commit()
    db.refresh(u)

    logger.info(
        "管理员 %d 为用户 %d 开通订阅 tier=%s expires=%s",
        admin.id, body.user_id, body.tier, new_expires.isoformat(),
    )
    return {
        "user_id": u.id,
        "nickname": u.nickname,
        "subscription_tier": u.subscription_tier,
        "subscription_expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
    }


# ── 系统配置 ──

@router.get("/config", response_model=ConfigOut)
def get_config(admin: User = Depends(require_admin_role)):
    """返回当前系统的配额与模型配置（供管理面板展示）"""
    return ConfigOut(
        free_ai_calls_per_month=settings.FREE_AI_CALLS_PER_MONTH,
        paid_ai_calls_per_month=settings.PAID_AI_CALLS_PER_MONTH,
        free_storage_bytes=settings.FREE_STORAGE_BYTES,
        paid_storage_bytes=settings.PAID_STORAGE_BYTES,
        free_library_limit=settings.FREE_LIBRARY_LIMIT,
        ai_model=settings.SILICONFLOW_MODEL or settings.DEEPSEEK_TEXT_MODEL or "deepseek-v4-flash",
    )


# ── 权限配置 ──

class PermissionsSaveIn(BaseModel):
    permissions: dict  # { "admin": [...], "editor": [...], "reader": [...] }


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    """获取所有非站长角色的权限配置"""
    rows = db.query(RolePermission).all()
    result = {"admin": [], "editor": [], "reader": []}
    for r in rows:
        if r.role in result:
            result[r.role].append(r.permission_key)
    return {"permissions": result, "all_keys": ALL_PERMISSION_KEYS}


@router.put("/permissions")
def save_permissions(
    body: PermissionsSaveIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    """批量保存权限配置（全量替换）"""
    valid_roles = {"admin", "editor", "reader"}
    for role, keys in body.permissions.items():
        if role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"无效角色: {role}")
        # 删除旧权限
        db.query(RolePermission).filter(RolePermission.role == role).delete()
        # 插入新权限
        for key in keys:
            if key not in ALL_PERMISSION_KEYS:
                raise HTTPException(status_code=400, detail=f"无效权限键: {key}")
            db.add(RolePermission(role=role, permission_key=key))
    db.commit()
    logger.info("管理员 %d 更新了角色权限配置", admin.id)
    return {"ok": True, "message": "权限配置已保存"}


@router.get("/my-permissions")
def my_permissions(perms: dict = Depends(get_user_permissions)):
    """返回当前登录用户的权限列表（供前端侧边栏渲染）"""
    return perms
