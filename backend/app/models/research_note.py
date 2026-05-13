"""
研究笔记模型 — research_notes 表
Phase 2: 作品研究笔记
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class ResearchNote(Base):
    __tablename__ = "research_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True, comment="作者用户ID")
    artwork_id = Column(Integer, nullable=False, index=True, comment="关联作品ID (tubi_analyses.id)")
    title = Column(String(255), nullable=True, comment="笔记标题")
    content = Column(Text, nullable=False, comment="笔记正文 (Markdown)")
    visibility = Column(String(20), default="private", comment="可见性: public/private")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
