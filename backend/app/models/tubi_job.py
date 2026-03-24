from sqlalchemy import Column, Integer, String, DateTime, func
from app.core.database import Base


class TubiJob(Base):
    __tablename__ = "tubi_jobs"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    last_error = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

