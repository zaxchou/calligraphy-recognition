"""
鉴权依赖 — JWT 角色鉴权 + 画家属地检查。

Phase 3: 5级角色系统 — super_admin / admin / editor / reader / guest

用法：
    from app.core.auth import require_super_admin, require_admin, require_editor

    @router.delete("/something")
    async def delete_something(db=Depends(get_db), admin=Depends(require_admin)):
        ...

    # 画家属地访问控制
    @router.put("/artwork/{id}")
    async def update_artwork(id: int, db=Depends(get_db),
                             user=Depends(require_artist_access("李鱓"))):
        ...
"""

import logging
from typing import Optional, Callable

from fastapi import Header, HTTPException, Depends

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# Legacy: Admin API Key (过渡兼容)
# ════════════════════════════════════════════════════════════════

async def require_admin_key(
    x_admin_key: Optional[str] = Header(None),
) -> bool:
    """如果配置了 ADMIN_API_KEY，则校验 X-Admin-Key header。

    当 ADMIN_API_KEY 为空时（默认），所有请求放行。
    此依赖保留用于过渡期，未来全部迁移到 JWT 角色鉴权。
    """
    from app.core.config import get_settings
    settings = get_settings()
    admin_key = settings.ADMIN_API_KEY

    if not admin_key:
        return True

    if not x_admin_key:
        logger.warning("管理操作被拒绝：缺少 X-Admin-Key header")
        raise HTTPException(status_code=403, detail="需要管理员权限")

    if x_admin_key.strip() != admin_key:
        logger.warning("管理操作被拒绝：X-Admin-Key 不匹配")
        raise HTTPException(status_code=403, detail="管理员密钥错误")

    return True


# Backward-compat alias
require_admin = require_admin_key


# ════════════════════════════════════════════════════════════════
# Core: get_current_user / get_optional_user
# ════════════════════════════════════════════════════════════════

async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> "User":
    """必选鉴权依赖 — 必须携带有效 JWT Token。

    用法：
        @router.get("/me")
        async def my_profile(user: User = Depends(get_current_user)):
            ...

    行为：
        - 无 Authorization header → 401
        - Token 无效或过期 → 401
        - Token 有效 → 返回 User 对象
    """
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.core.security import decode_access_token
    from app.models.user import User as UserModel

    if not authorization:
        raise HTTPException(status_code=401, detail="请先登录")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="认证格式错误，请使用 Bearer token")

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Token 无效")

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Token 无效")

    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    finally:
        db.close()


async def get_optional_user(
    authorization: Optional[str] = Header(None),
) -> Optional["User"]:
    """可选鉴权依赖 — 有 Token 就解析，没有就返回 None。

    用于「单接口双模式」：无 Token 返回公共数据，有 Token 额外返回私有数据。

    用法：
        @router.get("/public-items")
        async def items(user: Optional[User] = Depends(get_optional_user)):
            result = public_data
            if user:
                result["my_data"] = ...
            return result

    行为：
        - 无 Authorization header → 返回 None
        - Token 无效/过期 → 返回 None（静默降级，不报错）
        - Token 有效 → 返回 User 对象
    """
    from app.core.database import SessionLocal
    from app.core.security import decode_access_token
    from app.models.user import User as UserModel

    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    payload = decode_access_token(token)
    if payload is None:
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return None

    db = SessionLocal()
    try:
        return db.query(UserModel).filter(UserModel.id == user_id).first()
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════
# Role-based dependencies
# ════════════════════════════════════════════════════════════════

async def require_super_admin(user: "User" = Depends(get_current_user)):
    """站长权限 — 仅 super_admin 可通过。

    用法：
        @router.delete("/system/purge")
        async def purge(admin: User = Depends(require_super_admin)):
            ...
    """
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="需要站长权限")
    return user


async def require_admin_role(user: "User" = Depends(get_current_user)):
    """副站长及以上权限 — super_admin 或 admin 可通过。

    用法：
        @router.get("/admin/dashboard")
        async def dashboard(admin: User = Depends(require_admin_role)):
            ...
    """
    if user.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def require_editor(user: "User" = Depends(get_current_user)):
    """编者及以上权限 — super_admin / admin / editor 可通过。

    用法：
        @router.post("/artworks/upload")
        async def upload(editor: User = Depends(require_editor)):
            ...
    """
    if user.role not in ("super_admin", "admin", "editor"):
        raise HTTPException(status_code=403, detail="需要编者权限")
    return user


# ════════════════════════════════════════════════════════════════
# Granular permission check
# ════════════════════════════════════════════════════════════════

ALL_PERMISSION_KEYS = [
    "content.verify", "content.annotate", "content.upload", "content.batch",
    "metadata.dimensions", "metadata.seals", "metadata.albums",
    "metadata.strips", "metadata.tags",
    "knowledge.artist_info", "knowledge.artist_rules",
    "tools.dedup",
    "system.dashboard", "system.users", "system.permissions", "system.config",
]

PERMISSION_CATEGORIES = {
    "内容管理": ["content.verify", "content.annotate", "content.upload", "content.batch"],
    "元数据管理": ["metadata.dimensions", "metadata.seals", "metadata.albums", "metadata.strips", "metadata.tags"],
    "知识管理": ["knowledge.artist_info", "knowledge.artist_rules"],
    "工具": ["tools.dedup"],
    "系统管理": ["system.dashboard", "system.users", "system.permissions", "system.config"],
}

PERMISSION_LABELS = {
    "content.verify": "题跋校对",
    "content.annotate": "标注图校对",
    "content.upload": "作品上传",
    "content.batch": "批量操作",
    "metadata.dimensions": "尺寸录入",
    "metadata.seals": "印章管理",
    "metadata.albums": "册页管理",
    "metadata.strips": "条屏管理",
    "metadata.tags": "标签管理",
    "knowledge.artist_info": "作者信息",
    "knowledge.artist_rules": "画家规则",
    "tools.dedup": "作品查重",
    "system.dashboard": "系统概览",
    "system.users": "用户管理",
    "system.permissions": "权限配置",
    "system.config": "系统配置",
}


def require_permission(permission_key: str) -> Callable:
    """
    细粒度权限检查。
    super_admin → 直接通过
    其他角色 → 查 role_permissions 表
    """
    from app.core.database import SessionLocal
    from app.models.role_permission import RolePermission
    from app.models.user import User as UserModel

    async def _check(user: UserModel = Depends(get_current_user)) -> UserModel:
        if user.role == "super_admin":
            return user
        db = SessionLocal()
        try:
            has = db.query(RolePermission).filter(
                RolePermission.role == user.role,
                RolePermission.permission_key == permission_key,
            ).first()
            if not has:
                raise HTTPException(status_code=403, detail="无此操作权限")
            return user
        finally:
            db.close()
    return _check


async def get_user_permissions(user: "User" = Depends(get_current_user)):
    """返回当前用户的所有权限键列表。用于前端侧边栏渲染。"""
    from app.core.database import SessionLocal
    from app.models.role_permission import RolePermission
    from app.models.user import User as UserModel

    if user.role == "super_admin":
        return {"role": user.role, "permissions": list(ALL_PERMISSION_KEYS)}

    db = SessionLocal()
    try:
        rows = db.query(RolePermission.permission_key).filter(
            RolePermission.role == user.role,
        ).all()
        return {"role": user.role, "permissions": [r[0] for r in rows]}
    finally:
        db.close()


def require_artist_access(artist_name: str) -> Callable:
    """
    画家属地访问控制 — 返回一个 FastAPI 依赖。

    规则：
    - super_admin / admin / editor → 直接通过（editor 默认可维护任何画家）
    - reader → 检查 artist_claims 是否有该画家的 approved 认领 → 通过 / 403

    用法：
        @router.put("/image-info/{image_id}")
        async def update(image_id: int,
                         db: Session = Depends(get_db),
                         user: User = Depends(require_artist_access("李鱓"))):
            ...
    """
    from app.core.database import SessionLocal
    from app.models.artist_claim import ArtistClaim
    from app.models.user import User as UserModel

    async def _check(
        db_user: UserModel = Depends(get_current_user),
    ) -> UserModel:
        # super_admin / admin / editor → 全权通过
        if db_user.role in ("super_admin", "admin", "editor"):
            return db_user

        # reader → 检查是否有该画家的 approved 认领
        db = SessionLocal()
        try:
            claim = db.query(ArtistClaim).filter(
                ArtistClaim.user_id == db_user.id,
                ArtistClaim.artist_name == artist_name,
                ArtistClaim.status == "approved",
            ).first()
            if claim:
                return db_user
        finally:
            db.close()
        raise HTTPException(status_code=403, detail=f"您未认领画家「{artist_name}」，无权操作")

    return _check
