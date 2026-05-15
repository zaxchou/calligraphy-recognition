"""站点全局设置 — key-value 表，管理员可在后台实时编辑。"""
from sqlalchemy import Column, String, DateTime, func
from app.core.database import Base


class SiteSetting(Base):
    __tablename__ = "site_settings"

    key = Column(String(64), primary_key=True, comment="设置键名")
    value = Column(String(512), nullable=True, comment="设置值")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
