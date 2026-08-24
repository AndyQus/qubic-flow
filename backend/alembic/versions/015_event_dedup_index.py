"""add composite index used by the duplicate-event detection

Revision ID: 015
Revises: 014
Create Date: 2026-08-24
"""
from alembic import op

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade():
    # The dedup grouping query buckets by exactly these five columns; without
    # the index it degrades to a full table scan on every sync cycle.
    op.create_index(
        'ix_events_dedup',
        'events',
        ['wallet_id', 'tick_number', 'source_address', 'destination_addr', 'amount_qubic'],
    )
    # `log_digest` is now also consulted as a dedup guard in _persist_logs.
    op.create_index('ix_events_log_digest', 'events', ['log_digest'])


def downgrade():
    op.drop_index('ix_events_log_digest', table_name='events')
    op.drop_index('ix_events_dedup', table_name='events')
