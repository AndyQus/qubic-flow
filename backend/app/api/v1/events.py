from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List
from ...database import get_db
from ...models.event import Event
from ...models.wallet import Wallet
from ...schemas.event import EventOut
from ...services.label_service import get_label

router = APIRouter()


def _base_query(db, wallet_id=None, wallet_ids=None, epoch=None, month=None, year=None):
    q = db.query(Event).join(Wallet, Wallet.id == Event.wallet_id).filter(Wallet.deleted_at.is_(None))
    if wallet_ids:
        q = q.filter(Event.wallet_id.in_(wallet_ids))
    elif wallet_id:
        q = q.filter(Event.wallet_id == wallet_id)
    if epoch is not None:
        q = q.filter(Event.epoch == epoch)
    if month:
        q = q.filter(func.strftime('%Y-%m', Event.timestamp) == month)
    if year:
        q = q.filter(func.strftime('%Y', Event.timestamp) == str(year))
    return q


@router.get("/events/filter-options")
def filter_options(
    wallet_id: str | None = Query(None),
    wallet_ids: List[str] = Query(default=[]),
    db: Session = Depends(get_db),
):
    base = _base_query(db, wallet_id=wallet_id, wallet_ids=wallet_ids or None)

    years = sorted(
        {r[0] for r in base.with_entities(func.strftime('%Y', Event.timestamp)).distinct() if r[0]},
        reverse=True,
    )
    months = sorted(
        {r[0] for r in base.with_entities(func.strftime('%Y-%m', Event.timestamp)).distinct() if r[0]},
        reverse=True,
    )
    epochs = sorted(
        {r[0] for r in base.with_entities(Event.epoch).distinct() if r[0] is not None},
        reverse=True,
    )
    return {"years": years, "months": months, "epochs": epochs}


@router.get("/events/count")
def count_events(
    wallet_id: str | None = Query(None),
    wallet_ids: List[str] = Query(default=[]),
    epoch: int | None = Query(None),
    month: str | None = Query(None),
    year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    return {"count": _base_query(db, wallet_id=wallet_id, wallet_ids=wallet_ids or None, epoch=epoch, month=month, year=year).count()}


@router.get("/events", response_model=list[EventOut])
def list_events(
    wallet_id: str | None = Query(None),
    wallet_ids: List[str] = Query(default=[]),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    epoch: int | None = Query(None),
    month: str | None = Query(None),
    year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    events = (
        _base_query(db, wallet_id=wallet_id, wallet_ids=wallet_ids or None, epoch=epoch, month=month, year=year)
        .order_by(desc(Event.tick_number))
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = []
    for e in events:
        out = EventOut.model_validate(e)
        out.source_name = get_label(db, e.source_address)
        out.destination_name = get_label(db, e.destination_addr)
        result.append(out)
    return result
