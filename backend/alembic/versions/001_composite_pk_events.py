"""composite pk on events(id, wallet_id)

Revision ID: 001
Revises:
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # SQLite does not support ALTER TABLE ... DROP/ADD PRIMARY KEY.
    # We recreate the table with the new composite PK (id, wallet_id).
    op.execute("""
        CREATE TABLE events_new (
            id TEXT NOT NULL,
            wallet_id TEXT NOT NULL,
            epoch INTEGER,
            tick_number INTEGER,
            timestamp_raw TEXT,
            timestamp TEXT,
            log_type INTEGER,
            log_digest TEXT,
            categories TEXT,
            source_address TEXT,
            destination_addr TEXT,
            is_internal INTEGER DEFAULT 0,
            amount_qubic INTEGER,
            qubic_eur_rate REAL,
            qubic_usd_rate REAL,
            buy_value_eur REAL,
            buy_value_usd REAL,
            sell_value_eur REAL,
            sell_value_usd REAL,
            source_type TEXT,
            buy_currency TEXT,
            sell_currency TEXT,
            item_id TEXT,
            item_name TEXT,
            comment TEXT,
            trade_group TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT,
            PRIMARY KEY (id, wallet_id)
        )
    """)
    op.execute("""
        INSERT INTO events_new SELECT
            id, wallet_id, epoch, tick_number, timestamp_raw, timestamp,
            log_type, log_digest, categories, source_address, destination_addr,
            is_internal, amount_qubic, qubic_eur_rate, qubic_usd_rate,
            buy_value_eur, buy_value_usd, sell_value_eur, sell_value_usd,
            source_type, buy_currency, sell_currency, item_id, item_name,
            comment, trade_group, verified, created_at
        FROM events
    """)
    op.execute("DROP TABLE events")
    op.execute("ALTER TABLE events_new RENAME TO events")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_wallet_id ON events (wallet_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_tick_number ON events (tick_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_timestamp ON events (timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_source_address ON events (source_address)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_destination_addr ON events (destination_addr)")


def downgrade():
    op.execute("""
        CREATE TABLE events_old (
            id TEXT NOT NULL PRIMARY KEY,
            wallet_id TEXT,
            epoch INTEGER,
            tick_number INTEGER,
            timestamp_raw TEXT,
            timestamp TEXT,
            log_type INTEGER,
            log_digest TEXT,
            categories TEXT,
            source_address TEXT,
            destination_addr TEXT,
            is_internal INTEGER DEFAULT 0,
            amount_qubic INTEGER,
            qubic_eur_rate REAL,
            qubic_usd_rate REAL,
            buy_value_eur REAL,
            buy_value_usd REAL,
            sell_value_eur REAL,
            sell_value_usd REAL,
            source_type TEXT,
            buy_currency TEXT,
            sell_currency TEXT,
            item_id TEXT,
            item_name TEXT,
            comment TEXT,
            trade_group TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    op.execute("""
        INSERT OR IGNORE INTO events_old SELECT
            id, wallet_id, epoch, tick_number, timestamp_raw, timestamp,
            log_type, log_digest, categories, source_address, destination_addr,
            is_internal, amount_qubic, qubic_eur_rate, qubic_usd_rate,
            buy_value_eur, buy_value_usd, sell_value_eur, sell_value_usd,
            source_type, buy_currency, sell_currency, item_id, item_name,
            comment, trade_group, verified, created_at
        FROM events
    """)
    op.execute("DROP TABLE events")
    op.execute("ALTER TABLE events_old RENAME TO events")
