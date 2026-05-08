"""add notes to nodes

Revision ID: 013
Revises: 012
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('nodes') as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('nodes') as batch_op:
        batch_op.drop_column('notes')
