from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class WalletCreate(BaseModel):
    id: str
    label: str
    note: Optional[str] = None
    wallet_type: str


class WalletUpdate(BaseModel):
    label: Optional[str] = None
    note: Optional[str] = None
    wallet_type: Optional[str] = None
    active: Optional[int] = None


class WalletOut(BaseModel):
    id: str
    label: str
    note: Optional[str]
    wallet_type: str
    active: int
    created_at: str

    class Config:
        from_attributes = True
