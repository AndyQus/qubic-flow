from pydantic import BaseModel
from typing import Optional, Any


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
    log_type: Optional[int] = None
    is_internal: int = 0
    source_name: Optional[str] = None
    destination_name: Optional[str] = None
    note: Optional[str] = None
    sc_kind: Optional[str] = None
    reconstructed: Optional[int] = 0
    # Qearn payout split: [{part, amount_qubic, estimated, meta}] — empty for all other rows
    qearn_parts: list[dict[str, Any]] = []

    class Config:
        from_attributes = True


class EventNoteUpdate(BaseModel):
    wallet_id: str
    note: Optional[str] = None
