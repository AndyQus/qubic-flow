"""add note to events

Revision ID: 009
Revises: 008
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events') as batch_op:
        batch_op.add_column(sa.Column('note', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_column('note')
