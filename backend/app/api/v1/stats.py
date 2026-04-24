from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from datetime import datetime, timezone, timedelta
from ...database import get_db
from ...models.event import Event
from ...models.snapshot import WeeklySnapshot

router = APIRouter()


@router.get("/stats/current")
def current_stats(
    wallet_ids: List[str] = Query(default=[]),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    prev_hour_start = hour_start - timedelta(hours=1)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    prev_day_start = day_start - timedelta(days=1)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_end = month_start - timedelta(seconds=1)
    prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_year_start = year_start.replace(year=year_start.year - 1)

    current_epoch = db.query(func.max(Event.epoch)).scalar() or 0
    prev_epoch = max(0, current_epoch - 1)

    def base_q():
        q = db.query(Event)
        if wallet_ids:
            q = q.filter(Event.wallet_id.in_(wallet_ids))
        return q

    def between(s, e):
        q = base_q().with_entities(
            func.count(Event.id),
            func.coalesce(func.sum(Event.amount_qubic), 0),
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_eur_rate), 0.0),
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_usd_rate), 0.0),
            func.sum(func.iif(Event.source_type == "TX",    1, 0)),
            func.sum(func.iif(Event.source_type == "EVENT", 1, 0)),
        ).filter(Event.timestamp >= s, Event.timestamp < e)
        c, vq, ve, vu, tx_c, ev_c = q.one()
        return {"count": int(c or 0), "volume_qubic": int(vq or 0),
                "volume_eur": float(ve or 0.0), "volume_usd": float(vu or 0.0),
                "tx_count": int(tx_c or 0), "event_count": int(ev_c or 0)}

    def by_epoch(ep):
        q = base_q().with_entities(
            func.count(Event.id),
            func.coalesce(func.sum(Event.amount_qubic), 0),
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_eur_rate), 0.0),
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_usd_rate), 0.0),
            func.sum(func.iif(Event.source_type == "TX",    1, 0)),
            func.sum(func.iif(Event.source_type == "EVENT", 1, 0)),
        ).filter(Event.epoch == ep)
        c, vq, ve, vu, tx_c, ev_c = q.one()
        return {"count": int(c or 0), "volume_qubic": int(vq or 0),
                "volume_eur": float(ve or 0.0), "volume_usd": float(vu or 0.0),
                "tx_count": int(tx_c or 0), "event_count": int(ev_c or 0)}

    return {
        "hour":  {"current": between(hour_start.isoformat(), now.isoformat()),
                  "previous": between(prev_hour_start.isoformat(), hour_start.isoformat())},
        "day":   {"current": between(day_start.isoformat(), now.isoformat()),
                  "previous": between(prev_day_start.isoformat(), day_start.isoformat())},
        "epoch": {"current": by_epoch(current_epoch), "previous": by_epoch(prev_epoch)},
        "month": {"current": between(month_start.isoformat(), now.isoformat()),
                  "previous": between(prev_month_start.isoformat(), month_start.isoformat())},
        "year":  {"current": between(year_start.isoformat(), now.isoformat()),
                  "previous": between(prev_year_start.isoformat(), year_start.isoformat())},
    }


@router.get("/stats/snapshots")
def snapshots(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(WeeklySnapshot).order_by(desc(WeeklySnapshot.snapshot_at)).limit(limit).all()


@router.get("/stats/epochs")
def epochs_breakdown(db: Session = Depends(get_db)):
    """Per-epoch breakdown, aggregated per wallet.

    Returns a list of epochs (desc) with per-wallet rows containing total events,
    incoming events/volume (destination == wallet) and outgoing volume.
    """
    from ...models.wallet import Wallet

    in_match = Event.destination_addr == Event.wallet_id
    out_match = Event.source_address == Event.wallet_id
    in_tx = func.iif((Event.source_type == "TX") & in_match, Event.amount_qubic, 0)
    in_ev = func.iif((Event.source_type == "EVENT") & in_match, Event.amount_qubic, 0)
    out_tx = func.iif((Event.source_type == "TX") & out_match, Event.amount_qubic, 0)
    out_ev = func.iif((Event.source_type == "EVENT") & out_match, Event.amount_qubic, 0)
    rows = (
        db.query(
            Event.epoch.label("epoch"),
            Event.wallet_id.label("wallet_id"),
            func.count(Event.id).label("events"),
            func.sum(func.iif(in_match, 1, 0)).label("in_events"),
            func.sum(func.iif((Event.source_type == "TX") & in_match, 1, 0)).label("in_tx_count"),
            func.sum(func.iif((Event.source_type == "EVENT") & in_match, 1, 0)).label("in_event_count"),
            func.coalesce(
                func.sum(func.iif(in_match, Event.amount_qubic, 0)), 0
            ).label("in_qubic"),
            func.coalesce(func.sum(in_tx), 0).label("in_qubic_tx"),
            func.coalesce(func.sum(in_ev), 0).label("in_qubic_event"),
            func.sum(func.iif((Event.source_type == "TX") & out_match, 1, 0)).label("out_tx_count"),
            func.sum(func.iif((Event.source_type == "EVENT") & out_match, 1, 0)).label("out_event_count"),
            func.coalesce(
                func.sum(func.iif(out_match, Event.amount_qubic, 0)), 0
            ).label("out_qubic"),
            func.coalesce(func.sum(out_tx), 0).label("out_qubic_tx"),
            func.coalesce(func.sum(out_ev), 0).label("out_qubic_event"),
            func.coalesce(
                func.sum(func.iif(in_match, Event.amount_qubic * Event.qubic_eur_rate, 0.0)), 0.0
            ).label("in_eur"),
            func.coalesce(
                func.sum(func.iif(in_match, Event.amount_qubic * Event.qubic_usd_rate, 0.0)), 0.0
            ).label("in_usd"),
        )
        .join(Wallet, Wallet.id == Event.wallet_id)
        .filter(Event.epoch.isnot(None), Wallet.deleted_at.is_(None))
        .group_by(Event.epoch, Event.wallet_id)
        .order_by(desc(Event.epoch), Event.wallet_id)
        .all()
    )

    by_epoch: dict[int, dict] = {}
    for r in rows:
        bucket = by_epoch.setdefault(r.epoch, {
            "epoch": int(r.epoch),
            "totals": {"events": 0, "in_events": 0,
                       "in_tx_count": 0, "in_event_count": 0,
                       "in_qubic": 0, "in_qubic_tx": 0, "in_qubic_event": 0,
                       "out_tx_count": 0, "out_event_count": 0,
                       "out_qubic": 0, "out_qubic_tx": 0, "out_qubic_event": 0,
                       "in_eur": 0.0, "in_usd": 0.0,
                       "wallet_count": 0, "wallets_with_in": 0},
            "wallets": [],
        })
        in_q = int(r.in_qubic or 0)
        in_q_tx = int(r.in_qubic_tx or 0)
        in_q_ev = int(r.in_qubic_event or 0)
        out_q = int(r.out_qubic or 0)
        out_q_tx = int(r.out_qubic_tx or 0)
        out_q_ev = int(r.out_qubic_event or 0)
        bucket["wallets"].append({
            "wallet_id": r.wallet_id,
            "events": int(r.events or 0),
            "in_events": int(r.in_events or 0),
            "in_tx_count": int(r.in_tx_count or 0),
            "in_event_count": int(r.in_event_count or 0),
            "in_qubic": in_q,
            "in_qubic_tx": in_q_tx,
            "in_qubic_event": in_q_ev,
            "out_tx_count": int(r.out_tx_count or 0),
            "out_event_count": int(r.out_event_count or 0),
            "out_qubic": out_q,
            "out_qubic_tx": out_q_tx,
            "out_qubic_event": out_q_ev,
            "in_eur": float(r.in_eur or 0.0),
            "in_usd": float(r.in_usd or 0.0),
        })
        bucket["totals"]["events"] += int(r.events or 0)
        bucket["totals"]["in_events"] += int(r.in_events or 0)
        bucket["totals"]["in_tx_count"] += int(r.in_tx_count or 0)
        bucket["totals"]["in_event_count"] += int(r.in_event_count or 0)
        bucket["totals"]["in_qubic"] += in_q
        bucket["totals"]["in_qubic_tx"] += in_q_tx
        bucket["totals"]["in_qubic_event"] += in_q_ev
        bucket["totals"]["out_tx_count"] += int(r.out_tx_count or 0)
        bucket["totals"]["out_event_count"] += int(r.out_event_count or 0)
        bucket["totals"]["out_qubic"] += out_q
        bucket["totals"]["out_qubic_tx"] += out_q_tx
        bucket["totals"]["out_qubic_event"] += out_q_ev
        bucket["totals"]["in_eur"] += float(r.in_eur or 0.0)
        bucket["totals"]["in_usd"] += float(r.in_usd or 0.0)
        bucket["totals"]["wallet_count"] += 1
        if in_q > 0:
            bucket["totals"]["wallets_with_in"] += 1

    return sorted(by_epoch.values(), key=lambda b: b["epoch"], reverse=True)


@router.get("/stats/history")
def history(
    group_by: str = "week",
    wallet_ids: List[str] = Query(default=[]),
    db: Session = Depends(get_db),
):
    if group_by == "month":
        period_expr = func.strftime("%Y-%m", Event.timestamp)
    else:
        period_expr = func.strftime("%Y-%W", Event.timestamp)

    q = db.query(
        period_expr.label("period"),
        func.count(Event.id).label("count"),
        func.sum(func.iif(Event.source_type == "TX",    1, 0)).label("tx_count"),
        func.sum(func.iif(Event.source_type == "EVENT", 1, 0)).label("event_count"),
        func.coalesce(func.sum(Event.amount_qubic), 0).label("volume_qubic"),
        func.coalesce(func.sum(Event.amount_qubic * Event.qubic_eur_rate), 0.0).label("volume_eur"),
        func.coalesce(func.sum(Event.amount_qubic * Event.qubic_usd_rate), 0.0).label("volume_usd"),
    ).filter(Event.timestamp.isnot(None))

    if wallet_ids:
        q = q.filter(Event.wallet_id.in_(wallet_ids))

    rows = q.group_by("period").order_by("period").all()

    result = []
    for r in rows:
        period = r.period or ""
        base = {
            "count": r.count, "tx_count": r.tx_count or 0,
            "event_count": r.event_count or 0,
            "volume_qubic": int(r.volume_qubic or 0),
            "volume_eur": float(r.volume_eur or 0.0),
            "volume_usd": float(r.volume_usd or 0.0),
            "source": "live",
        }
        if group_by == "month" and len(period) == 7:
            result.append({**base, "period": period, "year": int(period[:4]), "month": int(period[5:]), "week": None})
        elif group_by == "week" and len(period) >= 7:
            result.append({**base, "period": period, "year": int(period[:4]), "week": int(period[5:]), "month": None})

    return result
