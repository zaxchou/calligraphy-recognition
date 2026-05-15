"""细粒度权限模型 — role_permissions 表"""

from sqlalchemy import Column, Integer, String
from app.core.database import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String, nullable=False, comment="角色: admin/editor/reader")
    permission_key = Column(String, nullable=False, comment="权限标识符")
