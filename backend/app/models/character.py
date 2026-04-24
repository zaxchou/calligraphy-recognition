from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, func, Float
from sqlalchemy.orm import relationship
from app.core.database import Base


class Character(Base):
    __tablename__ = "characters"
    
    id = Column(Integer, primary_key=True, index=True)
    stele_id = Column(Integer, ForeignKey("steles.id"), nullable=False)
    character = Column(String(10), nullable=False, comment="汉字")
    unicode = Column(String(10), comment="Unicode编码")
    image_path = Column(String(255), comment="字形图片路径")
    feature_vector = Column(JSON, comment="特征向量（列表存储）")
    stroke_count = Column(Integer, comment="笔画数")
    bounding_box = Column(JSON, comment="字形边界框信息")
    meta_info = Column(JSON, comment="其他元数据")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    stele = relationship("Stele", back_populates="characters")
