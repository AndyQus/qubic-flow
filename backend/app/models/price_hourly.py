from sqlalchemy import Column, Text, Float
from ..database import Base


class PriceHourly(Base):
    """QUBIC price captured once per full hour (UTC).

    A row only exists for hours whose fetch succeeded — gaps stay gaps, the
    lookup falls back to the last known hour instead of storing copies.
    """
    __tablename__ = "price_hourly"

    hour = Column(Text, primary_key=True)  # YYYY-MM-DDTHH (UTC)
    qubic_eur = Column(Float, nullable=False)
    qubic_usd = Column(Float, nullable=False)
    source = Column(Text, default="coingecko")
    fetched_at = Column(Text, nullable=False)
