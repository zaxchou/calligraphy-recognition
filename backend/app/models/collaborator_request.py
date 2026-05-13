"""
协作者申请模型 — collaborator_requests 表
Phase 2: 加入作品库的申请
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class CollaboratorRequest(Base):
    __tablename__ = "collaborator_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    library_id = Column(Integer, nullable=False, index=True, comment="目标作品库ID")
    from_user_id = Column(Integer, nullable=False, comment="申请人用户ID")
    to_user_id = Column(Integer, nullable=False, comment="审核人（库主）用户ID")
    status = Column(String(20), default="pending", comment="状态: pending/approved/rejected")
    message = Column(Text, nullable=True, comment="申请留言")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
