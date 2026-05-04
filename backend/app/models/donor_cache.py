from sqlalchemy import Column, Text, Integer
from ..database import Base


class DonorCache(Base):
    __tablename__ = "donor_cache"

    address = Column(Text, primary_key=True)
    total_qu = Column(Integer, nullable=False, default=0)
    last_date = Column(Text, nullable=True)   # ISO date YYYY-MM-DD
    last_tick = Column(Integer, nullable=True)
    suppressed_until = Column(Text, nullable=True)  # ISO date or "2099-12-31"
    forever = Column(Integer, nullable=False, default=0)  # 1 = forever
    updated_at = Column(Text, nullable=False)
