from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ...database import get_db
from ...models.event import Event
from ...schemas.event import EventOut

router = APIRouter()


@router.get("/events", response_model=list[EventOut])
def list_events(
    wallet_id: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Event)
    if wallet_id:
        q = q.filter(Event.wallet_id == wallet_id)
    return q.order_by(desc(Event.tick_number)).offset(offset).limit(limit).all()
