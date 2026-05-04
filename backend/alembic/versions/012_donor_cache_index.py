"""add index on donor_cache.total_qu

Revision ID: 012
Revises: 011
Create Date: 2026-05-04
"""
from alembic import op

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('donor_cache') as batch_op:
        batch_op.create_index('ix_donor_cache_total_qu', ['total_qu'])


def downgrade():
    with op.batch_alter_table('donor_cache') as batch_op:
        batch_op.drop_index('ix_donor_cache_total_qu')
