from sqlalchemy import Column, Text, Integer, Float
from ..database import Base


class WeeklySnapshot(Base):
    __tablename__ = "weekly_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_at = Column(Text, nullable=False)
    epoch = Column(Integer)
    week = Column(Integer)
    month = Column(Integer)
    year = Column(Integer)
    tx_count = Column(Integer, default=0)
    event_count = Column(Integer, default=0)
    volume_qubic = Column(Integer, default=0)
    volume_eur = Column(Float, default=0.0)
    volume_usd = Column(Float, default=0.0)
