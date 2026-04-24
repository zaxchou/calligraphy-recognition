from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class TubiJob(Base):
    __tablename__ = "tubi_jobs"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    mode = Column(String(30), nullable=True, default="analyze", comment="分析模式：analyze/analyze_text_only/manual")
    last_error = Column(String(500))
    error_code = Column(String(50), comment="结构化错误码：REDIS_UNAVAILABLE/VL_TIMEOUT/OCR_FAILED/WORKER_CRASHED等")
    last_error_detail = Column(Text, comment="详细错误信息（堆栈等）")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

