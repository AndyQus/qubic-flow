"""qearn: event classification, principal/interest splits, positions, yield cache

Revision ID: 016
Revises: 015
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events') as batch_op:
        # QEARN_LOCK | QEARN_PAYOUT | QEARN_REFUND — NULL for everything else
        batch_op.add_column(sa.Column('sc_kind', sa.Text(), nullable=True))
        # 1 = payout computed by the Qearn check (not found in any archive)
        batch_op.add_column(sa.Column('reconstructed', sa.Integer(), nullable=True, server_default='0'))

    op.create_table(
        'event_splits',
        sa.Column('event_id', sa.Text(), primary_key=True),
        sa.Column('wallet_id', sa.Text(), primary_key=True),
        sa.Column('part', sa.Text(), primary_key=True),       # PRINCIPAL | INTEREST
        sa.Column('amount_qubic', sa.Integer(), nullable=False),
        sa.Column('estimated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('meta_json', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.Text(), nullable=True),
    )
    op.create_index('ix_event_splits_wallet', 'event_splits', ['wallet_id'])

    op.create_table(
        'qearn_positions',
        sa.Column('wallet_id', sa.Text(), primary_key=True),
        sa.Column('lock_epoch', sa.Integer(), primary_key=True),
        sa.Column('principal_qu', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('early_unlocked_qu', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('end_epoch', sa.Integer(), nullable=False),
        sa.Column('yield_e7', sa.Integer(), nullable=True),
        sa.Column('expected_payout_qu', sa.Integer(), nullable=True),
        sa.Column('payout_qu', sa.Integer(), nullable=True),
        sa.Column('interest_qu', sa.Integer(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('detail_json', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.Text(), nullable=True),
    )

    op.create_table(
        'qearn_epochs',
        sa.Column('epoch', sa.Integer(), primary_key=True),
        sa.Column('yield_e7', sa.Integer(), nullable=True),
        sa.Column('locked_amount', sa.Integer(), nullable=True),
        sa.Column('bonus_amount', sa.Integer(), nullable=True),
        sa.Column('final', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fetched_at', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table('qearn_epochs')
    op.drop_table('qearn_positions')
    op.drop_index('ix_event_splits_wallet', table_name='event_splits')
    op.drop_table('event_splits')
    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_column('reconstructed')
        batch_op.drop_column('sc_kind')
