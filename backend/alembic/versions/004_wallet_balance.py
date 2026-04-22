"""add balance fields to wallets

Revision ID: 004
Revises: 003
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wallets") as batch_op:
        batch_op.add_column(sa.Column("balance", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("balance_updated_at", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("balance_live", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("balance_live_at", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("balance_since_tick", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("wallets") as batch_op:
        batch_op.drop_column("balance_since_tick")
        batch_op.drop_column("balance_live_at")
        batch_op.drop_column("balance_live")
        batch_op.drop_column("balance_updated_at")
        batch_op.drop_column("balance")
