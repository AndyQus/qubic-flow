from sqlalchemy import Column, Text, Integer
from ..database import Base


class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, unique=True, nullable=False)
    node_type = Column(Text, nullable=False)
    label = Column(Text)
    priority = Column(Integer, default=1)
    tick = Column(Integer)
    response_time_ms = Column(Integer)
    health_status = Column(Text, default="ONLINE")
    is_active = Column(Integer, default=1)
    fail_count = Column(Integer, default=0)
    last_checked = Column(Text)
    last_error = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
