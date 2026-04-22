"""add opening_positions table

Revision ID: 005
Revises: 004
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS opening_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id TEXT NOT NULL,
            date TEXT NOT NULL,
            amount_qubic INTEGER NOT NULL,
            price_eur REAL,
            price_usd REAL,
            note TEXT,
            created_at TEXT NOT NULL
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS opening_positions")
