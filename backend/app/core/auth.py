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
