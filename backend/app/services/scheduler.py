import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .health_monitor import check_nodes
from .sync_engine import sync_all_wallets
from .snapshot_service import create_snapshot
from .label_service import sync_labels
from ..database import SessionLocal

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
