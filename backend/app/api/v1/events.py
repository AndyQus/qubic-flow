from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List
from ...database import get_db
from ...models.event import Event
from ...models.wallet import Wallet
from ...schemas.event import EventOut, EventNoteUpdate
from ...services.label_service import get_label

router = APIRouter()


def _base_query(db, wallet_id=None, wallet_ids=None, epoch=None, month=None, year=None, search=None, source_type=None):
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
    if source_type and source_type != "ALL":
        q = q.filter(Event.source_type == source_type)
    if search:
        from sqlalchemy import or_, cast, String
        term = f"%{search}%"
        q = q.filter(or_(
            Event.source_address.ilike(term),
            Event.destination_addr.ilike(term),
            cast(Event.amount_qubic, String).ilike(term),
            cast(Event.epoch, String).ilike(term),
            Event.note.ilike(term),
        ))
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
    search: str | None = Query(None),
    source_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return {"count": _base_query(db, wallet_id=wallet_id, wallet_ids=wallet_ids or None, epoch=epoch, month=month, year=year, search=search, source_type=source_type).count()}


@router.get("/events", response_model=list[EventOut])
def list_events(
    wallet_id: str | None = Query(None),
    wallet_ids: List[str] = Query(default=[]),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    epoch: int | None = Query(None),
    month: str | None = Query(None),
    year: int | None = Query(None),
    search: str | None = Query(None),
    source_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    events = (
        _base_query(db, wallet_id=wallet_id, wallet_ids=wallet_ids or None, epoch=epoch, month=month, year=year, search=search, source_type=source_type)
        .order_by(desc(Event.tick_number))
        .offset(offset)
        .limit(limit)
        .all()
    )
    parts = _qearn_parts(db, events)
    result = []
    for e in events:
        out = EventOut.model_validate(e)
        out.source_name = get_label(db, e.source_address)
        out.destination_name = get_label(db, e.destination_addr)
        out.qearn_parts = parts.get((e.id, e.wallet_id), [])
        result.append(out)
    return result


def _qearn_parts(db: Session, events: list) -> dict:
    """Principal/interest parts of Qearn payouts, keyed by (event id, wallet id)."""
    import json
    from ...models.qearn import EventSplit
    ids = [e.id for e in events if e.sc_kind == "QEARN_PAYOUT"]
    if not ids:
        return {}
    order = {"PRINCIPAL": 0, "INTEREST": 1}
    out: dict = {}
    for s in db.query(EventSplit).filter(EventSplit.event_id.in_(ids)).all():
        out.setdefault((s.event_id, s.wallet_id), []).append({
            "part": s.part, "amount_qubic": s.amount_qubic, "estimated": bool(s.estimated),
            "meta": json.loads(s.meta_json or "{}"),
        })
    for v in out.values():
        v.sort(key=lambda p: order.get(p["part"], 9))
    return out


@router.patch("/events/{event_id}/note", status_code=204)
def update_event_note(event_id: str, body: EventNoteUpdate, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id, Event.wallet_id == body.wallet_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    event.note = body.note or None
    db.commit()
