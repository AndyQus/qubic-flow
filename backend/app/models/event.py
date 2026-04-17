from sqlalchemy import Column, Text, Integer, Float
from sqlalchemy.orm import relationship
from ..database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Text, primary_key=True)
    epoch = Column(Integer)
    tick_number = Column(Integer, index=True)
    timestamp_raw = Column(Text)
    timestamp = Column(Text, index=True)
    log_type = Column(Integer)
    log_digest = Column(Text)
    categories = Column(Text)
    source_address = Column(Text, index=True)
    destination_addr = Column(Text, index=True)
    wallet_id = Column(Text, index=True)
    is_internal = Column(Integer, default=0)
    amount_qubic = Column(Integer)
    qubic_eur_rate = Column(Float)
    qubic_usd_rate = Column(Float)
    buy_value_eur = Column(Float)
    buy_value_usd = Column(Float)
    sell_value_eur = Column(Float)
    sell_value_usd = Column(Float)
    source_type = Column(Text)
    buy_currency = Column(Text)
    sell_currency = Column(Text)
    item_id = Column(Text)
    item_name = Column(Text)
    comment = Column(Text)
    trade_group = Column(Text)
    verified = Column(Integer, default=0)
    created_at = Column(Text)

    wallet = relationship(
        "Wallet",
        back_populates="events",
        primaryjoin="foreign(Event.wallet_id) == Wallet.id",
    )
