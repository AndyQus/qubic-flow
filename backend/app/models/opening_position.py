from sqlalchemy import Column, Text, Integer, Float
from ..database import Base


class OpeningPosition(Base):
    __tablename__ = "opening_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Text, nullable=False, index=True)
    date = Column(Text, nullable=False)
    amount_qubic = Column(Integer, nullable=False)
    price_eur = Column(Float)
    price_usd = Column(Float)
    note = Column(Text)
    created_at = Column(Text, nullable=False)
