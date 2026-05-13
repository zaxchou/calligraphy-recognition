"""Phase 1: Multi-user base — users table, artwork fields, new tables

Revision ID: 1baa719a7a57
Revises: 0c90edc2a0cd
Create Date: 2026-05-14 03:30:30.327347
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1baa719a7a57'
down_revision: Union[str, Sequence[str], None] = '0c90edc2a0cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. users table ──
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('wechat_openid', sa.Text(), unique=True, nullable=False),
        sa.Column('wechat_unionid', sa.Text(), nullable=True),
        sa.Column('nickname', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), server_default='free_user'),
        sa.Column('subscription_tier', sa.Text(), server_default='free'),
        sa.Column('subscription_expires_at', sa.DateTime(), nullable=True),
        sa.Column('storage_used_bytes', sa.Integer(), server_default='0'),
        sa.Column('ai_calls_this_month', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 2. tubi_analyses 新增字段（全部可为 NULL，确保现有数据不受影响）──
    with op.batch_alter_table('tubi_analyses') as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('library_id', sa.Integer(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('visibility', sa.Text(), nullable=True, server_default=sa.text("'public'")))
        batch_op.add_column(sa.Column('created_by', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('material', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('mounting_format', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('current_location', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('provenance', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('style_tags', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('subject_tags', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('technique_tags', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('free_tags', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('inscription_author', sa.Text(), nullable=True, server_default=None))
        batch_op.add_column(sa.Column('inscription_date', sa.Text(), nullable=True, server_default=None))

    # ── 3. artwork_libraries ──
    op.create_table(
        'artwork_libraries',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('visibility', sa.Text(), server_default='private'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 4. library_collaborators ──
    op.create_table(
        'library_collaborators',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('library_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Text(), server_default='viewer'),
        sa.Column('added_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('library_id', 'user_id', name='uq_library_collab'),
    )

    # ── 5. collaborator_requests ──
    op.create_table(
        'collaborator_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('library_id', sa.Integer(), nullable=False),
        sa.Column('from_user_id', sa.Integer(), nullable=False),
        sa.Column('to_user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Text(), server_default='pending'),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 6. research_notes ──
    op.create_table(
        'research_notes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('artwork_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('visibility', sa.Text(), server_default='private'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 7. subscriptions ──
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_tier', sa.Text(), nullable=False, server_default='free'),
        sa.Column('amount_paid', sa.Integer(), server_default='0'),
        sa.Column('currency', sa.Text(), server_default='CNY'),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('payment_ref', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 8. api_usage_logs ──
    op.create_table(
        'api_usage_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('model_name', sa.Text(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), server_default='0'),
        sa.Column('duration_ms', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 9. literature_references ──
    op.create_table(
        'literature_references',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('artwork_id', sa.Integer(), nullable=False),
        sa.Column('reference_type', sa.Text(), server_default='citation'),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('publisher', sa.Text(), nullable=True),
        sa.Column('page', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 10. auction_records ──
    op.create_table(
        'auction_records',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('artwork_id', sa.Integer(), nullable=False),
        sa.Column('auction_house', sa.Text(), nullable=True),
        sa.Column('sale_date', sa.Text(), nullable=True),
        sa.Column('lot_number', sa.Text(), nullable=True),
        sa.Column('estimate_low', sa.Float(), nullable=True),
        sa.Column('estimate_high', sa.Float(), nullable=True),
        sa.Column('hammer_price', sa.Float(), nullable=True),
        sa.Column('currency', sa.Text(), server_default='CNY'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # ── Drop new tables in reverse order ──
    op.drop_table('auction_records')
    op.drop_table('literature_references')
    op.drop_table('api_usage_logs')
    op.drop_table('subscriptions')
    op.drop_table('research_notes')
    op.drop_table('collaborator_requests')
    op.drop_table('library_collaborators')
    op.drop_table('artwork_libraries')

    # ── Drop new columns from tubi_analyses ──
    with op.batch_alter_table('tubi_analyses') as batch_op:
        batch_op.drop_column('inscription_date')
        batch_op.drop_column('inscription_author')
        batch_op.drop_column('free_tags')
        batch_op.drop_column('technique_tags')
        batch_op.drop_column('subject_tags')
        batch_op.drop_column('style_tags')
        batch_op.drop_column('provenance')
        batch_op.drop_column('current_location')
        batch_op.drop_column('mounting_format')
        batch_op.drop_column('material')
        batch_op.drop_column('created_by')
        batch_op.drop_column('visibility')
        batch_op.drop_column('library_id')
        batch_op.drop_column('owner_id')

    # ── Drop users table ──
    op.drop_table('users')
