from sqlalchemy import Column, Integer, String, DateTime, func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wechat_openid = Column(String, unique=True, nullable=False, comment="微信 OpenID")
    wechat_unionid = Column(String, nullable=True, comment="微信 UnionID")
    nickname = Column(String, nullable=True, comment="微信昵称")
    avatar_url = Column(String, nullable=True, comment="微信头像URL")
    email = Column(String, nullable=True, comment="邮箱")
    phone = Column(String, nullable=True, comment="手机号")
    role = Column(String, default="free_user", comment="角色: free_user/admin")
    subscription_tier = Column(String, default="free", comment="订阅等级: free/pro/premium")
    subscription_expires_at = Column(DateTime, nullable=True, comment="订阅到期时间")
    storage_used_bytes = Column(Integer, default=0, comment="已用存储(bytes)")
    ai_calls_this_month = Column(Integer, default=0, comment="本月AI调用数")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
