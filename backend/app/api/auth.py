"""
认证 API — 手机验证码登录 + 密码登录 + 微信登录（兼容）

Phase 3: 废弃纯微信登录，新增手机号真实登录系统。
"""
import hashlib
import logging
import os
import time
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Depends, Query, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR, get_settings
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

# ── 开发模式验证码存储（内存）──
# 生产环境应使用 Redis
_verify_codes: dict = {}  # {phone: {"code": "123456", "expires_at": timestamp, "sent_at": timestamp}}


# ════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ════════════════════════════════════════════════════════════════

class SendCodeRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 11:
            raise ValueError("手机号格式不正确")
        return v


class RegisterRequest(BaseModel):
    phone: str
    code: str
    nickname: Optional[str] = None
    password: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 11:
            raise ValueError("手机号格式不正确")
        return v


class LoginCodeRequest(BaseModel):
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 11:
            raise ValueError("手机号格式不正确")
        return v


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


class WechatLoginRequest(BaseModel):
    code: str


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

def _generate_mock_openid(code: str) -> str:
    """Mock 模式下根据 code 生成一致的假 openid"""
    code_clean = code.replace("mock_", "")
    return "mock_openid_" + hashlib.md5(code_clean.encode()).hexdigest()[:16]


def _assign_uid(db: Session, user: User) -> None:
    """为新用户生成不可变 UID（8位数字，基于 10000000 + id）。"""
    if user.uid:
        return
    user.uid = str(10000000 + user.id)
    db.commit()


def _check_code(phone: str, code: str) -> bool:
    """验证手机验证码。开发模式：固定 "123456"。"""
    settings = get_settings()
    # 开发模式：固定验证码
    if settings.WECHAT_MOCK_MODE:
        if code == "123456":
            return True
        # 也允许查看内存中的验证码
        entry = _verify_codes.get(phone)
        if entry and entry["code"] == code and time.time() < entry["expires_at"]:
            return True
        return False

    # 生产模式：查 Redis / 短信服务
    entry = _verify_codes.get(phone)
    if not entry:
        return False
    if time.time() > entry["expires_at"]:
        del _verify_codes[phone]
        return False
    if entry["code"] != code:
        return False
    # 验证成功，清理
    del _verify_codes[phone]
    return True


def _can_send_code(phone: str) -> tuple[bool, Optional[int]]:
    """检查能否发送验证码。返回 (可以发送, 剩余等待秒数)。"""
    entry = _verify_codes.get(phone)
    if not entry:
        return True, None
    elapsed = time.time() - entry["sent_at"]
    if elapsed < 60:
        return False, int(60 - elapsed)
    return True, None


def _user_to_auth_response(user: User, token: str) -> dict:
    return {
        "token": token,
        "user_id": user.id,
        "uid": user.uid,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "phone": user.phone,
    }


# ════════════════════════════════════════════════════════════════
# Phone Auth Endpoints
# ════════════════════════════════════════════════════════════════

@router.post("/send-code")
async def send_code(req: SendCodeRequest):
    """
    发送手机验证码。

    开发模式（WECHAT_MOCK_MODE=true）：
    - 接受任意手机号，不真发短信
    - 验证码固定为 "123456"
    - 60秒内同一手机号不可重复发送

    生产模式：
    - 调用短信服务发送验证码
    """
    phone = req.phone.strip()

    can_send, wait_secs = _can_send_code(phone)
    if not can_send:
        raise HTTPException(
            status_code=429,
            detail=f"发送过于频繁，请 {wait_secs} 秒后再试"
        )

    settings = get_settings()
    if settings.WECHAT_MOCK_MODE:
        code = "123456"
        logger.info(f"[Mock] 验证码已发送到 {phone}，验证码: {code}")
    else:
        # 生产模式：生成随机6位验证码 + 调用短信服务
        import random
        code = "".join(str(random.randint(0, 9)) for _ in range(6))
        logger.info(f"[PROD] 验证码: {phone} -> {code}")
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
    手机号注册。
    - 验证码校验 → 创建用户（role=reader）→ 返回JWT
    - 可选设置密码
    """
    phone = req.phone.strip()

    if not _check_code(phone, req.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    # 检查手机号是否已注册
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        raise HTTPException(status_code=409, detail="该手机号已注册")

    user = User(
        phone=phone,
        nickname=req.nickname or f"用户{phone[-4:]}",
        role="reader",
        password_hash=hash_password(req.password) if req.password else None,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        _assign_uid(db, user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="注册失败，请重试")

    token = create_access_token(user_id=user.id, role=user.role)
    logger.info(f"新用户注册: id={user.id}, uid={user.uid}, phone={phone}")

    return {
        **{"token": token, "user_id": user.id, "nickname": user.nickname,
           "avatar_url": user.avatar_url, "role": user.role, "phone": user.phone,
           "score": user.score or 0},
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


# ════════════════════════════════════════════════════════════════
# Wechat Login (兼容保留)
# ════════════════════════════════════════════════════════════════

@router.post("/wechat-login")
async def wechat_login(req: WechatLoginRequest, db: Session = Depends(get_db)):
    """
    微信小程序登录接口（兼容保留）。

    接收微信 code，调微信 API 换 openid，
    创建新用户或查找已有用户，返回 JWT token。

    开发阶段：设置 WECHAT_MOCK_MODE=true 可使用 mock_<any_string> 作为 code。
    """
    code = req.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="code 不能为空")

    settings = get_settings()

    if settings.WECHAT_MOCK_MODE:
        if not code.startswith("mock_"):
            raise HTTPException(
                status_code=400,
                detail="Mock 模式下请使用 mock_<任意字符串> 作为 code"
            )
        openid = _generate_mock_openid(code)
        unionid = None
        logger.info(f"[Mock] 微信登录: code={code[:20]}... -> openid={openid}")
    else:
        if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
            raise HTTPException(
                status_code=503,
                detail="微信小程序配置未就绪（缺少 WECHAT_APP_ID/WECHAT_APP_SECRET）"
            )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.weixin.qq.com/sns/jscode2session",
                    params={
                        "appid": settings.WECHAT_APP_ID,
                        "secret": settings.WECHAT_APP_SECRET,
                        "js_code": code,
                        "grant_type": "authorization_code",
                    },
                )
                data = resp.json()
        except Exception as e:
            logger.error(f"微信 API 调用失败: {e}")
            raise HTTPException(status_code=503, detail="微信服务暂时不可用，请稍后重试")

        if "errcode" in data and data["errcode"] != 0:
            logger.warning(f"微信登录失败: {data}")
            errcode = data.get("errcode", -1)
            if errcode == 40029:
                raise HTTPException(status_code=400, detail="code 无效或已过期")
            elif errcode == 45011:
                raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
            else:
                raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg', '未知错误')}")

        openid = data.get("openid")
        unionid = data.get("unionid")
        if not openid:
            raise HTTPException(status_code=400, detail="无法获取微信 openid")

    # 查找或创建用户
    user = db.query(User).filter(User.wechat_openid == openid).first()
    is_new_user = False

    if not user:
        user = User(
            wechat_openid=openid,
            wechat_unionid=unionid,
            role="reader",
            subscription_tier="free",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            _assign_uid(db, user)
            is_new_user = True
            logger.info(f"新用户创建: id={user.id}, uid={user.uid}, openid={openid[:16]}...")
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.wechat_openid == openid).first()
            if not user:
                raise HTTPException(status_code=500, detail="用户创建失败，请重试")
        if unionid and not user.wechat_unionid:
            user.wechat_unionid = unionid
            db.commit()
            db.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)

    return {
        "token": token,
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "is_new_user": is_new_user,
        "role": user.role,
        "phone": user.phone,
    }


# ════════════════════════════════════════════════════════════════
# User Profile
# ════════════════════════════════════════════════════════════════

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
