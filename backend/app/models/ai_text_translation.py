from sqlalchemy import Column, Integer, Text, DateTime, String, func

from app.core.database import Base


class AiTextTranslation(Base):
    """AI 分析内容的中文→英文翻译缓存（按原文精确匹配）。

    由 backfill_ai_translations.py 离线回填；读接口在 Accept-Language: en 时
    用它替换响应 JSON 里的中文文本。"""
    __tablename__ = "ai_text_translations"

    id = Column(Integer, primary_key=True, index=True)
    zh = Column(Text, nullable=False, unique=True, index=True, comment="原文（中文）")
    en = Column(Text, nullable=False, comment="英文译文")
    source = Column(String(50), default="llm", comment="来源：llm/manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
