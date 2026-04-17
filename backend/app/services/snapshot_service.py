import logging
from datetime import datetime, timezone
from sqlalchemy import func
from ..database import SessionLocal
from ..models.event import Event
from ..models.snapshot import WeeklySnapshot
from ..utils.time import now_utc_iso

logger = logging.getLogger(__name__)


def create_snapshot():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        iso_year, iso_week, _ = now.isocalendar()

        epoch_row = db.query(func.max(Event.epoch)).scalar()
        tx_count = db.query(func.count(Event.id)).filter(Event.source_type == "TX").scalar() or 0
        event_count = db.query(func.count(Event.id)).filter(Event.source_type == "EVENT").scalar() or 0
        volume_qubic = db.query(func.coalesce(func.sum(Event.amount_qubic), 0)).scalar() or 0
        volume_eur = db.query(
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_eur_rate), 0.0)
        ).scalar() or 0.0
        volume_usd = db.query(
            func.coalesce(func.sum(Event.amount_qubic * Event.qubic_usd_rate), 0.0)
        ).scalar() or 0.0

        snap = WeeklySnapshot(
            snapshot_at=now_utc_iso(),
            epoch=epoch_row or 0,
            week=iso_week,
            month=now.month,
            year=iso_year,
            tx_count=tx_count,
            event_count=event_count,
            volume_qubic=int(volume_qubic),
            volume_eur=float(volume_eur),
            volume_usd=float(volume_usd),
        )
        db.add(snap)
        db.commit()
        logger.info(f"Weekly snapshot created: epoch={snap.epoch} week={snap.week} events={event_count}")
    finally:
        db.close()
