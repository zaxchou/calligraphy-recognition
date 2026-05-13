"""
认证 API — 微信登录、Token 刷新

Phase 1 多用户底座的核心入口。
"""
import hashlib
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class WechatLoginRequest(BaseModel):
    code: str


class WechatLoginResponse(BaseModel):
    token: str
    user_id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    is_new_user: bool = False


class TokenVerifyResponse(BaseModel):
    valid: bool
    user_id: Optional[int] = None
    role: Optional[str] = None


def _generate_mock_openid(code: str) -> str:
    """Mock 模式下根据 code 生成一致的假 openid"""
    code_clean = code.replace("mock_", "")
    return "mock_openid_" + hashlib.md5(code_clean.encode()).hexdigest()[:16]


@router.post("/wechat-login", response_model=WechatLoginResponse)
async def wechat_login(req: WechatLoginRequest, db: Session = Depends(get_db)):
    """
    微信小程序登录接口。

    接收微信 code，调微信 API 换 openid，
    创建新用户或查找已有用户，返回 JWT token。

    开发阶段：设置 WECHAT_MOCK_MODE=true 可使用 mock_<any_string> 作为 code。
    """
    code = req.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="code 不能为空")

    settings = get_settings()

    if settings.WECHAT_MOCK_MODE:
        # Mock 模式：接受 mock_ 开头的 code
        if not code.startswith("mock_"):
            raise HTTPException(
                status_code=400,
                detail="Mock 模式下请使用 mock_<任意字符串> 作为 code"
            )
        openid = _generate_mock_openid(code)
        unionid = None
        logger.info(f"[Mock] 微信登录: code={code[:20]}... -> openid={openid}")
    else:
        # 真实微信 API 调用
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
            role="free_user",
            subscription_tier="free",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            is_new_user = True
            logger.info(f"新用户创建: id={user.id}, openid={openid[:16]}...")
        except Exception:
            db.rollback()
            # 竞态条件：另一个请求已经创建了同样的用户
            user = db.query(User).filter(User.wechat_openid == openid).first()
            if not user:
                raise HTTPException(status_code=500, detail="用户创建失败，请重试")
            logger.info(f"竞态解决: 使用已存在的用户 id={user.id}")
        # 更新 unionid（如果之前没有）
        if unionid and not user.wechat_unionid:
            user.wechat_unionid = unionid
            db.commit()
            db.refresh(user)

    # 生成 JWT
    token = create_access_token(
        user_id=user.id,
        role=user.role,
        tier=user.subscription_tier,
    )

    return WechatLoginResponse(
        token=token,
        user_id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        is_new_user=is_new_user,
    )
