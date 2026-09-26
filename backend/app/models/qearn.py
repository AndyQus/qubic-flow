from sqlalchemy import Column, Text, Integer
from ..database import Base


class EventSplit(Base):
    """Principal/interest breakdown of one on-chain Qearn payout.

    The original event row stays untouched (1 row = 1 on-chain transfer, so
    balance, dedup and explorer matching keep working); UI, exports and the
    tax engine read the two parts from here instead.
    """
    __tablename__ = "event_splits"

    event_id = Column(Text, primary_key=True)
    wallet_id = Column(Text, primary_key=True, index=True)
    part = Column(Text, primary_key=True)  # PRINCIPAL | INTEREST
    amount_qubic = Column(Integer, nullable=False)
    estimated = Column(Integer, nullable=False, default=0)
    meta_json = Column(Text)
    updated_at = Column(Text)


class QearnPosition(Base):
    """One Qearn lock round of a wallet (all locks of one epoch are merged by the contract)."""
    __tablename__ = "qearn_positions"

    wallet_id = Column(Text, primary_key=True)
    lock_epoch = Column(Integer, primary_key=True)
    principal_qu = Column(Integer, nullable=False, default=0)
    early_unlocked_qu = Column(Integer, nullable=False, default=0)
    end_epoch = Column(Integer, nullable=False)
    yield_e7 = Column(Integer)
    expected_payout_qu = Column(Integer)
    payout_qu = Column(Integer)
    interest_qu = Column(Integer)
    status = Column(Text, nullable=False)
    detail_json = Column(Text)
    checked_at = Column(Text)


class QearnEpoch(Base):
    """Cached getLockInfoPerEpoch result — immutable once the round has ended."""
    __tablename__ = "qearn_epochs"

    epoch = Column(Integer, primary_key=True)
    yield_e7 = Column(Integer)
    locked_amount = Column(Integer)
    bonus_amount = Column(Integer)
    final = Column(Integer, nullable=False, default=0)
    fetched_at = Column(Text)
