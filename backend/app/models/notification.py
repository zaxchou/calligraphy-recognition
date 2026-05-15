"""
通知模型 — notifications 表
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True, comment="接收者用户ID")
    type = Column(String(30), nullable=False, comment="通知类型: cr_approved/cr_rejected/cr_pending/system")
    title = Column(String(255), nullable=False, comment="通知标题")
    body = Column(Text, nullable=True, comment="通知正文")
    reference_type = Column(String(30), nullable=True, comment="关联类型: change_request/artwork/system")
    reference_id = Column(Integer, nullable=True, comment="关联ID")
    is_read = Column(Integer, default=0, comment="是否已读: 0/1")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
