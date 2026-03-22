from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Stele(Base):
    __tablename__ = "steles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="碑帖名称")
    dynasty = Column(String(50), comment="朝代")
    calligrapher = Column(String(100), comment="书法家")
    style = Column(String(50), comment="字体风格（楷/行/草/隶/篆）")
    description = Column(Text, comment="碑帖简介")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    characters = relationship("Character", back_populates="stele")
