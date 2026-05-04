"""add gap_type to sync_gaps

Revision ID: 010
Revises: 009
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sync_gaps') as batch_op:
        batch_op.add_column(sa.Column('gap_type', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('sync_gaps') as batch_op:
        batch_op.drop_column('gap_type')
