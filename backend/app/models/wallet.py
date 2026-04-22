from sqlalchemy import Column, Text, Integer
from sqlalchemy.orm import relationship
from ..database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Text, primary_key=True)
    label = Column(Text, nullable=False)
    note = Column(Text)
    wallet_type = Column(Text, nullable=False)
    active = Column(Integer, default=1)
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text)
    deleted_at = Column(Text, nullable=True)
    balance = Column(Integer, nullable=True)
    balance_updated_at = Column(Text, nullable=True)
    balance_live = Column(Integer, nullable=True)
    balance_live_at = Column(Text, nullable=True)
    balance_since_tick = Column(Integer, nullable=True)

    sync_state = relationship(
        "SyncState",
        back_populates="wallet",
        uselist=False,
        primaryjoin="Wallet.id == foreign(SyncState.wallet_id)",
    )
    events = relationship(
        "Event",
        back_populates="wallet",
        primaryjoin="Wallet.id == foreign(Event.wallet_id)",
    )
