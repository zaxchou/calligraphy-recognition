"""
库协作者模型 — library_collaborators 表
Phase 2: 协作管理
"""
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func
from app.core.database import Base


class LibraryCollaborator(Base):
    __tablename__ = "library_collaborators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    library_id = Column(Integer, nullable=False, index=True, comment="作品库ID")
    user_id = Column(Integer, nullable=False, index=True, comment="协作者用户ID")
    role = Column(String(20), default="viewer", comment="角色: viewer/editor/maintainer")
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('library_id', 'user_id', name='uq_library_collab'),
    )
