from pydantic import BaseModel
from typing import Optional


class EventOut(BaseModel):
    id: str
    log_digest: Optional[str] = None
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
    note: Optional[str] = None

    class Config:
        from_attributes = True


class EventNoteUpdate(BaseModel):
    wallet_id: str
    note: Optional[str] = None
