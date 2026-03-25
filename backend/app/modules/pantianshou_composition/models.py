from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text

from app.core.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class CompositionJob(Base):
    __tablename__ = "composition_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(64), default="queued")
    stage_text: Mapped[str] = mapped_column(String(64), default="等待处理")
    message: Mapped[str] = mapped_column(String(255), default="")

    eta_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eta_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    queue_eta_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    upload_path: Mapped[str] = mapped_column(String(512))
    original_url: Mapped[str] = mapped_column(String(512))

    report_json_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    overlay_heatmap_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompositionFeedback(Base):
    __tablename__ = "composition_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comments: Mapped[str] = mapped_column(Text, default="")
    client_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
