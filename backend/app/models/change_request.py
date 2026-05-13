"""
变更请求模型 — change_requests 表
Phase 2: Wiki 式协作编辑，类似百度百科的编辑审阅机制
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    library_id = Column(Integer, nullable=False, index=True, comment="所属作品库ID")
    artwork_id = Column(Integer, nullable=False, index=True, comment="目标作品ID (tubi_analyses.id)")
    request_type = Column(String(30), nullable=False, comment="请求类型: edit_field/edit_inscription/adjust_region/add_field")
    field_name = Column(String(100), nullable=True, comment="要修改的字段名")
    old_value = Column(Text, nullable=True, comment="原始值")
    new_value = Column(Text, nullable=True, comment="新值")
    change_summary = Column(Text, nullable=True, comment="修改说明/依据")
    submitter_id = Column(Integer, nullable=False, index=True, comment="提交者用户ID")
    reviewer_id = Column(Integer, nullable=True, comment="审核者用户ID")
    status = Column(String(20), default="pending", comment="状态: pending/approved/rejected")
    review_comment = Column(Text, nullable=True, comment="审核意见")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True, comment="审核时间")
