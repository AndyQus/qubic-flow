"""add owner column to wallets

Revision ID: 006
Revises: 005
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("wallets", sa.Column("owner", sa.String(), nullable=True))


def downgrade():
    op.drop_column("wallets", "owner")
