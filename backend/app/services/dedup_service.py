"""Duplicate-event detection and automatic cleanup.

Two independent ingest paths write into `events`:

  * `_persist_logs`      - archiver getEventLogs (id = 60-char transactionHash,
                           or the numeric logId when the archiver gives none)
  * `_sync_transactions` - archiver getTransferTransactions (id = 60-char txId)

Because the *same on-chain transfer* can arrive through both paths under two
different ids, the TX path reconciles by upgrading an existing stub in place
instead of inserting. That reconciliation matches on
(wallet, tick, source, destination, amount) and takes `.first()`, so it is
one-stub-at-a-time: when a tick legitimately contains N identical transfers,
only one stub is upgraded per pass and the remaining stubs stay behind as
orphans that look exactly like the reconciled row.

`find_duplicate_groups` / `dedup_events` clean that up and are wired into the
scheduler so the database heals itself without any user interaction.

Identity used for a duplicate: two rows are the same on-chain movement when
they share wallet_id, tick_number, source_address, destination_addr and
amount_qubic. Rows carrying a real 60-char TxID are only merged with each other
when the TxID is *identical* - two distinct TxIDs in the same tick are two
genuinely distinct transfers and must both survive.
"""
import logging
from sqlalchemy import func, delete
from sqlalchemy.orm import Session

from ..models.event import Event
from ..models.qearn import EventSplit
from ..models.wallet import Wallet
from ..utils.time import now_utc_iso

logger = logging.getLogger(__name__)

# Columns holding user-entered data. When collapsing duplicates these are
# merged onto the survivor so manual work is never lost.
USER_COLUMNS = (
    "note", "comment", "item_id", "item_name", "trade_group",
    "buy_value_eur", "buy_value_usd", "sell_value_eur", "sell_value_usd",
    "buy_currency", "sell_currency",
)


def is_real_txid(value) -> bool:
    """True for the 60-char lowercase Qubic TxID format used by the explorer."""
    return isinstance(value, str) and len(value) == 60 and value.isalpha() and value.islower()


def _identity(ev: Event) -> tuple:
    """Grouping key for 'same on-chain movement'."""
    return (
        ev.wallet_id,
        ev.tick_number,
        ev.source_address,
        ev.destination_addr,
        ev.amount_qubic,
    )


def _has_user_data(ev: Event) -> bool:
    if ev.verified:
        return True
    return any(getattr(ev, col, None) not in (None, "") for col in USER_COLUMNS)


def _survivor_rank(ev: Event) -> tuple:
    """Lower sorts first - the row we keep.

    Preference order:
      1. rows with a real 60-char TxID (explorer-verifiable identity)
      2. rows the user has touched (note/comment/tags/verified)
      3. rows with an epoch resolved
      4. oldest created_at, then id, for a stable deterministic result
    """
    real = 1 if ev.reconstructed else 0  # a computed Qearn payout never beats on-chain data
    has_txid = 0 if is_real_txid(ev.id) else 1
    touched = 0 if _has_user_data(ev) else 1
    has_epoch = 0 if ev.epoch is not None else 1
    return (real, has_txid, touched, has_epoch, ev.created_at or "", ev.id or "")


def _split_by_txid(rows: list) -> list:
    """Split one identity group into sub-groups that are truly the same transfer.

    Rows with distinct real TxIDs are distinct transfers even though every other
    column matches - a wallet can legitimately send the identical amount to the
    identical address twice within one tick. Stubs without a real TxID are
    ambiguous, so at most one stub may remain per distinct TxID: each stub is
    attached to a TxID bucket, and any surplus stubs beyond the number of real
    transfers are the duplicates we remove.
    """
    with_txid = [r for r in rows if is_real_txid(r.id)]
    stubs = [r for r in rows if not is_real_txid(r.id)]

    buckets: list = []
    seen: dict = {}
    for r in with_txid:
        if r.id not in seen:
            seen[r.id] = []
            buckets.append(seen[r.id])
        seen[r.id].append(r)

    if not buckets:
        # No verifiable identity at all - all stubs describe one transfer.
        return [stubs] if stubs else []

    # Distribute stubs one per real transfer; surplus stubs are duplicates and
    # get folded into the first bucket so they are removed.
    for idx, stub in enumerate(stubs):
        buckets[min(idx, len(buckets) - 1)].append(stub)

    return buckets


def find_duplicate_groups(db: Session, wallet_id: str | None = None) -> list:
    """Return groups of rows representing the same on-chain movement.

    Each returned group has 2+ members; the first entry is the survivor.
    """
    dup_keys = db.query(
        Event.wallet_id, Event.tick_number, Event.source_address,
        Event.destination_addr, Event.amount_qubic,
    ).filter(Event.tick_number.isnot(None))
    if wallet_id:
        dup_keys = dup_keys.filter(Event.wallet_id == wallet_id)
    dup_keys = dup_keys.group_by(
        Event.wallet_id, Event.tick_number, Event.source_address,
        Event.destination_addr, Event.amount_qubic,
    ).having(func.count() > 1).all()

    if not dup_keys:
        return []

    key_set = {tuple(k) for k in dup_keys}

    # Fetch only the rows belonging to a colliding key. Restricting by the
    # affected ticks keeps this an index seek instead of loading the whole
    # table, which matters once a wallet has tens of thousands of events.
    ticks = {k[1] for k in key_set}
    groups: dict = {}
    tick_list = list(ticks)
    CHUNK = 500  # keep the IN(...) list within SQLite's variable limit
    for i in range(0, len(tick_list), CHUNK):
        q = db.query(Event).filter(Event.tick_number.in_(tick_list[i:i + CHUNK]))
        if wallet_id:
            q = q.filter(Event.wallet_id == wallet_id)
        for ev in q.all():
            key = _identity(ev)
            if key in key_set:
                groups.setdefault(key, []).append(ev)

    result = []
    for rows in groups.values():
        for bucket in _split_by_txid(rows):
            if len(bucket) > 1:
                bucket.sort(key=_survivor_rank)
                result.append(bucket)
    return result


def _merge_user_data(survivor: Event, losers: list) -> None:
    """Carry user-entered data from removed rows onto the survivor."""
    for col in USER_COLUMNS:
        if getattr(survivor, col, None) in (None, ""):
            for loser in losers:
                val = getattr(loser, col, None)
                if val not in (None, ""):
                    setattr(survivor, col, val)
                    break
    if not survivor.verified and any(l.verified for l in losers):
        survivor.verified = 1
    if survivor.epoch is None:
        for loser in losers:
            if loser.epoch is not None:
                survivor.epoch = loser.epoch
                break


def dedup_events(db: Session, wallet_id: str | None = None, dry_run: bool = False) -> dict:
    """Collapse duplicate events, correcting the tracked wallet balance.

    Returns a summary dict. With dry_run=True nothing is written.
    """
    groups = find_duplicate_groups(db, wallet_id)
    if not groups:
        return {
            "groups": 0, "removed": 0, "wallets": [],
            "balance_corrections": {}, "details": [], "dry_run": dry_run,
        }

    # Balance correction: removed rows had their amount applied to
    # wallet.balance at insert time, so subtract their effect back out.
    wallets = {w.id: w for w in db.query(Wallet).all()}
    balance_fix: dict = {}
    details = []
    removed_total = 0

    for group in groups:
        survivor, losers = group[0], group[1:]
        if not dry_run:
            _merge_user_data(survivor, losers)

        for loser in losers:
            wal = wallets.get(loser.wallet_id)
            if (
                wal is not None
                and wal.balance is not None
                and wal.balance_since_tick is not None
                and loser.tick_number is not None
                and loser.tick_number > wal.balance_since_tick
            ):
                amt = loser.amount_qubic or 0
                delta = 0
                if loser.destination_addr == loser.wallet_id:
                    delta -= amt
                if loser.source_address == loser.wallet_id:
                    delta += amt
                if delta:
                    balance_fix[loser.wallet_id] = balance_fix.get(loser.wallet_id, 0) + delta

        details.append({
            "wallet_id": survivor.wallet_id,
            "tick_number": survivor.tick_number,
            "amount_qubic": survivor.amount_qubic,
            "source_address": survivor.source_address,
            "destination_addr": survivor.destination_addr,
            "kept_id": survivor.id,
            "removed_ids": [l.id for l in losers],
        })
        removed_total += len(losers)

        if not dry_run:
            for loser in losers:
                # Qearn splits hang on the event id: drop the loser's and let
                # the Qearn auto-processing rebuild them for the survivor.
                if db.execute(
                    delete(EventSplit).where(
                        EventSplit.event_id == loser.id,
                        EventSplit.wallet_id == loser.wallet_id,
                    )
                ).rowcount:
                    survivor.sc_kind = None
                db.execute(
                    delete(Event).where(
                        Event.id == loser.id,
                        Event.wallet_id == loser.wallet_id,
                    )
                )

    if not dry_run:
        for wid, delta in balance_fix.items():
            wal = wallets.get(wid)
            if wal is not None and delta:
                wal.balance = (wal.balance or 0) + delta
                wal.balance_updated_at = now_utc_iso()
        db.commit()

    return {
        "groups": len(groups),
        "removed": removed_total,
        "wallets": sorted({d["wallet_id"] for d in details}),
        "balance_corrections": balance_fix,
        "details": details,
        "dry_run": dry_run,
    }


async def auto_dedup_job():
    """Scheduler job - heal duplicates without any user interaction."""
    from ..database import SessionLocal
    from ..utils.log_buffer import log_buffer

    db = SessionLocal()
    try:
        result = dedup_events(db)
        if result["removed"]:
            msg = (
                f"Auto-dedup: {result['removed']} duplicate event(s) removed "
                f"in {result['groups']} group(s)"
            )
            logger.info(msg)
            log_buffer.add("INFO", "dedup", msg)
    except Exception as e:
        db.rollback()
        logger.error(f"auto_dedup_job failed: {e}", exc_info=True)
    finally:
        db.close()
