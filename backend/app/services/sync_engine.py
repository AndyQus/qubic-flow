import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal
from ..models.wallet import Wallet
from ..models.event import Event
from ..models.sync_state import SyncState
from ..models.sync_gap import SyncGap
from ..utils.time import now_utc_iso, unix_ms_to_iso, iso_to_date
from .qubic_client import RPCClient, BOBClient
from .coingecko import get_price_for_date
from ..websocket.manager import manager
from ..models.node import Node

logger = logging.getLogger(__name__)

MAX_WINDOW_RECORDS = 10000
PAGE_SIZE = 1000


def _get_active_client(db):
    """Return the best-available client based on node priority and health."""
    node = (
        db.query(Node)
        .filter(Node.is_active == 1, Node.health_status.in_(["ONLINE", "DEGRADED"]))
        .order_by(Node.health_status != "ONLINE", Node.priority)
        .first()
    )
    if node is None:
        return RPCClient()
    if node.node_type == "BOB_NODE":
        return BOBClient(node.url)
    return RPCClient(node.url)


async def sync_all_wallets():
    """Entry point — called by scheduler every 60s."""
    db = SessionLocal()
    try:
        client = _get_active_client(db)
        current_tick = await client.get_current_tick()
        wallets = db.query(Wallet).filter(Wallet.active == 1, Wallet.deleted_at.is_(None)).all()
        for wallet in wallets:
            try:
                await sync_wallet(db, wallet.id, current_tick, client)
            except Exception as e:
                logger.error(f"Event sync failed for wallet {wallet.id}: {e}", exc_info=True)
                _set_sync_failed(db, wallet.id, str(e))
            try:
                await sync_wallet_tx(db, wallet.id, current_tick, client)
            except Exception as e:
                logger.error(f"TX sync failed for wallet {wallet.id}: {e}", exc_info=True)
    finally:
        db.close()


async def sync_wallet(db: Session, wallet_id: str, current_tick: int, client=None):
    if client is None:
        client = RPCClient()
    state = db.query(SyncState).filter(SyncState.wallet_id == wallet_id).first()
    if state is None:
        state = SyncState(wallet_id=wallet_id, last_tick=0, status="IDLE", total_events=0)
        db.add(state)
        db.commit()

    is_initial_sync = (state.last_tick or 0) == 0
    from_tick = (state.last_tick or 0) + 1
    to_tick = current_tick

    if from_tick > to_tick:
        return

    state.status = "SYNCING"
    state.last_sync = now_utc_iso()
    db.commit()

    try:
        owned_addresses = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}
        max_valid_tick = await _sync_window(db, wallet_id, from_tick, to_tick, owned_addresses, client, broadcast=not is_initial_sync)

        effective_tick = max_valid_tick if max_valid_tick is not None else to_tick
        if effective_tick < to_tick:
            gap = SyncGap(
                wallet_id=wallet_id,
                from_tick=effective_tick + 1,
                to_tick=to_tick,
                detected_at=now_utc_iso(),
            )
            db.add(gap)
            logger.warning(f"Wallet {wallet_id}: validForTick={effective_tick} < to_tick={to_tick}, gap recorded")
        state.last_tick = effective_tick
        state.status = "SUCCESS"
        state.error_message = None
        db.commit()
    except Exception as e:
        db.rollback()
        gap = SyncGap(
            wallet_id=wallet_id,
            from_tick=from_tick,
            to_tick=to_tick,
            detected_at=now_utc_iso(),
        )
        db.add(gap)
        state.status = "FAILED"
        state.error_message = str(e)[:500]
        db.commit()
        raise


async def _sync_window(db: Session, wallet_id: str, from_tick: int, to_tick: int, owned_addresses: set, client, broadcast: bool = True) -> int:
    probe = await client.get_event_logs(wallet_id, from_tick, to_tick, offset=0, size=1)
    total = probe.get("hits", {}).get("total", 0)
    valid_for_tick = probe.get("validForTick", to_tick)

    if total > MAX_WINDOW_RECORDS and from_tick < to_tick:
        mid = (from_tick + to_tick) // 2
        v1 = await _sync_window(db, wallet_id, from_tick, mid, owned_addresses, client, broadcast=broadcast)
        v2 = await _sync_window(db, wallet_id, mid + 1, to_tick, owned_addresses, client, broadcast=broadcast)
        return max(v1, v2)

    if total > MAX_WINDOW_RECORDS:
        logger.warning(f"Wallet {wallet_id} tick {from_tick}: {total} events, truncating at {MAX_WINDOW_RECORDS}")

    offset = 0
    while offset < min(total, MAX_WINDOW_RECORDS):
        resp = await client.get_event_logs(wallet_id, from_tick, to_tick, offset=offset, size=PAGE_SIZE)
        logs = resp.get("eventLogs", [])
        if not logs:
            break
        await _persist_logs(db, wallet_id, logs, owned_addresses, broadcast=broadcast)
        offset += len(logs)
        valid_for_tick = resp.get("validForTick", valid_for_tick)

    return valid_for_tick


def _apply_balance_delta(db: Session, wallet_id: str, events: list):
    """Update the tracked wallet balance for events newer than the baseline tick."""
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
    if not wallet or wallet.balance is None or wallet.balance_since_tick is None:
        return
    delta = 0
    for ev in events:
        tick = ev.get("tick_number")
        if tick is None or tick <= wallet.balance_since_tick:
            continue
        amount = ev.get("amount_qubic", 0) or 0
        if ev.get("destination_addr") == wallet_id:
            delta += amount
        if ev.get("source_address") == wallet_id:
            delta -= amount
    if delta != 0:
        wallet.balance = (wallet.balance or 0) + delta
        wallet.balance_updated_at = now_utc_iso()


async def _persist_logs(db: Session, wallet_id: str, logs: list, owned_addresses: set, broadcast: bool = True):
    state = db.query(SyncState).filter(SyncState.wallet_id == wallet_id).first()
    inserted = 0
    new_events = []

    for log in logs:
        log_id = log.get("logId")
        if not log_id:
            continue
        if db.query(Event.id).filter(Event.id == log_id, Event.wallet_id == wallet_id).first():
            continue

        qu = log.get("quTransfer", {})
        source = qu.get("source")
        dest = qu.get("destination")
        amount = int(qu.get("amount", "0")) if qu.get("amount") else 0

        ts_iso = unix_ms_to_iso(log.get("timestamp", "0"))
        date_str = iso_to_date(ts_iso)
        price = await get_price_for_date(db, date_str)

        is_internal = 1 if (source in owned_addresses and dest in owned_addresses) else 0

        event = Event(
            id=log_id,
            epoch=log.get("epoch"),
            tick_number=log.get("tickNumber"),
            timestamp_raw=log.get("timestamp"),
            timestamp=ts_iso,
            log_type=log.get("logType"),
            log_digest=log.get("logDigest"),
            categories=json.dumps(log.get("categories", [])),
            source_address=source,
            destination_addr=dest,
            wallet_id=wallet_id,
            is_internal=is_internal,
            amount_qubic=amount,
            qubic_eur_rate=price.get("eur"),
            qubic_usd_rate=price.get("usd"),
            source_type="EVENT",
            verified=0,
            created_at=now_utc_iso(),
        )
        db.merge(event)
        inserted += 1
        new_events.append({
            "id": log_id,
            "epoch": event.epoch,
            "tick_number": event.tick_number,
            "timestamp": event.timestamp,
            "source_address": event.source_address,
            "destination_addr": event.destination_addr,
            "wallet_id": event.wallet_id,
            "amount_qubic": event.amount_qubic,
            "qubic_eur_rate": event.qubic_eur_rate,
            "qubic_usd_rate": event.qubic_usd_rate,
            "is_internal": event.is_internal,
        })

    if inserted > 0:
        state.total_events = (state.total_events or 0) + inserted
        _apply_balance_delta(db, wallet_id, new_events)
        db.commit()
        logger.info(f"Wallet {wallet_id}: persisted {inserted} new events")
        if broadcast:
            for ev in new_events:
                await manager.broadcast("event.new", ev)


async def sync_wallet_tx(db: Session, wallet_id: str, current_tick: int, client=None):
    if client is None:
        client = RPCClient()
    state = db.query(SyncState).filter(SyncState.wallet_id == wallet_id).first()
    if state is None:
        return

    from_tick = (state.last_tx_tick or 0) + 1
    to_tick = current_tick

    if from_tick > to_tick:
        return

    owned_addresses = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}
    total_inserted = await _sync_transactions(db, wallet_id, from_tick, to_tick, owned_addresses, client)

    state.last_tx_tick = to_tick
    if total_inserted > 0:
        state.total_events = (state.total_events or 0) + total_inserted
    db.commit()
    logger.info(f"TX sync done for wallet {wallet_id}: {total_inserted} new records (ticks {from_tick}–{to_tick})")


async def _sync_transactions(db: Session, wallet_id: str, from_tick: int, to_tick: int, owned_addresses: set, client) -> int:
    page = 1
    total_inserted = 0

    while True:
        resp = await client.get_transfer_transactions(wallet_id, from_tick, to_tick, page=page, page_size=100)
        tick_groups = resp.get("transactions", [])
        inserted = 0

        for tick_group in tick_groups:
            tick_number = tick_group.get("tickNumber")
            for tx_data in tick_group.get("transactions", []):
                if not tx_data.get("moneyFlew", False):
                    continue

                tx = tx_data.get("transaction", {})
                tx_id = tx.get("txId")
                if not tx_id:
                    continue

                # Skip if already stored as TX
                if db.query(Event.id).filter(Event.id == tx_id, Event.wallet_id == wallet_id).first():
                    continue
                # Skip if already covered by an Event (logDigest == txId)
                if db.query(Event.id).filter(Event.log_digest == tx_id, Event.wallet_id == wallet_id).first():
                    continue

                source = tx.get("sourceId")
                dest = tx.get("destId")
                amount = int(tx.get("amount") or "0")
                ts_unix_s = tx_data.get("timestamp", 0)
                ts_iso = unix_ms_to_iso(int(ts_unix_s) * 1000)
                date_str = iso_to_date(ts_iso)
                price = await get_price_for_date(db, date_str)
                is_internal = 1 if (source in owned_addresses and dest in owned_addresses) else 0

                event = Event(
                    id=tx_id,
                    wallet_id=wallet_id,
                    tick_number=tick_number,
                    timestamp_raw=str(ts_unix_s),
                    timestamp=ts_iso,
                    log_type=tx.get("inputType"),
                    log_digest=tx_id,
                    source_address=source,
                    destination_addr=dest,
                    is_internal=is_internal,
                    amount_qubic=amount,
                    qubic_eur_rate=price.get("eur"),
                    qubic_usd_rate=price.get("usd"),
                    source_type="TX",
                    verified=0,
                    created_at=now_utc_iso(),
                )
                db.merge(event)
                inserted += 1

        if inserted > 0:
            db.commit()
            total_inserted += inserted
            logger.info(f"Wallet {wallet_id}: TX page {page} — {inserted} new records")

        pagination = resp.get("pagination", {})
        if page >= pagination.get("totalPages", 1) or not tick_groups:
            break
        page += 1

    return total_inserted


def _set_sync_failed(db: Session, wallet_id: str, message: str):
    state = db.query(SyncState).filter(SyncState.wallet_id == wallet_id).first()
    if state:
        state.status = "FAILED"
        state.error_message = message[:500]
        db.commit()
