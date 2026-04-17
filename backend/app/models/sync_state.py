from sqlalchemy import Column, Text, Integer
from sqlalchemy.orm import relationship
from ..database import Base


class SyncState(Base):
    __tablename__ = "sync_state"

    wallet_id = Column(Text, primary_key=True)
    last_tick = Column(Integer, default=0)
    last_sync = Column(Text)
    status = Column(Text, default="IDLE")
    error_message = Column(Text, nullable=True)
    total_events = Column(Integer, default=0)
    last_window_size = Column(Integer, default=10000)

    wallet = relationship(
        "Wallet",
        back_populates="sync_state",
        primaryjoin="foreign(SyncState.wallet_id) == Wallet.id",
    )
