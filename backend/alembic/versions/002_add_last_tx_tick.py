"""add last_tx_tick to sync_state

Revision ID: 002
Revises: 001
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sync_state") as batch_op:
        batch_op.add_column(sa.Column("last_tx_tick", sa.Integer(), nullable=True, server_default="0"))


def downgrade():
    with op.batch_alter_table("sync_state") as batch_op:
        batch_op.drop_column("last_tx_tick")
