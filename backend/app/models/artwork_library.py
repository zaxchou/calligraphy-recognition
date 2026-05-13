"""
作品库模型 — artwork_libraries 表
Phase 2: 作品库产品线核心表
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class ArtworkLibrary(Base):
    __tablename__ = "artwork_libraries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="作品库名称")
    artist_name = Column(String(255), nullable=True, comment="画家名称")
    description = Column(Text, nullable=True, comment="作品库描述")
    owner_id = Column(Integer, nullable=False, index=True, comment="创建者用户ID")
    visibility = Column(String(20), default="private", comment="可见性: public/private")
    artwork_count = Column(Integer, default=0, comment="作品数量")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
