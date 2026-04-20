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
        ).filter(Event.timestamp >= s, Event.timestamp < e)
        c, vq, ve, vu = q.one()
        return {"count": int(c or 0), "volume_qubic": int(vq or 0),
                "volume_eur": float(ve or 0.0), "volume_usd": float(vu or 0.0)}

    def by_epoch(ep):
        q = base_q().with_entities(
            func.count(Event.id),
            func.coalesce(func.sum(Event.amount_qubic), 0),
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_eur_rate), 0.0),
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_usd_rate), 0.0),
        ).filter(Event.epoch == ep)
        c, vq, ve, vu = q.one()
        return {"count": int(c or 0), "volume_qubic": int(vq or 0),
                "volume_eur": float(ve or 0.0), "volume_usd": float(vu or 0.0)}

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
