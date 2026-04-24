from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, func, Float
from app.core.database import Base


class RecognitionLog(Base):
    __tablename__ = "recognition_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, comment="用户ID")
    uploaded_image_path = Column(String(255), comment="上传图片路径")
    recognized_character = Column(String(10), comment="识别的汉字")
    matched_stele_id = Column(Integer, ForeignKey("steles.id"))
    similarity_score = Column(Float, comment="相似度分数（0-100）")
    top_matches = Column(JSON, comment="前N个匹配结果")
    processing_time_ms = Column(Integer, comment="处理耗时")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
