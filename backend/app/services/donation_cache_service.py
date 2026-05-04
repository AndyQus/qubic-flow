import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from ..database import SessionLocal
from ..models.donor_cache import DonorCache
from ..models.settings import AppSetting
from .donation_utils import (
    DONATION_ADDRESS, DONATION_QU_PER_MONTH, DONATION_QU_FOREVER,
    TICKS_PER_DAY, parse_v2_transfers, fetch_all_transfer_pages,
)

logger = logging.getLogger(__name__)


async def refresh_donation_cache() -> None:
    from .qubic_client import RPCClient

    rpc = RPCClient()
    try:
        current_tick = await rpc.get_current_tick()
    except Exception as e:
        logger.warning(f"donation_cache: could not get current tick: {e}")
        return

    try:
        pages = await fetch_all_transfer_pages(rpc, DONATION_ADDRESS, 0, current_tick)
    except Exception as e:
        logger.warning(f"donation_cache: transfer fetch failed: {e}")
        return

    transfers = parse_v2_transfers(pages)

    now = datetime.now(timezone.utc)
    donors: dict = defaultdict(lambda: {"total_qu": 0, "last_tick": 0, "payments": []})

    for tick, source, dest, amount in transfers:
        if dest == DONATION_ADDRESS and source:
            donors[source]["total_qu"] += amount
            donors[source]["payments"].append((tick, amount))
            if tick > donors[source]["last_tick"]:
                donors[source]["last_tick"] = tick

    if not donors:
        logger.info("donation_cache: no transfers found, skipping DB update")
        return

    db = SessionLocal()
    try:
        updated_at = now.isoformat()

        for address, d in donors.items():
            total_qu = d["total_qu"]
            last_tick = d["last_tick"]
            payments = d["payments"]

            days_since_last = max(0, (current_tick - last_tick) / TICKS_PER_DAY)
            last_date = (now - timedelta(days=days_since_last)).date().isoformat()

            forever = total_qu >= DONATION_QU_FOREVER
            if forever:
                suppressed_until = "2099-12-31"
            else:
                suppressed_until_dt = None
                for tick, amount in sorted(payments, key=lambda x: x[0]):
                    months = amount // DONATION_QU_PER_MONTH
                    if months == 0:
                        continue
                    days_since_pay = max(0, (current_tick - tick) / TICKS_PER_DAY)
                    payment_date = now - timedelta(days=days_since_pay)
                    paid_until = payment_date + timedelta(days=30 * months)
                    if suppressed_until_dt is None or paid_until > suppressed_until_dt:
                        suppressed_until_dt = paid_until
                suppressed_until = (
                    suppressed_until_dt.date().isoformat()
                    if suppressed_until_dt is not None and suppressed_until_dt > now
                    else None
                )

            row = db.query(DonorCache).filter(DonorCache.address == address).first()
            if row:
                row.total_qu = total_qu
                row.last_date = last_date
                row.last_tick = last_tick
                row.suppressed_until = suppressed_until
                row.forever = 1 if forever else 0
                row.updated_at = updated_at
            else:
                db.add(DonorCache(
                    address=address,
                    total_qu=total_qu,
                    last_date=last_date,
                    last_tick=last_tick,
                    suppressed_until=suppressed_until,
                    forever=1 if forever else 0,
                    updated_at=updated_at,
                ))

        # Only remove addresses that truly no longer appear (full fetch succeeded)
        known = set(donors.keys())
        db.query(DonorCache).filter(DonorCache.address.notin_(known)).delete(synchronize_session=False)

        setting = db.query(AppSetting).filter(AppSetting.key == "donation_cache_updated_at").first()
        if setting:
            setting.value = updated_at
        else:
            db.add(AppSetting(key="donation_cache_updated_at", value=updated_at))

        db.commit()
        logger.info(f"donation_cache: refreshed {len(donors)} donors (tick {current_tick})")
    except Exception as e:
        db.rollback()
        logger.error(f"donation_cache: DB write failed: {e}")
    finally:
        db.close()
