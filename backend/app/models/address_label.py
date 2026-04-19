from sqlalchemy import Column, Text, Integer
from ..database import Base


class AddressLabel(Base):
    __tablename__ = "address_labels"

    address = Column(Text, primary_key=True)
    name = Column(Text)
    label = Column(Text)
    website = Column(Text)
    category = Column(Text)
    asset_type = Column(Integer)
    decimal_places = Column(Integer)
    universe_index = Column(Integer)
    source = Column(Text)
    updated_at = Column(Text)
