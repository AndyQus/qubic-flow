"""Balance snapshot capture for the Bestandsverlauf feature.

Three series (hourly / daily / weekly) capture the live balance of every
active wallet plus rates and cumulative transfer totals. Each row stores the
delta versus the previous row of the same series+wallet — mirroring the
user's manual Wednesday ledger where every epoch row holds the newly added
QUBIC per wallet.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import settings as app_config
from ..database import SessionLocal
from ..models.balance_snapshot import BalanceSnapshot
from ..models.settings import AppSetting
from ..models.wallet import Wallet
from ..models.event import Event
from ..utils.time import now_utc_iso
from .coingecko import get_live_price, get_price_for_date

logger = logging.getLogger(__name__)

KINDS = ("hourly", "daily", "weekly")

# Capture series default OFF in production installs — every user enables the
# series they want. In local development all three are pre-enabled for testing.
_IS_DEV = app_config.app_env.lower() in ("development", "dev")
_SERIES_DEFAULT = "true" if _IS_DEV else "false"

SETTING_DEFAULTS = {
    "bh_hourly_enabled": _SERIES_DEFAULT,
    "bh_daily_enabled": _SERIES_DEFAULT,
    "bh_weekly_enabled": _SERIES_DEFAULT,
    "bh_excel_autoexport": "true",
    "bh_hourly_retention_days": "0",  # 0 = keep forever
    "bh_export_lang": "de",
}

# Weekly capture polls for the new epoch for at most 2 hours after 12:00 UTC.
EPOCH_POLL_INTERVAL_SECONDS = 120
EPOCH_POLL_MAX_SECONDS = 2 * 60 * 60


def get_bh_settings(db: Session) -> dict:
    rows = {
        r.key: r.value
        for r in db.query(AppSetting).filter(AppSetting.key.in_(SETTING_DEFAULTS.keys())).all()
    }
    out = {}
    for key, default in SETTING_DEFAULTS.items():
        out[key] = rows.get(key, default)
    return out


def save_bh_settings(db: Session, values: dict) -> dict:
    for key in SETTING_DEFAULTS:
        if key not in values or values[key] is None:
            continue
        val = str(values[key]).lower() if isinstance(values[key], bool) else str(values[key])
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = val
        else:
            db.add(AppSetting(key=key, value=val))
    db.commit()
    return get_bh_settings(db)


def _enabled(settings_map: dict, kind: str) -> bool:
    return settings_map.get(f"bh_{kind}_enabled", "true") == "true"


def bucket_for(kind: str, now: datetime, epoch: int | None) -> str:
    if kind == "hourly":
        return now.strftime("%Y-%m-%dT%H")
    if kind == "daily":
        return now.strftime("%Y-%m-%d")
    # weekly: the epoch number is the natural slot; date as fallback
    return f"e{epoch}" if epoch is not None else f"w{now.strftime('%Y-%m-%d')}"


def _previous_snapshot(db: Session, kind: str, wallet_id: str) -> BalanceSnapshot | None:
    """Last measured row of the series for the wallet (user rows are deltas
    entered by hand without a balance — they cannot serve as baseline)."""
    return (
        db.query(BalanceSnapshot)
        .filter(
            BalanceSnapshot.kind == kind,
            BalanceSnapshot.wallet_id == wallet_id,
            BalanceSnapshot.trigger.in_(("auto", "manual")),
            BalanceSnapshot.balance.isnot(None),
        )
        .order_by(BalanceSnapshot.captured_at.desc(), BalanceSnapshot.id.desc())
        .first()
    )


async def _resolve_rates(db: Session, now: datetime) -> tuple[float | None, float | None]:
    live = await get_live_price()
    eur, usd = live.get("eur"), live.get("usd")
    if eur is None or usd is None:
        daily = await get_price_for_date(db, now.strftime("%Y-%m-%d"))
        eur = eur if eur is not None else daily.get("eur")
        usd = usd if usd is not None else daily.get("usd")
    return eur, usd


async def capture_snapshots(kind: str, trigger: str = "auto", export: bool = True) -> dict:
    """Capture one snapshot row per active wallet for the given series.

    Manual button captures join the hourly series (trigger='manual') with
    their own bucket so they never collide with the full-hour slot.
    With export=False the Excel regeneration is left to the caller (the API
    endpoint runs it as a background task so the response is not blocked).
    """
    from .sync_engine import _get_active_client, _get_rpc_client

    if kind not in KINDS:
        raise ValueError(f"unknown snapshot kind: {kind}")

    db = SessionLocal()
    try:
        settings_map = get_bh_settings(db)
        if trigger == "auto" and not _enabled(settings_map, kind):
            logger.debug(f"balance snapshot {kind} skipped (disabled)")
            return {"kind": kind, "skipped": True, "captured": 0}

        now = datetime.now(timezone.utc)
        now_iso = now_utc_iso()

        rpc = _get_rpc_client(db)
        epoch = await rpc.get_current_epoch()
        if epoch is None:
            epoch = db.query(Event.epoch).filter(Event.epoch.isnot(None)).order_by(Event.epoch.desc()).limit(1).scalar()

        if trigger == "manual":
            bucket = f"m{int(now.timestamp() * 1000)}"
        else:
            bucket = bucket_for(kind, now, epoch)

        existing = (
            db.query(BalanceSnapshot.wallet_id)
            .filter(BalanceSnapshot.kind == kind, BalanceSnapshot.bucket == bucket)
            .all()
        )
        already = {w for (w,) in existing}

        eur_rate, usd_rate = await _resolve_rates(db, now)

        fallback = _get_active_client(db)
        wallets = db.query(Wallet).filter(Wallet.active == 1, Wallet.deleted_at.is_(None)).all()
        pending = [w for w in wallets if w.id not in already]
        pending_count = len(pending)

        # Fetch all balances concurrently (bounded) — with many wallets a
        # sequential loop makes the manual capture button feel stuck.
        sem = asyncio.Semaphore(5)

        async def _fetch(wallet):
            async with sem:
                try:
                    info = await rpc.get_balance_info(wallet.id)
                    if info is not None:
                        return wallet, info, "rpc"
                    if fallback is not rpc:
                        info = await fallback.get_balance_info(wallet.id)
                        if info is not None:
                            return wallet, info, "bob"
                except Exception as e:
                    logger.warning(f"balance snapshot {kind}: fetch failed for {wallet.id}: {e}")
                return wallet, None, None

        results = await asyncio.gather(*(_fetch(w) for w in pending))

        captured = 0
        for wallet, info, source in results:
            try:
                if info is None or info.get("balance") is None:
                    logger.warning(f"balance snapshot {kind}: no balance for {wallet.id}")
                    continue

                prev = _previous_snapshot(db, kind, wallet.id)
                balance = info["balance"]
                delta = balance - prev.balance if prev is not None else None
                in_amount = out_amount = None
                if prev is not None and prev.in_total is not None and info.get("in_total") is not None:
                    in_amount = info["in_total"] - prev.in_total
                if prev is not None and prev.out_total is not None and info.get("out_total") is not None:
                    out_amount = info["out_total"] - prev.out_total

                db.add(BalanceSnapshot(
                    kind=kind,
                    bucket=bucket,
                    trigger=trigger,
                    captured_at=now_iso,
                    range_from=prev.captured_at if prev is not None else None,
                    range_to=now_iso,
                    wallet_id=wallet.id,
                    label=wallet.label,
                    owner=wallet.owner,
                    balance=balance,
                    delta=delta,
                    in_total=info.get("in_total"),
                    out_total=info.get("out_total"),
                    in_amount=in_amount,
                    out_amount=out_amount,
                    tick=info.get("valid_for_tick"),
                    epoch=epoch,
                    eur_rate=eur_rate,
                    usd_rate=usd_rate,
                    value_eur=round(balance * eur_rate, 6) if eur_rate is not None else None,
                    value_usd=round(balance * usd_rate, 6) if usd_rate is not None else None,
                    source=source,
                    edited=0,
                    created_at=now_iso,
                ))
                captured += 1
            except Exception as e:
                logger.warning(f"balance snapshot {kind} failed for {wallet.id}: {e}")

        if captured:
            db.commit()
        logger.info(f"balance snapshot {kind} ({trigger}): captured {captured}/{len(wallets)} wallets, bucket={bucket}")

        # Only this series' file changed — regenerating the other two would
        # triple the work for nothing.
        if export and captured and settings_map.get("bh_excel_autoexport", "true") == "true":
            try:
                from .excel_workbook_service import write_workbooks
                await asyncio.to_thread(write_workbooks, [kind])
            except Exception as e:
                logger.warning(f"excel auto export after {kind} snapshot failed: {e}")

        return {"kind": kind, "skipped": False, "captured": captured,
                "pending": pending_count, "bucket": bucket}
    finally:
        db.close()


async def capture_with_retry(kind: str, trigger: str = "auto",
                             attempts: int = 6, delay_seconds: int = 600) -> dict:
    """Capture with retries for the daily/weekly slots: if RPC and BOB are
    both unreachable at the scheduled time, nothing is captured — retry a few
    times instead of losing the whole day/week row. The delta chain still
    bridges any gap that remains (the next capture carries the full change)."""
    result: dict = {}
    for attempt in range(attempts):
        result = await capture_snapshots(kind, trigger=trigger)
        if result.get("skipped") or result.get("captured", 0) > 0 or result.get("pending", 0) == 0:
            return result
        if attempt < attempts - 1:
            logger.warning(
                f"balance snapshot {kind}: nothing captured "
                f"(attempt {attempt + 1}/{attempts}, nodes unreachable?) — retry in {delay_seconds}s"
            )
            await asyncio.sleep(delay_seconds)
    return result


def _last_weekly_epoch(db: Session) -> int | None:
    row = (
        db.query(BalanceSnapshot.epoch)
        .filter(BalanceSnapshot.kind == "weekly", BalanceSnapshot.epoch.isnot(None))
        .order_by(BalanceSnapshot.epoch.desc())
        .limit(1)
        .scalar()
    )
    return int(row) if row is not None else None


async def capture_weekly_after_epoch() -> dict:
    """Wednesday 12:00 UTC job: wait until the RPC actually reports the new
    epoch, then capture. Falls back to capturing anyway after the poll window
    so the Wednesday row is never lost entirely."""
    from .sync_engine import _get_rpc_client

    db = SessionLocal()
    try:
        settings_map = get_bh_settings(db)
        if not _enabled(settings_map, "weekly"):
            return {"kind": "weekly", "skipped": True, "captured": 0}
        last_epoch = _last_weekly_epoch(db)
        rpc = _get_rpc_client(db)
    finally:
        db.close()

    waited = 0
    while True:
        epoch_now = await rpc.get_current_epoch()
        if last_epoch is None and epoch_now is not None:
            break  # first weekly capture — baseline, no transition to wait for
        if epoch_now is not None and last_epoch is not None and epoch_now > last_epoch:
            break
        if waited >= EPOCH_POLL_MAX_SECONDS:
            logger.warning(
                f"weekly snapshot: epoch transition not observed after {waited}s "
                f"(last={last_epoch}, current={epoch_now}) — capturing anyway"
            )
            break
        await asyncio.sleep(EPOCH_POLL_INTERVAL_SECONDS)
        waited += EPOCH_POLL_INTERVAL_SECONDS

    return await capture_with_retry("weekly", trigger="auto")


async def apply_hourly_retention() -> int:
    """Delete hourly auto/manual rows older than the configured retention.
    User-entered rows are never deleted. Returns number of deleted rows."""
    db = SessionLocal()
    try:
        settings_map = get_bh_settings(db)
        try:
            days = int(settings_map.get("bh_hourly_retention_days", "0"))
        except ValueError:
            days = 0
        if days <= 0:
            return 0
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        deleted = (
            db.query(BalanceSnapshot)
            .filter(
                BalanceSnapshot.kind == "hourly",
                BalanceSnapshot.trigger.in_(("auto", "manual")),
                BalanceSnapshot.captured_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted:
            logger.info(f"hourly snapshot retention: deleted {deleted} rows older than {days}d")
        return deleted
    finally:
        db.close()


def reset_series(db: Session, kind: str) -> int:
    """Delete ALL captures of one series (including manual records and
    annotations) — full restart of that series. The Excel file of the series
    is regenerated empty by the caller. Returns number of deleted rows."""
    from ..models.balance_snapshot import SnapshotAnnotation

    if kind not in KINDS:
        raise ValueError(f"unknown snapshot kind: {kind}")
    deleted = (
        db.query(BalanceSnapshot)
        .filter(BalanceSnapshot.kind == kind)
        .delete(synchronize_session=False)
    )
    db.query(SnapshotAnnotation).filter(SnapshotAnnotation.kind == kind).delete(synchronize_session=False)
    db.commit()
    logger.info(f"balance snapshot series {kind} reset: deleted {deleted} rows")
    return deleted


def apply_edit(db: Session, snap: BalanceSnapshot, changes: dict) -> BalanceSnapshot:
    """Apply a user edit to a snapshot row. The first edit preserves the
    original measured values in original_json (audit trail)."""
    editable = ("balance", "delta", "in_amount", "out_amount", "eur_rate", "usd_rate")
    relevant = {k: v for k, v in changes.items() if k in editable}
    if not relevant:
        return snap

    if not snap.edited:
        snap.original_json = json.dumps({k: getattr(snap, k) for k in editable})
        snap.edited = 1

    for key, value in relevant.items():
        setattr(snap, key, value)

    if snap.balance is not None and snap.eur_rate is not None:
        snap.value_eur = round(snap.balance * snap.eur_rate, 6)
    if snap.balance is not None and snap.usd_rate is not None:
        snap.value_usd = round(snap.balance * snap.usd_rate, 6)
    db.commit()
    db.refresh(snap)
    return snap
