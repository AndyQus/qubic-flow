from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List
from ...database import get_db
from ...models.event import Event
from ...models.wallet import Wallet
from ...schemas.event import EventOut, EventNoteUpdate
from ...services.label_service import get_label

from ...models.settings import AppSetting

DONATION_ADDRESS = "CCCJKFMDTUFFWDCRBFNHMQRYOBABEKBDUZWEJMARUETQPTFZWBCJLYUGREXI"
DONATION_QU_PER_MONTH = 1_000_000
DONATION_QU_FOREVER = 100_000_000

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


@router.patch("/events/{event_id}/note", status_code=204)
def update_event_note(event_id: str, body: EventNoteUpdate, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id, Event.wallet_id == body.wallet_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    event.note = body.note or None
    db.commit()


def _save_suppression(db: Session, until: str):
    row = db.query(AppSetting).filter(AppSetting.key == "donation_suppressed_until").first()
    if row:
        row.value = until
    else:
        db.add(AppSetting(key="donation_suppressed_until", value=until))
    db.commit()


@router.get("/events/donation-suppression")
def get_suppression(db: Session = Depends(get_db)):
    row = db.query(AppSetting).filter(AppSetting.key == "donation_suppressed_until").first()
    return {"suppressed_until": row.value if row else None}


@router.get("/events/donation-check")
async def donation_check(db: Session = Depends(get_db)):
    from datetime import datetime, timezone, timedelta
    from ...services.qubic_client import RPCClient

    # Collect user wallet addresses
    user_wallets = db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()
    all_addresses = {w.id for w in user_wallets}

    # If the donation address itself is registered as a wallet → owner mode, no blockchain check needed
    if DONATION_ADDRESS in all_addresses:
        _save_suppression(db, "2099-12-31")
        return {"total_qu": 0, "months_earned": 0, "suppressed_until": "2099-12-31",
                "donation_address": DONATION_ADDRESS, "forever": True}

    user_addresses = all_addresses

    if not user_addresses:
        return {"total_qu": 0, "months_earned": 0, "suppressed_until": None, "donation_address": DONATION_ADDRESS}

    # Query blockchain: all transfers involving the donation address
    rpc = RPCClient()
    try:
        current_tick = await rpc.get_current_tick()
    except Exception:
        return {"total_qu": 0, "months_earned": 0, "suppressed_until": None, "donation_address": DONATION_ADDRESS}

    from_tick = max(0, current_tick - 500_000)

    all_transactions = []
    page = 1
    while True:
        try:
            data = await rpc.get_transfer_transactions(DONATION_ADDRESS, from_tick, current_tick, page=page, page_size=100)
        except Exception:
            break
        txs = data.get("transactions") or []
        if not txs:
            break
        all_transactions.extend(txs)
        total_pages = data.get("pagination", {}).get("totalPages", 1)
        if page >= total_pages:
            break
        page += 1

    # Filter: source must be a registered user wallet, destination must be donation address
    payments: list[tuple[int, int]] = []  # (tick, amount)
    for tx in all_transactions:
        source = tx.get("sourceId") or tx.get("source") or ""
        dest = tx.get("destId") or tx.get("destination") or ""
        amount = int(tx.get("amount", 0))
        tick = int(tx.get("tickNumber") or tx.get("tick") or 0)
        if source in user_addresses and dest == DONATION_ADDRESS and amount > 0:
            payments.append((tick, amount))

    if not payments:
        return {"total_qu": 0, "months_earned": 0, "suppressed_until": None, "donation_address": DONATION_ADDRESS}

    # Calculate suppression: sort by tick, accumulate months from each payment date
    payments.sort(key=lambda x: x[0])
    now = datetime.now(timezone.utc)

    # Ticks per day approximation (1 tick ≈ 1 second → 86400 ticks/day)
    TICKS_PER_DAY = 86_400
    suppressed_until_dt = now

    for tick, amount in payments:
        months = amount // DONATION_QU_PER_MONTH
        if months == 0:
            continue
        days_since_payment = max(0, (current_tick - tick) / TICKS_PER_DAY)
        payment_date = now - timedelta(days=days_since_payment)
        paid_until = payment_date + timedelta(days=30 * months)
        if paid_until > suppressed_until_dt:
            suppressed_until_dt = paid_until

    total_qu = sum(a for _, a in payments)
    months_earned = total_qu // DONATION_QU_PER_MONTH

    # 100M QU = forever
    if total_qu >= DONATION_QU_FOREVER:
        _save_suppression(db, "2099-12-31")
        last_tick, last_amount = max(payments, key=lambda x: x[0])
        days_since_last = max(0, (current_tick - last_tick) / TICKS_PER_DAY)
        last_payment_date = (now - timedelta(days=days_since_last)).date().isoformat()
        return {"total_qu": total_qu, "months_earned": int(months_earned), "suppressed_until": "2099-12-31",
                "donation_address": DONATION_ADDRESS, "forever": True,
                "last_payment_amount": last_amount, "last_payment_date": last_payment_date}

    suppressed_until = suppressed_until_dt.date().isoformat() if suppressed_until_dt > now else None

    last_tick, last_amount = max(payments, key=lambda x: x[0])
    days_since_last = max(0, (current_tick - last_tick) / TICKS_PER_DAY)
    last_payment_date = (now - timedelta(days=days_since_last)).date().isoformat()

    if suppressed_until:
        _save_suppression(db, suppressed_until)

    return {
        "total_qu": total_qu,
        "months_earned": int(months_earned),
        "suppressed_until": suppressed_until,
        "donation_address": DONATION_ADDRESS,
        "forever": False,
        "last_payment_amount": last_amount,
        "last_payment_date": last_payment_date,
    }


@router.get("/events/donation-top")
async def donation_top():
    from datetime import datetime, timezone, timedelta
    from collections import defaultdict
    from ...services.qubic_client import RPCClient

    rpc = RPCClient()
    try:
        current_tick = await rpc.get_current_tick()
    except Exception:
        return {"donors": []}

    from_tick = max(0, current_tick - 500_000)
    all_transactions = []
    page = 1
    while True:
        try:
            data = await rpc.get_transfer_transactions(DONATION_ADDRESS, from_tick, current_tick, page=page, page_size=100)
        except Exception:
            break
        txs = data.get("transactions") or []
        if not txs:
            break
        all_transactions.extend(txs)
        total_pages = data.get("pagination", {}).get("totalPages", 1)
        if page >= total_pages:
            break
        page += 1

    now = datetime.now(timezone.utc)
    TICKS_PER_DAY = 86_400
    donors: dict = defaultdict(lambda: {"total_qu": 0, "last_tick": 0})

    for tx in all_transactions:
        source = tx.get("sourceId") or tx.get("source") or ""
        dest = tx.get("destId") or tx.get("destination") or ""
        amount = int(tx.get("amount", 0))
        tick = int(tx.get("tickNumber") or tx.get("tick") or 0)
        if dest == DONATION_ADDRESS and amount > 0 and source:
            donors[source]["total_qu"] += amount
            if tick > donors[source]["last_tick"]:
                donors[source]["last_tick"] = tick

    result = []
    for address, d in donors.items():
        days_since = max(0, (current_tick - d["last_tick"]) / TICKS_PER_DAY)
        date = (now - timedelta(days=days_since)).date().isoformat()
        result.append({"address": address, "total_qu": d["total_qu"], "date": date})

    result.sort(key=lambda x: x["total_qu"], reverse=True)
    return {"donors": result[:20]}


@router.get("/events/donation-history")
async def donation_history(mine_only: bool = False, db: Session = Depends(get_db)):
    from datetime import datetime, timezone, timedelta
    from ...services.qubic_client import RPCClient

    user_addresses: set | None = None
    if mine_only:
        user_wallets = db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()
        user_addresses = {w.id for w in user_wallets}
        if not user_addresses:
            return {"transactions": [], "total_qu": 0}

    rpc = RPCClient()
    try:
        current_tick = await rpc.get_current_tick()
    except Exception:
        return {"transactions": [], "total_qu": 0}

    from_tick = max(0, current_tick - 500_000)
    all_transactions = []
    page = 1
    while True:
        try:
            data = await rpc.get_transfer_transactions(DONATION_ADDRESS, from_tick, current_tick, page=page, page_size=100)
        except Exception:
            break
        txs = data.get("transactions") or []
        if not txs:
            break
        all_transactions.extend(txs)
        total_pages = data.get("pagination", {}).get("totalPages", 1)
        if page >= total_pages:
            break
        page += 1

    now = datetime.now(timezone.utc)
    TICKS_PER_DAY = 86_400
    result = []
    total_qu = 0

    for tx in all_transactions:
        source = tx.get("sourceId") or tx.get("source") or ""
        dest = tx.get("destId") or tx.get("destination") or ""
        amount = int(tx.get("amount", 0))
        tick = int(tx.get("tickNumber") or tx.get("tick") or 0)
        if dest == DONATION_ADDRESS and amount > 0 and source:
            if user_addresses is not None and source not in user_addresses:
                continue
            days_since = max(0, (current_tick - tick) / TICKS_PER_DAY)
            date = (now - timedelta(days=days_since)).date().isoformat()
            result.append({"address": source, "amount": amount, "tick": tick, "date": date})
            total_qu += amount

    result.sort(key=lambda x: x["tick"], reverse=True)
    return {"transactions": result, "total_qu": total_qu}
