import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .health_monitor import check_nodes
from .sync_engine import sync_all_wallets

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

scheduler.add_job(
    sync_all_wallets,
    "interval",
    seconds=60,
    id="sync_all_wallets",
    max_instances=1,
    coalesce=True,
)

scheduler.add_job(
    check_nodes,
    "interval",
    seconds=30,
    id="health_monitor",
    max_instances=1,
    coalesce=True,
)


async def weekly_snapshot():
    logger.info("Weekly snapshot - not yet implemented")


scheduler.add_job(
    weekly_snapshot,
    CronTrigger(day_of_week="wed", hour=12, minute=0, timezone="UTC"),
    id="weekly_snapshot",
    max_instances=1,
)
