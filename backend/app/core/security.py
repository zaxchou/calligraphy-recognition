"""
JWT 安全模块 — 创建/解析 JWT Token + 密码哈希

Phase 3: 新增 pbkdf2 密码哈希
"""
import hashlib
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Password hashing (PBKDF2) ──

def hash_password(password: str) -> str:
    """
    使用 PBKDF2-HMAC-SHA256 哈希密码。
    返回格式: pbkdf2:sha256:<iterations>$<salt_hex>$<hash_hex>
    """
    iterations = 600000
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2:sha256:{iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码是否匹配。
    支持格式: pbkdf2:sha256:<iterations>$<salt_hex>$<hash_hex>
    """
    try:
        algo_part, _, params = password_hash.partition("$")
        if algo_part.startswith("pbkdf2:"):
            parts = algo_part.split(":")
            if len(parts) < 3:
                return False
            iterations = int(parts[2])
            salt_hex, _, hash_hex = params.partition("$")
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return dk.hex() == hash_hex
        return False
    except Exception:
        return False


# ── JWT ──

def create_access_token(user_id: int, role: str, tier: str = "free") -> str:
    """
    创建 JWT access token。

    Args:
        user_id: 用户 ID
        role: 用户角色 (super_admin/admin/editor/reader/guest)
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
