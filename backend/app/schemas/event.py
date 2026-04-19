from pydantic import BaseModel
from typing import Optional


class EventOut(BaseModel):
    id: str
    epoch: Optional[int]
    tick_number: Optional[int]
    timestamp: Optional[str]
    source_address: Optional[str]
    destination_addr: Optional[str]
    wallet_id: Optional[str]
    amount_qubic: Optional[int]
    qubic_eur_rate: Optional[float]
    qubic_usd_rate: Optional[float]
    source_type: Optional[str]
    is_internal: int = 0
    source_name: Optional[str] = None
    destination_name: Optional[str] = None

    class Config:
        from_attributes = True
