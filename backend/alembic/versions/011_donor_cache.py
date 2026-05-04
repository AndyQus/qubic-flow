"""add donor_cache table

Revision ID: 011
Revises: 010
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'donor_cache',
        sa.Column('address', sa.Text(), primary_key=True),
        sa.Column('total_qu', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_date', sa.Text(), nullable=True),
        sa.Column('last_tick', sa.Integer(), nullable=True),
        sa.Column('suppressed_until', sa.Text(), nullable=True),
        sa.Column('forever', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table('donor_cache')
