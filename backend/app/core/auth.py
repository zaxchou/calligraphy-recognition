"""
管理员鉴权依赖。

用法：
    from app.core.auth import require_admin

    @router.delete("/something")
    async def delete_something(db=Depends(get_db), admin=Depends(require_admin)):
        ...

行为：
    - ADMIN_API_KEY 未设置（空字串）→ 无条件放行，向后兼容
    - ADMIN_API_KEY 已设置 → 请求必须带 X-Admin-Key header 匹配才放行
"""

import logging
from fastapi import Header, HTTPException, Depends
from typing import Optional

logger = logging.getLogger(__name__)


async def require_admin(
    x_admin_key: Optional[str] = Header(None),
) -> bool:
    """如果配置了 ADMIN_API_KEY，则校验 X-Admin-Key header。

    当 ADMIN_API_KEY 为空时（默认），所有请求放行。
    """
    # 延迟导入避免启动时的循环依赖
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


async def require_admin_role(user: "User" = Depends(get_current_user)):
    """基于 JWT 角色的管理员鉴权依赖。

    用法：
        @router.get("/admin/something")
        async def admin_only(admin: User = Depends(require_admin_role)):
            ...

    行为：
        - 用户未登录 → 401（由 get_current_user 抛出）
        - 用户角色不是 admin 或 super_admin → 403
        - 通过则返回 User 对象
    """
    if user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


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

    # 提取 Bearer token
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
        # NOTE: User 对象在 session 关闭后 detached。
        # Phase 2+ 若 User 加了 relationship 字段，需改用 Depends(get_db) 注入共享 session。
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
                result["my_library_count"] = ...
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
