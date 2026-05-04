import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from ..database import SessionLocal
from ..models.donor_cache import DonorCache
from ..models.settings import AppSetting

logger = logging.getLogger(__name__)

DONATION_ADDRESS = "CCCJKFMDTUFFWDCRBFNHMQRYOBABEKBDUZWEJMARUETQPTFZWBCJLYUGREXI"
DONATION_QU_PER_MONTH = 1_000_000
DONATION_QU_FOREVER = 100_000_000
TICKS_PER_DAY = 86_400


def _parse_v2_transfers(pages: list[dict]) -> list[tuple[int, str, str, int]]:
    result = []
    for page_data in pages:
        for tick_group in (page_data.get("transactions") or []):
            tick_number = int(tick_group.get("tickNumber") or 0)
            for tx_data in (tick_group.get("transactions") or []):
                if not tx_data.get("moneyFlew", False):
                    continue
                tx = tx_data.get("transaction") or tx_data
                source = tx.get("sourceId") or tx.get("source") or ""
                dest   = tx.get("destId")   or tx.get("destination") or ""
                amount = int(tx.get("amount") or 0)
                if source and dest and amount > 0:
                    result.append((tick_number, source, dest, amount))
    return result


async def _fetch_all_transfer_pages(rpc, address: str, from_tick: int, to_tick: int) -> list[dict]:
    pages = []
    page = 1
    while True:
        try:
            data = await rpc.get_transfer_transactions(address, from_tick, to_tick, page=page, page_size=100)
        except Exception:
            break
        pages.append(data)
        tick_groups = data.get("transactions") or []
        if not tick_groups:
            break
        total_pages = data.get("pagination", {}).get("totalPages", 1)
        if page >= total_pages:
            break
        page += 1
    return pages


async def refresh_donation_cache() -> None:
    from ..services.qubic_client import RPCClient

    rpc = RPCClient()
    try:
        current_tick = await rpc.get_current_tick()
    except Exception as e:
        logger.warning(f"donation_cache: could not get current tick: {e}")
        return

    try:
        pages = await _fetch_all_transfer_pages(rpc, DONATION_ADDRESS, 0, current_tick)
    except Exception as e:
        logger.warning(f"donation_cache: transfer fetch failed: {e}")
        return

    transfers = _parse_v2_transfers(pages)

    now = datetime.now(timezone.utc)
    donors: dict = defaultdict(lambda: {"total_qu": 0, "last_tick": 0, "payments": []})

    for tick, source, dest, amount in transfers:
        if dest == DONATION_ADDRESS and source:
            donors[source]["total_qu"] += amount
            donors[source]["payments"].append((tick, amount))
            if tick > donors[source]["last_tick"]:
                donors[source]["last_tick"] = tick

    db = SessionLocal()
    try:
        updated_at = now.isoformat()

        for address, d in donors.items():
            total_qu = d["total_qu"]
            last_tick = d["last_tick"]
            payments = d["payments"]

            days_since_last = max(0, (current_tick - last_tick) / TICKS_PER_DAY)
            last_date = (now - timedelta(days=days_since_last)).date().isoformat()

            # Calculate suppressed_until
            forever = total_qu >= DONATION_QU_FOREVER
            if forever:
                suppressed_until = "2099-12-31"
            else:
                suppressed_until_dt = now
                for tick, amount in sorted(payments, key=lambda x: x[0]):
                    months = amount // DONATION_QU_PER_MONTH
                    if months == 0:
                        continue
                    days_since_pay = max(0, (current_tick - tick) / TICKS_PER_DAY)
                    payment_date = now - timedelta(days=days_since_pay)
                    paid_until = payment_date + timedelta(days=30 * months)
                    if paid_until > suppressed_until_dt:
                        suppressed_until_dt = paid_until
                suppressed_until = (
                    suppressed_until_dt.date().isoformat()
                    if suppressed_until_dt > now else None
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

        # Remove addresses that no longer appear (edge case)
        known = set(donors.keys())
        db.query(DonorCache).filter(DonorCache.address.notin_(known)).delete(synchronize_session=False)

        # Store last refresh timestamp
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
