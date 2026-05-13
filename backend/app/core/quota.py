"""
配额中间件 — FastAPI 依赖注入函数。

用法：
    from app.core.quota import check_ai_quota, check_storage_quota, check_library_quota

    @router.post("/endpoint")
    async def my_endpoint(user: User = Depends(get_current_user), _q = Depends(check_ai_quota)):
        ...

所有限额配置从 .env / Settings 读取，有合理默认值。
"""

import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()


async def check_ai_quota(user: User = Depends(get_current_user)):
    """检查 AI 调用配额。

    月初自动重置计数器（对比 user.updated_at 的月份）。
    admin / super_admin 不限次数。
    通过后调用次数 +1。
    超限时抛出 HTTP 429。
    """
    # admin 不限
    if user.role in ("admin", "super_admin"):
        return

    db = SessionLocal()
    try:
        # 重新加载 user（原对象可能 detached）
        u = db.query(User).filter(User.id == user.id).first()
        if not u:
            raise HTTPException(status_code=401, detail="用户不存在")

        # 月初自动重置
        now = datetime.now(timezone.utc)
        if u.updated_at:
            last_month = u.updated_at.month
            last_year = u.updated_at.year
            if last_month != now.month or last_year != now.year:
                u.ai_calls_this_month = 0

        # 配额检查
        if u.subscription_tier == "free":
            limit = settings.FREE_AI_CALLS_PER_MONTH
        else:
            limit = settings.PAID_AI_CALLS_PER_MONTH

        if u.ai_calls_this_month >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"本月 AI 调用次数已用完（{limit}次/月）。升级 Pro 可享 {settings.PAID_AI_CALLS_PER_MONTH} 次/月。",
            )

        # 计数 +1
        u.ai_calls_this_month += 1
        db.commit()
        logger.info(
            "用户 %d AI配额 %d/%d", u.id, u.ai_calls_this_month, limit,
        )
    finally:
        db.close()


async def check_storage_quota(
    user: User = Depends(get_current_user),
    additional_bytes: int = 0,
):
    """检查存储配额。

    调用方需自行计算 additional_bytes（即将新增的字节数），
    本函数检查 current_usage + additional_bytes 是否超限。
    admin / super_admin 不限存储。
    超限时抛出 HTTP 413。
    """
    if user.role in ("admin", "super_admin"):
        return

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user.id).first()
        if not u:
            return

        if u.subscription_tier == "free":
            limit = settings.FREE_STORAGE_BYTES
        else:
            limit = settings.PAID_STORAGE_BYTES

        projected = (u.storage_used_bytes or 0) + additional_bytes
        if projected > limit:
            free_gb = settings.FREE_STORAGE_BYTES / (1024**3)
            paid_gb = settings.PAID_STORAGE_BYTES / (1024**3)
            raise HTTPException(
                status_code=413,
                detail=f"存储空间不足。当前 {projected / (1024**2):.1f} MB，"
                       f"免费限额 {free_gb:.0f} GB，Pro 限额 {paid_gb:.0f} GB。",
            )
    finally:
        db.close()


async def check_library_quota(user: User = Depends(get_current_user)):
    """检查私有库数量配额。

    仅限免费用户（付费用户 / admin 不限）。
    超限时抛出 HTTP 403。
    """
    if user.role in ("admin", "super_admin"):
        return
    if user.subscription_tier != "free":
        return

    db = SessionLocal()
    try:
        from app.models.artwork_library import ArtworkLibrary

        count = (
            db.query(ArtworkLibrary)
            .filter(ArtworkLibrary.owner_id == user.id)
            .count()
        )
        if count >= settings.FREE_LIBRARY_LIMIT:
            raise HTTPException(
                status_code=403,
                detail=f"免费用户最多创建 {settings.FREE_LIBRARY_LIMIT} 个作品库。升级 Pro 可创建无限库。",
            )
    finally:
        db.close()
