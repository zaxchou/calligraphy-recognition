"""
认领画家模型 — artist_claims 表
Phase 3: 用户系统重构 — 编者认领画家制
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class ArtistClaim(Base):
    __tablename__ = "artist_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="申请人用户ID")
    artist_name = Column(String(255), nullable=False, comment="画家名称")
    claim_type = Column(String(20), default="wiki", comment="认领类型: wiki/full")
    status = Column(String(20), default="pending", comment="状态: pending/approved/rejected")
    apply_reason = Column(Text, nullable=True, comment="申请理由")
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="审核人用户ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True, comment="审核时间")

    __table_args__ = (
        UniqueConstraint('user_id', 'artist_name', name='uq_user_artist_claim'),
    )

    # Relationships
    user = relationship("User", back_populates="artist_claims", foreign_keys=[user_id])
