from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class WalletCreate(BaseModel):
    id: str = Field(..., pattern=r"^[A-Z]{60}$", description="Qubic address: 60 uppercase letters")
    label: str = Field(..., min_length=1, max_length=200)
    note: Optional[str] = Field(None, max_length=1000)
    wallet_type: Literal["PRIVATE", "BUSINESS"]


class WalletUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=200)
    note: Optional[str] = Field(None, max_length=1000)
    wallet_type: Optional[Literal["PRIVATE", "BUSINESS"]] = None
    active: Optional[int] = None


class WalletOut(BaseModel):
    id: str
    label: str
    note: Optional[str]
    wallet_type: str
    active: int
    created_at: str
    balance: Optional[int] = None
    balance_updated_at: Optional[str] = None
    balance_live: Optional[int] = None
    balance_live_at: Optional[str] = None

    class Config:
        from_attributes = True
