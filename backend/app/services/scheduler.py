import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .health_monitor import check_nodes
from .sync_engine import sync_all_wallets, backfill_tx_epochs
from .snapshot_service import create_snapshot
from .label_service import sync_labels
from .coingecko import get_price_for_date
from .balance_service import check_all_balances
from ..database import SessionLocal
from ..models.event import Event

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

scheduler.add_job(sync_all_wallets, "interval", seconds=60, id="sync_all_wallets", max_instances=1, coalesce=True)
scheduler.add_job(check_nodes, "interval", seconds=30, id="health_monitor", max_instances=1, coalesce=True)


async def weekly_snapshot():
    await asyncio.to_thread(create_snapshot)


scheduler.add_job(
    weekly_snapshot,
    CronTrigger(day_of_week="wed", hour=12, minute=0, timezone="UTC"),
    id="weekly_snapshot",
    max_instances=1,
)


async def daily_sync_labels():
    db = SessionLocal()
    try:
        await sync_labels(db)
    finally:
        db.close()


scheduler.add_job(
    daily_sync_labels,
    "interval",
    hours=24,
    id="sync_labels",
    max_instances=1,
    coalesce=True,
    next_run_time=datetime.now(timezone.utc),
)


async def backfill_missing_rates():
    """Fetch EUR/USD rates for events that have none."""
    db = SessionLocal()
    try:
        events = db.query(Event).filter(
            Event.qubic_eur_rate == None,  # noqa: E711
            Event.timestamp != None,       # noqa: E711
        ).all()
        if not events:
            return
        logger.info(f"Backfilling rates for {len(events)} events without a rate")
        updated = 0
        for ev in events:
            try:
                date_str = ev.timestamp[:10]  # YYYY-MM-DD
            except Exception:
                continue
            prices = await get_price_for_date(db, date_str)
            eur = prices.get("eur")
            usd = prices.get("usd")
            if eur is not None:
                ev.qubic_eur_rate = eur
                ev.qubic_usd_rate = usd
                updated += 1
        if updated:
            db.commit()
            logger.info(f"Backfilled rates for {updated} events")
    except Exception as e:
        logger.error(f"backfill_missing_rates failed: {e}")
    finally:
        db.close()


scheduler.add_job(
    backfill_missing_rates,
    "interval",
    hours=6,
    id="backfill_rates",
    max_instances=1,
    coalesce=True,
    next_run_time=datetime.now(timezone.utc),
)


scheduler.add_job(
    check_all_balances,
    "interval",
    hours=1,
    id="check_balances",
    max_instances=1,
    coalesce=True,
    next_run_time=datetime.now(timezone.utc),
)


async def run_backfill_tx_epochs():
    db = SessionLocal()
    try:
        await backfill_tx_epochs(db)
    finally:
        db.close()


scheduler.add_job(
    run_backfill_tx_epochs,
    "interval",
    hours=1,
    id="backfill_tx_epochs",
    max_instances=1,
    coalesce=True,
    next_run_time=datetime.now(timezone.utc),
)
