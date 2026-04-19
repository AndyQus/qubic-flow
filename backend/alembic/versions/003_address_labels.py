"""add address_labels table

Revision ID: 003
Revises: 002
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS address_labels (
            address TEXT NOT NULL PRIMARY KEY,
            name TEXT,
            label TEXT,
            website TEXT,
            category TEXT,
            asset_type INTEGER,
            decimal_places INTEGER,
            universe_index INTEGER,
            source TEXT,
            updated_at TEXT
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS address_labels")
