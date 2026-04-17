from sqlalchemy import Column, Text, Integer
from ..database import Base


class SyncGap(Base):
    __tablename__ = "sync_gaps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Text, nullable=False)
    from_tick = Column(Integer, nullable=False)
    to_tick = Column(Integer, nullable=False)
    detected_at = Column(Text, nullable=False)
    resolved_at = Column(Text, nullable=True)
