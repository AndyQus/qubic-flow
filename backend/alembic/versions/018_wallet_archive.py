"""add archive flag, reason and successor to wallets

Revision ID: 018
Revises: 017
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wallets') as batch_op:
        batch_op.add_column(sa.Column('archived', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('archived_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('archived_successor', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('archived_at', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('wallets') as batch_op:
        batch_op.drop_column('archived_at')
        batch_op.drop_column('archived_successor')
        batch_op.drop_column('archived_reason')
        batch_op.drop_column('archived')
