from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ...database import get_db
from ...models.address_label import AddressLabel

router = APIRouter()


class LabelOut(BaseModel):
    address: str
    name: Optional[str]
    label: Optional[str]
    website: Optional[str]
    category: Optional[str]

    class Config:
        from_attributes = True


@router.get("/labels", response_model=list[LabelOut])
def list_labels(
    address: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(AddressLabel)
    if address:
        q = q.filter(AddressLabel.address == address)
    return q.all()
