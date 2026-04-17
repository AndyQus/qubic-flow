from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timezone, timedelta
from ...database import get_db
from ...models.event import Event
from ...models.snapshot import WeeklySnapshot

router = APIRouter()


def _aggregate(db: Session, since_iso: str) -> dict:
    q = db.query(
        func.count(Event.id),
        func.coalesce(func.sum(Event.amount_qubic), 0),
        func.coalesce(func.sum(Event.amount_qubic * Event.qubic_eur_rate), 0.0),
    ).filter(Event.timestamp >= since_iso)
    count, vol_q, vol_eur = q.one()
    return {
        "count": int(count or 0),
        "volume_qubic": int(vol_q or 0),
        "volume_eur": float(vol_eur or 0.0),
    }


@router.get("/stats/current")
def current_stats(db: Session = Depends(get_db)):
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

    def between(s, e):
        q = db.query(
            func.count(Event.id),
            func.coalesce(func.sum(Event.amount_qubic), 0),
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_eur_rate), 0.0),
        ).filter(Event.timestamp >= s, Event.timestamp < e)
        c, vq, ve = q.one()
        return {"count": int(c or 0), "volume_qubic": int(vq or 0), "volume_eur": float(ve or 0.0)}

    def by_epoch(ep):
        q = db.query(
            func.count(Event.id),
            func.coalesce(func.sum(Event.amount_qubic), 0),
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_eur_rate), 0.0),
        ).filter(Event.epoch == ep)
        c, vq, ve = q.one()
        return {"count": int(c or 0), "volume_qubic": int(vq or 0), "volume_eur": float(ve or 0.0)}

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
