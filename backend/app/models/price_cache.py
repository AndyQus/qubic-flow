from sqlalchemy import Column, Text, Float
from ..database import Base


class PriceCache(Base):
    __tablename__ = "price_cache"

    date = Column(Text, primary_key=True)
    qubic_eur = Column(Float, nullable=False)
    qubic_usd = Column(Float, nullable=False)
    source = Column(Text, default="coingecko")
    fetched_at = Column(Text, nullable=False)
