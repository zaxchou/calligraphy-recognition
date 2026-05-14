from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wechat_openid = Column(String, unique=True, nullable=True, comment="微信 OpenID（手机登录后可空）")
    wechat_unionid = Column(String, nullable=True, comment="微信 UnionID")
    nickname = Column(String, nullable=True, comment="昵称")
    avatar_url = Column(String, nullable=True, comment="头像URL")
    email = Column(String, nullable=True, comment="邮箱")
    phone = Column(String, nullable=True, comment="手机号")
    password_hash = Column(String, nullable=True, comment="密码哈希（bcrypt/pbkdf2）")
    role = Column(String, default="reader", comment="角色: super_admin/admin/editor/reader/guest")
    subscription_tier = Column(String, default="free", comment="订阅等级: free/pro/premium")
    subscription_expires_at = Column(DateTime, nullable=True, comment="订阅到期时间")
    storage_used_bytes = Column(Integer, default=0, comment="已用存储(bytes)")
    ai_calls_this_month = Column(Integer, default=0, comment="本月AI调用数")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    artist_claims = relationship(
        "ArtistClaim", back_populates="user", lazy="dynamic",
        foreign_keys="ArtistClaim.user_id",
    )
