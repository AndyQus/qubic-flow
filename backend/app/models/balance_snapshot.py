from sqlalchemy import Column, Text, Integer, Float, UniqueConstraint
from ..database import Base


class BalanceSnapshot(Base):
    """One wallet balance captured at one point of a series (hourly/daily/weekly).

    `bucket` identifies the capture slot within a series so restarts cannot
    create duplicates: hourly "2026-07-14T15", daily "2026-07-14", weekly
    "e221" (epoch number), manual captures "m<ms>", user-entered rows "u<ms>".
    `delta` is the change versus the previous row of the same series+wallet.
    When a user edits an auto-captured value the previous values are kept in
    `original_json` and `edited` is set — the export shows the edited value,
    the measurement stays available as audit trail.
    """
    __tablename__ = "balance_snapshots"
    __table_args__ = (
        UniqueConstraint("kind", "bucket", "wallet_id", name="uq_balance_snapshot_slot"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(Text, nullable=False, index=True)      # hourly | daily | weekly
    bucket = Column(Text, nullable=False, index=True)
    trigger = Column(Text, nullable=False, default="auto")  # auto | manual | user
    captured_at = Column(Text, nullable=False, index=True)
    range_from = Column(Text)
    range_to = Column(Text)
    wallet_id = Column(Text, nullable=False, index=True)
    label = Column(Text)
    owner = Column(Text)
    balance = Column(Integer)
    delta = Column(Integer)
    in_total = Column(Integer)     # cumulative incoming amount (RPC)
    out_total = Column(Integer)    # cumulative outgoing amount (RPC)
    in_amount = Column(Integer)    # incoming within the interval
    out_amount = Column(Integer)   # outgoing within the interval
    tick = Column(Integer)
    epoch = Column(Integer)
    eur_rate = Column(Float)       # EUR per QUBIC
    usd_rate = Column(Float)       # USD per QUBIC
    value_eur = Column(Float)      # balance * eur_rate
    value_usd = Column(Float)      # balance * usd_rate
    source = Column(Text)          # rpc | bob | user
    edited = Column(Integer, default=0)
    original_json = Column(Text)
    created_at = Column(Text, nullable=False)


class SnapshotAnnotation(Base):
    """User annotations per capture row (kind+bucket): category and notes.

    Mirrors the manual columns of the user's Excel ledger (why / Informationen /
    Anmerkungen) — maintained in the app, exported into the generated files.
    """
    __tablename__ = "snapshot_annotations"
    __table_args__ = (
        UniqueConstraint("kind", "bucket", name="uq_snapshot_annotation_slot"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(Text, nullable=False, index=True)
    bucket = Column(Text, nullable=False, index=True)
    why = Column(Text)
    info = Column(Text)
    note = Column(Text)
    updated_at = Column(Text)
