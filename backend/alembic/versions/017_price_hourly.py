"""add price_hourly table and hourly rate columns on events

Revision ID: 017
Revises: 016
Create Date: 2026-10-07
"""
from alembic import op
import sqlalchemy as sa

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'price_hourly',
        sa.Column('hour', sa.Text(), primary_key=True),
        sa.Column('qubic_eur', sa.Float(), nullable=False),
        sa.Column('qubic_usd', sa.Float(), nullable=False),
        sa.Column('source', sa.Text(), nullable=True, server_default='coingecko'),
        sa.Column('fetched_at', sa.Text(), nullable=False),
    )
    with op.batch_alter_table('events') as batch_op:
        batch_op.add_column(sa.Column('qubic_eur_rate_hourly', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('qubic_usd_rate_hourly', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_column('qubic_usd_rate_hourly')
        batch_op.drop_column('qubic_eur_rate_hourly')
    op.drop_table('price_hourly')
