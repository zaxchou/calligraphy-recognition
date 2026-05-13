"""
JWT 安全模块 — 创建和解析 JWT Token

用于 Phase 1 多用户底座的认证中间件。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_access_token(user_id: int, role: str, tier: str) -> str:
    """
    创建 JWT access token。

    Args:
        user_id: 用户 ID
        role: 用户角色 (free_user/admin)
        tier: 订阅等级 (free/pro/premium)

    Returns:
        JWT token string
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)

    payload = {
        "sub": str(user_id),
        "role": role,
        "tier": tier,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码 JWT token，返回 payload 字典。

    Args:
        token: JWT token string

    Returns:
        payload dict 或 None（解码失败）
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT 解码失败: {e}")
        return None
