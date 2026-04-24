"""add last_error to nodes

Revision ID: 008
Revises: 007
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('nodes') as batch_op:
        batch_op.add_column(sa.Column('last_error', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('nodes') as batch_op:
        batch_op.drop_column('last_error')
