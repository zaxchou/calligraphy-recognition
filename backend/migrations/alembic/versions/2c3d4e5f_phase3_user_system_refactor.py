"""Phase 3: User system refactor — 5-level roles + artist claims + real login

Revision ID: 2c3d4e5f
Revises: 1baa719a7a57
Create Date: 2026-05-14

废弃 Phase2 的粗糙作品库体系，建立：
- 5级角色: super_admin / admin / editor / reader / guest
- 真实登录: 手机验证码 + 密码双模式
- 认领画家制: artist_claims 表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '1baa719a7a57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """废弃作品库体系 + 建立新角色系统"""

    # ── 1. DROP 作品库相关表（IF EXISTS via raw SQL）──
    op.execute("DROP TABLE IF EXISTS artwork_libraries")
    op.execute("DROP TABLE IF EXISTS library_collaborators")

    # ── 2. 重命名 role 列值 ──
    # free_user → reader, paid_user → editor
    # 先查有哪些 role 存在，再做对应的 UPDATE
    op.execute("UPDATE users SET role = 'reader' WHERE role = 'free_user'")
    op.execute("UPDATE users SET role = 'editor' WHERE role = 'paid_user'")

    # ── 3. users 表加字段 ──
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('password_hash', sa.Text(), nullable=True, server_default=None))

    # ── 4. 创建 artist_claims 表 ──
    op.create_table(
        'artist_claims',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('artist_name', sa.Text(), nullable=False),
        sa.Column('claim_type', sa.Text(), server_default='wiki'),
        sa.Column('status', sa.Text(), server_default='pending'),
        sa.Column('apply_reason', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'artist_name', name='uq_user_artist_claim'),
    )

    # ── 5. 站长 (id=1) 设为 super_admin ──
    op.execute("UPDATE users SET role = 'super_admin' WHERE id = 1")


def downgrade() -> None:
    """回滚到 Phase2 状态"""

    # ── 5. 恢复 id=1 角色 ──
    op.execute("UPDATE users SET role = 'free_user' WHERE id = 1 AND role = 'super_admin'")

    # ── 4. DROP artist_claims ──
    op.drop_table('artist_claims')

    # ── 3. users 删字段 ──
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('password_hash')

    # ── 2. 恢复 role 值 ──
    op.execute("UPDATE users SET role = 'free_user' WHERE role = 'reader'")
    op.execute("UPDATE users SET role = 'paid_user' WHERE role = 'editor'")

    # ── 1. 重建 artwork_libraries 和 library_collaborators ──
    op.create_table(
        'artwork_libraries',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('artist_name', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('visibility', sa.Text(), server_default='private'),
        sa.Column('artwork_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        'library_collaborators',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('library_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Text(), server_default='viewer'),
        sa.Column('added_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('library_id', 'user_id', name='uq_library_collab'),
    )
