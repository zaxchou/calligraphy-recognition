"""
版本历史模型 — work_revisions 表
每次数据变更时自动创建一条 revision 记录
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base


class WorkRevision(Base):
    __tablename__ = "work_revisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artwork_id = Column(Integer, nullable=False, index=True, comment="作品ID (tubi_analyses.id)")
    revision_number = Column(Integer, nullable=False, comment="版本号（从1开始递增）")
    snapshot = Column(Text, nullable=False, comment="完整数据快照 (JSON)")
    change_summary = Column(Text, nullable=True, comment="编辑摘要")
    operation_type = Column(String(30), nullable=False, default="edit", comment="操作类型: edit/approve/reject/upload/rollback")
    approved_by = Column(Integer, nullable=True, comment="审核者用户ID")
    submitted_by = Column(Integer, nullable=True, comment="提交者用户ID")
    change_request_id = Column(Integer, nullable=True, comment="关联的变更请求ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
