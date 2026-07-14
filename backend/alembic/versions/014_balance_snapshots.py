"""add balance_snapshots and snapshot_annotations tables

Revision ID: 014
Revises: 013
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'balance_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('bucket', sa.Text(), nullable=False),
        sa.Column('trigger', sa.Text(), nullable=False, server_default='auto'),
        sa.Column('captured_at', sa.Text(), nullable=False),
        sa.Column('range_from', sa.Text(), nullable=True),
        sa.Column('range_to', sa.Text(), nullable=True),
        sa.Column('wallet_id', sa.Text(), nullable=False),
        sa.Column('label', sa.Text(), nullable=True),
        sa.Column('owner', sa.Text(), nullable=True),
        sa.Column('balance', sa.Integer(), nullable=True),
        sa.Column('delta', sa.Integer(), nullable=True),
        sa.Column('in_total', sa.Integer(), nullable=True),
        sa.Column('out_total', sa.Integer(), nullable=True),
        sa.Column('in_amount', sa.Integer(), nullable=True),
        sa.Column('out_amount', sa.Integer(), nullable=True),
        sa.Column('tick', sa.Integer(), nullable=True),
        sa.Column('epoch', sa.Integer(), nullable=True),
        sa.Column('eur_rate', sa.Float(), nullable=True),
        sa.Column('usd_rate', sa.Float(), nullable=True),
        sa.Column('value_eur', sa.Float(), nullable=True),
        sa.Column('value_usd', sa.Float(), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('edited', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('original_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.UniqueConstraint('kind', 'bucket', 'wallet_id', name='uq_balance_snapshot_slot'),
    )
    op.create_index('ix_balance_snapshots_kind', 'balance_snapshots', ['kind'])
    op.create_index('ix_balance_snapshots_bucket', 'balance_snapshots', ['bucket'])
    op.create_index('ix_balance_snapshots_wallet_id', 'balance_snapshots', ['wallet_id'])
    op.create_index('ix_balance_snapshots_captured_at', 'balance_snapshots', ['captured_at'])

    op.create_table(
        'snapshot_annotations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('bucket', sa.Text(), nullable=False),
        sa.Column('why', sa.Text(), nullable=True),
        sa.Column('info', sa.Text(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.Text(), nullable=True),
        sa.UniqueConstraint('kind', 'bucket', name='uq_snapshot_annotation_slot'),
    )
    op.create_index('ix_snapshot_annotations_kind', 'snapshot_annotations', ['kind'])
    op.create_index('ix_snapshot_annotations_bucket', 'snapshot_annotations', ['bucket'])


def downgrade():
    op.drop_table('snapshot_annotations')
    op.drop_table('balance_snapshots')
