"""
著录引用模型 — literature_references 表
Phase 2: 作品著录信息
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, func
from app.core.database import Base


class LiteratureReference(Base):
    __tablename__ = "literature_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artwork_id = Column(Integer, nullable=False, index=True, comment="关联作品ID (tubi_analyses.id)")
    reference_type = Column(String(30), default="citation", comment="著录类型: citation/catalogue/exhibition/thesis")
    title = Column(String(500), nullable=True, comment="文献标题")
    author = Column(String(200), nullable=True, comment="文献作者")
    year = Column(Integer, nullable=True, comment="出版年份")
    publisher = Column(String(200), nullable=True, comment="出版社")
    page = Column(String(100), nullable=True, comment="页码")
    notes = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
