"""
认证 API — 手机验证码登录 + 密码登录

Phase 3: 废弃纯微信登录，新增手机号真实登录系统。
"""
import logging
import os
import secrets
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Depends, Request, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

# ── 开发模式验证码存储（内存）──
# 生产环境应使用 Redis
_verify_codes: dict = {}  # {phone: {"code": "123456", "expires_at": timestamp, "sent_at": timestamp}}


def _cleanup_expired_codes():
    """清理过期验证码，每次发送/验证时调用"""
    now = time.time()
    expired = [k for k, v in _verify_codes.items() if now > v["expires_at"]]
    for k in expired:
        del _verify_codes[k]


# ════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ════════════════════════════════════════════════════════════════

import re
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")

def _validate_phone(v: str) -> str:
    """公共手机号验证"""
    v = v.strip()
    if not _PHONE_RE.match(v):
        raise ValueError("手机号格式不正确")
    return v


class SendCodeRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)


class RegisterRequest(BaseModel):
    # 方式一：手机号注册（需要验证码）
    phone: Optional[str] = None
    code: Optional[str] = None
    # 方式二：用户名注册（不需要验证码）
    username: Optional[str] = None
    # 通用字段
    nickname: Optional[str] = None
    password: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_phone(v)
        return v


class LoginCodeRequest(BaseModel):
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)


class LoginPasswordRequest(BaseModel):
    account: str
    password: str

    @field_validator("account")
    @classmethod
    def validate_account(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("请输入手机号或昵称")
        return v


class SetPasswordRequest(BaseModel):
    password: str
    old_password: Optional[str] = None  # 修改密码时需要旧密码

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少6位")
        return v


class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user_id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    phone: Optional[str] = None


# ════════════════════════════════════════════════════════════════
# Helper
# ════════════════════════════════════════════════════════════════

def _assign_uid(db: Session, user: User) -> None:
    """为新用户生成不可变 UID（8位数字，基于 10000000 + id）。"""
    if user.uid:
        return
    user.uid = str(10000000 + user.id)
    db.commit()


def _check_code(phone: str, code: str) -> bool:
    """验证手机验证码（原子 pop 避免并发重放）。"""
    _cleanup_expired_codes()
    entry = _verify_codes.pop(phone, None)
    if not entry:
        return False
    if entry["code"] != code:
        # 验证码错误，放回去（允许重试）
        _verify_codes[phone] = entry
        return False
    return True


def _can_send_code(phone: str) -> tuple[bool, Optional[int]]:
    """检查能否发送验证码。返回 (可以发送, 剩余等待秒数)。"""
    _cleanup_expired_codes()
    entry = _verify_codes.get(phone)
    if not entry:
        return True, None
    elapsed = time.time() - entry["sent_at"]
    if elapsed < 60:
        return False, int(60 - elapsed)
    return True, None



# ════════════════════════════════════════════════════════════════
# Phone Auth Endpoints
# ════════════════════════════════════════════════════════════════

@router.post("/send-code")
async def send_code(req: SendCodeRequest):
    """
    发送手机验证码。

    生成并发送手机验证码（60秒内同一手机号不可重复发送）。
    TODO: 当前无真实短信服务，验证码仅存内存，接入短信服务商后注册/验证码登录才可用。
    """
    phone = req.phone.strip()

    can_send, wait_secs = _can_send_code(phone)
    if not can_send:
        raise HTTPException(
            status_code=429,
            detail=f"发送过于频繁，请 {wait_secs} 秒后再试"
        )

    # 生成随机6位验证码 + 调用短信服务（验证码不得写入日志）
    code = "".join(str(secrets.randbelow(10)) for _ in range(6))
    logger.info(f"[PROD] 验证码已发送至 {phone}")
    # TODO: 接入真实短信服务（阿里云/腾讯云）

    # 存储验证码（10分钟有效期）
    now = time.time()
    _verify_codes[phone] = {
        "code": code,
        "sent_at": now,
        "expires_at": now + 600,
    }

    return {"success": True, "message": "验证码已发送"}


@router.post("/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    注册。支持两种方式：
    - 方式一：手机号 + 验证码注册
    - 方式二：用户名 + 密码注册（不需要验证码）
    """
    # 判断注册方式
    if req.phone:
        # 手机号注册：需要验证码
        phone = req.phone.strip()
        if not req.code or not _check_code(phone, req.code):
            raise HTTPException(status_code=400, detail="验证码错误或已过期")
        existing = db.query(User).filter(User.phone == phone).first()
        if existing:
            raise HTTPException(status_code=409, detail="该手机号已注册")
        user = User(
            phone=phone,
            nickname=req.nickname or f"用户{phone[-4:]}",
            role="reader",
            password_hash=hash_password(req.password) if req.password else None,
        )
    elif req.username:
        # 用户名注册：需要密码
        username = req.username.strip()
        if len(username) < 2:
            raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
        if not req.password or len(req.password) < 6:
            raise HTTPException(status_code=400, detail="密码至少 6 位")
        existing = db.query(User).filter(User.nickname == username).first()
        if existing:
            raise HTTPException(status_code=409, detail="该用户名已注册")
        user = User(
            nickname=username,
            role="reader",
            password_hash=hash_password(req.password),
        )
    else:
        raise HTTPException(status_code=400, detail="请提供手机号或用户名")

    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        _assign_uid(db, user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="注册失败，请重试")

    token = create_access_token(user_id=user.id, role=user.role)
    logger.info(f"新用户注册: id={user.id}, uid={user.uid}, nickname={user.nickname}")

    return {
        "token": token, "user_id": user.id, "nickname": user.nickname,
        "avatar_url": user.avatar_url, "role": user.role, "phone": user.phone,
        "score": user.score or 0,
        "is_new_user": True,
    }


@router.post("/login")
async def login_by_code(req: LoginCodeRequest, db: Session = Depends(get_db)):
    """
    验证码登录。
    - 用户存在 → 校验验证码 → 返回JWT
    - 用户不存在 → 校验验证码 → 自动注册为reader → 返回JWT
    """
    phone = req.phone.strip()

    if not _check_code(phone, req.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    user = db.query(User).filter(User.phone == phone).first()
    is_new_user = False

    if not user:
        # 自动注册
        user = User(
            phone=phone,
            nickname=f"用户{phone[-4:]}",
            role="reader",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            _assign_uid(db, user)
            is_new_user = True
            logger.info(f"自动注册新用户: id={user.id}, uid={user.uid}, phone={phone}")
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.phone == phone).first()
            if not user:
                raise HTTPException(status_code=500, detail="登录失败，请重试")

    token = create_access_token(user_id=user.id, role=user.role)
    return {
        **{"token": token, "user_id": user.id, "nickname": user.nickname,
           "avatar_url": user.avatar_url, "role": user.role, "phone": user.phone,
           "score": user.score or 0},
        "is_new_user": is_new_user,
    }


@router.post("/login-password")
async def login_by_password(req: LoginPasswordRequest, db: Session = Depends(get_db)):
    """
    密码登录。
    - 支持 UID / 手机号 / 邮箱 / 昵称 + 密码校验 → 返回JWT
    - 未设置密码 → 提示先用验证码登录后设置密码
    """
    account = req.account.strip()

    # 依次尝试：UID → 手机号 → 邮箱 → 昵称
    user = None
    for field, value in [("uid", account), ("phone", account), ("email", account), ("nickname", account)]:
        user = db.query(User).filter(getattr(User, field) == value).first()
        if user:
            break

    if not user:
        raise HTTPException(status_code=401, detail="账号未注册，请先注册")

    if not user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="未设置密码，请使用验证码登录后在个人中心设置密码"
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="密码错误")

    token = create_access_token(user_id=user.id, role=user.role)
    return {
        "token": token, "user_id": user.id, "nickname": user.nickname,
        "avatar_url": user.avatar_url, "role": user.role, "phone": user.phone,
        "score": user.score or 0,
    }


@router.get("/profile")
async def get_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取当前用户信息"""
    from app.models.artist_claim import ArtistClaim
    claims = db.query(ArtistClaim).filter(
        ArtistClaim.user_id == user.id,
        ArtistClaim.status == "approved",
    ).all()
    return {
        "user_id": user.id,
        "uid": user.uid,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "score": user.score or 0,
        "has_password": bool(user.password_hash),
        "has_wechat": bool(user.wechat_openid),
        "nickname_changed_at": user.nickname_changed_at.isoformat() if user.nickname_changed_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "claimed_artists": [c.artist_name for c in claims],
    }


@router.put("/profile")
async def update_profile(
    req: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新个人信息"""
    user = db.merge(user)  # 重新挂载到当前 session（get_current_user 的 session 已关闭）
    if req.nickname is not None:
        # 昵称唯一性检测
        dup = db.query(User).filter(
            User.nickname == req.nickname,
            User.id != user.id,
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail="该昵称已被使用")
        # 一年内只能改一次（管理员跳过）
        if user.nickname_changed_at and user.role not in ("super_admin", "admin"):
            from datetime import datetime, timedelta, timezone
            one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
            if user.nickname_changed_at > one_year_ago:
                raise HTTPException(status_code=400, detail="昵称每年只能修改一次")
        if req.nickname != user.nickname:
            user.nickname_changed_at = datetime.now(timezone.utc)
        user.nickname = req.nickname
    if req.avatar_url is not None:
        user.avatar_url = req.avatar_url
    if req.email is not None:
        user.email = req.email
    if req.phone is not None:
        # 检查手机号是否已被其他用户使用
        if req.phone:
            existing = db.query(User).filter(User.phone == req.phone, User.id != user.id).first()
            if existing:
                raise HTTPException(status_code=409, detail="该手机号已被其他用户使用")
        user.phone = req.phone
    db.commit()
    db.refresh(user)
    return {"success": True, "message": "个人信息已更新"}


@router.put("/password")
async def set_password(
    req: SetPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """设置或修改密码"""
    user = db.merge(user)  # 重新挂载到当前 session
    if user.password_hash:
        # 已有密码，需要验证旧密码
        if not req.old_password:
            raise HTTPException(status_code=400, detail="请提供旧密码")
        if not verify_password(req.old_password, user.password_hash):
            raise HTTPException(status_code=401, detail="旧密码错误")

    user.password_hash = hash_password(req.password)
    db.commit()
    return {"success": True, "message": "密码设置成功"}


# ════════════════════════════════════════════════════════════════
# Avatar Upload
# ════════════════════════════════════════════════════════════════

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传用户头像"""
    user = db.merge(user)  # 重新挂载到当前 session
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WebP/GIF 格式")

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="头像文件不能超过 2MB")

    # 保存到 data/avatars/
    avatar_dir = os.path.join(DATA_DIR, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(avatar_dir, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    # 更新用户头像 URL
    avatar_url = f"/static/avatars/{filename}"
    user.avatar_url = avatar_url
    db.commit()

    logger.info(f"用户 {user.id} 更新头像: {avatar_url}")
    return {"success": True, "avatar_url": avatar_url}
