from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, comment="姓名")
    alias = Column(String, default="", comment="字号")
    dynasty = Column(String, default="", comment="朝代")
    hometown = Column(String, default="", comment="籍贯")
    birth_year = Column(Integer, nullable=True, comment="出生年份")
    death_year = Column(Integer, nullable=True, comment="卒年")
    avatar_url = Column(String, default="", comment="头像URL")
    biography = Column(Text, default="", comment="生平简介")
    background = Column(String, default="", comment="背景简介（旧）")
    specialties = Column(String, default="", comment="专长（旧）")
    bio_events = Column(Text, default="[]", comment="生平时间线 JSON")
    art_school = Column(String, default="", comment="画派（逗号分隔）")
    masterpieces = Column(Text, default="[]", comment="代表作 JSON 数组")
    tags = Column(Text, default="[]", comment="标签 JSON 数组")
    baidu_url = Column(String, default="", comment="百度百科 URL")
    view_count = Column(Integer, default=0, comment="浏览量")
    featured = Column(Integer, default=0, comment="推荐标记 1推荐/0非推荐")
    enabled = Column(Integer, default=1, comment="启用状态")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
