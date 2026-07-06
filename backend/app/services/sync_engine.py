import json
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func
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
from ..utils.log_buffer import log_buffer
from ..config import settings

import httpx

logger = logging.getLogger(__name__)

MAX_WINDOW_RECORDS = 10000
PAGE_SIZE = 1000

# A BOB node is only used for live sync if it is no more than this many ticks
# behind the network (RPC) tip. Beyond this it is considered "stalled" and we
# fall back to RPC so live data keeps flowing.
MAX_BOB_LAG = 1000

_active_sync_node_id: int | None = None
_last_event_source_log: float = 0.0   # Unix timestamp of last "event source" log entry
_last_event_source_key: str = ""       # e.g. "BOB:https://bobnet.qubic.li"
_EVENT_SOURCE_LOG_INTERVAL = 3600      # log at most once per hour unless source changes


def get_active_sync_node_id() -> int | None:
    return _active_sync_node_id


def _get_active_client(db):
    """Compatibility wrapper — returns the first available client."""
    candidates = _get_ordered_clients(db)
    return candidates[0][1] if candidates else RPCClient()


def _get_ordered_clients(db):
    """Return list of (node, client) sorted by health then priority."""
    nodes = (
        db.query(Node)
        .filter(Node.is_active == 1, Node.health_status.in_(["ONLINE", "DEGRADED"]))
        .order_by(Node.health_status != "ONLINE", Node.priority)
        .all()
    )
    result = []
    for n in nodes:
        client = BOBClient(n.url) if n.node_type == "BOB_NODE" else RPCClient(n.url)
        result.append((n, client))
    if not result:
        result.append((None, RPCClient()))
    return result


def _get_rpc_client(db) -> RPCClient:
    """Return the best available RPC client for historical/gap queries.

    Priority:
      1. User-configured RPC node (ONLINE preferred, DEGRADED accepted)
      2. Default URL from settings (settings.qubic_rpc_url = rpc.qubic.org)

    This means users can always change the fallback URL by adding/editing their
    RPC node entry — no code release needed.
    """
    rpc_node = (
        db.query(Node)
        .filter(
            Node.is_active == 1,
            Node.node_type == "RPC",
            Node.health_status.in_(["ONLINE", "DEGRADED"]),
        )
        .order_by(Node.health_status != "ONLINE", Node.priority)
        .first()
    )
    if rpc_node:
        return RPCClient(rpc_node.url)
    return RPCClient()  # falls back to settings.qubic_rpc_url


def _select_best_bob(db, rpc_tick: int | None):
    """Pick the active BOB node best suited for live sync.

    Selection is tick-based, not priority-based: among all active ONLINE/DEGRADED
    BOB nodes we choose the one with the *highest* tick (furthest advanced).
    A BOB node that lags more than MAX_BOB_LAG ticks behind the RPC tip is
    considered stalled and skipped, so a stuck primary node no longer blocks
    live sync. Priority is only used as a tiebreaker between nodes at (nearly)
    the same tick.

    Returns the chosen Node, or None if no suitable BOB node exists.
    """
    bob_nodes = (
        db.query(Node)
        .filter(
            Node.is_active == 1,
            Node.node_type == "BOB_NODE",
            Node.health_status.in_(["ONLINE", "DEGRADED"]),
        )
        .all()
    )
    if not bob_nodes:
        return None

    # Best = highest tick, then lowest priority number as tiebreaker.
    bob_nodes.sort(key=lambda n: (-(n.tick or 0), n.priority))
    best = bob_nodes[0]

    # If we know where the network stands, reject the best BOB when it lags too far.
    if rpc_tick is not None and (best.tick or 0) > 0:
        lag = rpc_tick - (best.tick or 0)
        if lag > MAX_BOB_LAG:
            logger.warning(
                f"Best BOB {best.url} lags {lag} ticks behind RPC "
                f"(bob={best.tick}, rpc={rpc_tick}) — falling back to RPC for live sync"
            )
            log_buffer.add(
                "WARNING", "sync",
                f"Best BOB lags {lag} ticks behind network (> {MAX_BOB_LAG}) — using RPC for live sync",
                node=best.url,
            )
            return None
    return best


async def _set_active_sync_node(db, node_id: int | None):
    """Update the active sync node id and notify the UI on change.

    Broadcasts a `sync.node` event whenever the elected live-sync node changes,
    so the header can show which node is really feeding data without polling.
    """
    global _active_sync_node_id
    if node_id == _active_sync_node_id:
        _active_sync_node_id = node_id
        return
    _active_sync_node_id = node_id
    node = db.query(Node).filter(Node.id == node_id).first() if node_id else None
    await manager.broadcast("sync.node", {
        "node_id": node_id,
        "url": node.url if node else None,
        "label": node.label if node else None,
        "node_type": node.node_type if node else None,
        "tick": node.tick if node else None,
    })


async def _get_event_client(db, rpc_tick: int | None = None):
    """Return the best available event client for incremental (live) sync.

    BOB nodes are preferred for live sync since they stream the current tick
    efficiently, but only the BOB node with the highest tick is used, and only
    if it is not stalled relative to the RPC tip (see _select_best_bob).
    BOB cannot perform historical queries — use _get_rpc_client() for gap filling.
    Falls back to RPC if no suitable BOB node is available or reachable.

    Also records the chosen node in _active_sync_node_id (and notifies the UI
    on change) so the header can show which node is really feeding live data.
    """
    bob_node = _select_best_bob(db, rpc_tick)
    if bob_node:
        bob = BOBClient(bob_node.url)
        try:
            if await bob.supports_event_logs():
                logger.info(f"BOB {bob_node.url}: live-tick streaming active (tick {bob_node.tick})")
            await _set_active_sync_node(db, bob_node.id)
            return bob
        except Exception as e:
            logger.warning(f"BOB {bob_node.url} probe failed ({e}) — falling back to RPC")

    # RPC fallback — reflect the RPC node as the active sync node in the UI.
    rpc_node = (
        db.query(Node)
        .filter(
            Node.is_active == 1,
            Node.node_type == "RPC",
            Node.health_status.in_(["ONLINE", "DEGRADED"]),
        )
        .order_by(Node.health_status != "ONLINE", Node.priority)
        .first()
    )
    await _set_active_sync_node(db, rpc_node.id if rpc_node else None)
    return _get_rpc_client(db)


def elect_active_sync_node(db) -> int | None:
    """Pick the best available node, update _active_sync_node_id, and return it."""
    global _active_sync_node_id
    for node, _ in _get_ordered_clients(db):
        if node is not None:
            _active_sync_node_id = node.id
            return node.id
    _active_sync_node_id = None
    return None


async def sync_all_wallets():
    """Entry point — called by scheduler every 60s."""
    db = SessionLocal()
    try:
        client = None
        current_tick = None

        for node, c in _get_ordered_clients(db):
            try:
                current_tick = await c.get_current_tick()
                client = c
                if node is not None:
                    node.fail_count = 0
                    node.last_error = None
                    db.commit()
                    global _active_sync_node_id
                    _active_sync_node_id = node.id
                break
            except Exception as e:
                logger.warning(f"Node {getattr(node, 'url', 'fallback')} get_tick failed: {e}, trying next")
                log_buffer.add("WARNING", "sync", f"get_tick failed: {e}", node=getattr(node, 'url', 'fallback'))
                if node is not None:
                    node.fail_count = (node.fail_count or 0) + 1
                    node.health_status = "OFFLINE" if node.fail_count >= 3 else "DEGRADED"
                    node.last_error = str(e)[:500]
                    db.commit()

        # All configured nodes failed → try default RPC as silent last resort.
        # BOB-Nodes bleiben DEGRADED und werden im nächsten Zyklus erneut versucht.
        if client is None:
            try:
                rpc_fallback = RPCClient()
                current_tick = await rpc_fallback.get_current_tick()
                client = rpc_fallback
                logger.info("All configured nodes failed — using default RPC as fallback")
                log_buffer.add("INFO", "sync", "All configured nodes failed — using default RPC as fallback", node=settings.qubic_rpc_url)
            except Exception as e:
                logger.error(f"Default RPC fallback also failed: {e} — sync skipped")
                log_buffer.add("ERROR", "sync", f"Default RPC fallback also failed: {e} — sync skipped", node=settings.qubic_rpc_url)
                return

        # Determine the network tip (RPC) as reference for BOB lag detection.
        # Prefer the freshly stored RPC node tick from the health monitor (no
        # extra network call); fall back to current_tick from the sync probe.
        rpc_node = (
            db.query(Node)
            .filter(
                Node.is_active == 1,
                Node.node_type == "RPC",
                Node.health_status.in_(["ONLINE", "DEGRADED"]),
            )
            .order_by(Node.health_status != "ONLINE", Node.priority)
            .first()
        )
        rpc_tick = (rpc_node.tick if rpc_node and rpc_node.tick else None) or current_tick

        event_client = await _get_event_client(db, rpc_tick)
        rpc_client_for_history = _get_rpc_client(db)

        # Log which source is fetching events — at most once per hour, immediately on change.
        global _last_event_source_log, _last_event_source_key
        _src_type = "BOB" if isinstance(event_client, BOBClient) else "RPC"
        _src_url = getattr(event_client, 'base_url', settings.qubic_rpc_url)
        _src_key = f"{_src_type}:{_src_url}"
        _now = time.monotonic()
        if _src_key != _last_event_source_key or (_now - _last_event_source_log) >= _EVENT_SOURCE_LOG_INTERVAL:
            msg = f"Event source active: {_src_type}"
            logger.info(msg)
            log_buffer.add("INFO", "sync", msg, node=_src_url)
            _last_event_source_key = _src_key
            _last_event_source_log = _now

        wallets = db.query(Wallet).filter(Wallet.active == 1, Wallet.deleted_at.is_(None)).all()
        for wallet in wallets:
            try:
                await sync_wallet(db, wallet.id, current_tick, event_client, rpc_client_for_history)
            except Exception as e:
                logger.error(f"Event sync failed for wallet {wallet.id}: {e}", exc_info=True)
                log_buffer.add("ERROR", "sync", f"Event sync failed for wallet {wallet.id}: {e}", node=_src_url)
                _set_sync_failed(db, wallet.id, str(e))
            try:
                await sync_wallet_tx(db, wallet.id, current_tick, client)
            except Exception as e:
                logger.error(f"TX sync failed for wallet {wallet.id}: {e}", exc_info=True)
                log_buffer.add("ERROR", "sync", f"TX sync failed for wallet {wallet.id}: {e}", node=_src_url)
    finally:
        db.close()


async def sync_wallet(db: Session, wallet_id: str, current_tick: int, client=None, rpc_fallback=None):
    """Sync a wallet's event log.

    client: the preferred event source (may be BOBClient for live sync).
    rpc_fallback: always an RPCClient; used for initial/historical sync since BOB cannot backfill.
    """
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

    # Always prefer BOB if available — BOB may already have the current tick's transfers ready.
    # Only fall back to RPC if BOB returns no data (empty response or error).
    # The _sync_window / _fetch_transfers logic handles gaps via validForTick automatically.
    is_bob = isinstance(client, BOBClient)
    if is_bob:
        logger.info(f"Wallet {wallet_id}: gap {to_tick - from_tick} ticks, trying BOB first")
    effective_client = client

    state.status = "SYNCING"
    state.last_sync = now_utc_iso()
    db.commit()

    try:
        owned_addresses = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}
        max_valid_tick = await _sync_window(db, wallet_id, from_tick, to_tick, owned_addresses, effective_client, broadcast=not is_initial_sync)

        # BOB only serves its current live tick, so valid_for_tick may be >> from_tick,
        # leaving the range [from_tick .. valid_for_tick-1] unfilled.
        # Fill that historical gap via RPC before accepting BOB's tick as the new baseline.
        if is_bob and max_valid_tick is not None and max_valid_tick > from_tick:
            historical_to = max_valid_tick - 1
            if historical_to >= from_tick:
                logger.info(f"Wallet {wallet_id}: BOB served tick {max_valid_tick}, backfilling gap {from_tick}-{historical_to} via RPC")
                rpc = rpc_fallback or _get_rpc_client(db)
                await _sync_window(db, wallet_id, from_tick, historical_to, owned_addresses, rpc, broadcast=not is_initial_sync)
        elif is_bob and (max_valid_tick is None or max_valid_tick < from_tick):
            logger.info(f"Wallet {wallet_id}: BOB had no data for tick range {from_tick}-{to_tick}, falling back to RPC")
            rpc = rpc_fallback or _get_rpc_client(db)
            max_valid_tick = await _sync_window(db, wallet_id, from_tick, to_tick, owned_addresses, rpc, broadcast=not is_initial_sync)

        effective_tick = max_valid_tick if max_valid_tick is not None else to_tick
        if effective_tick < to_tick:
            gap_from = effective_tick + 1
            existing_gap = (
                db.query(SyncGap)
                .filter(
                    SyncGap.wallet_id == wallet_id,
                    SyncGap.from_tick == gap_from,
                    SyncGap.resolved_at.is_(None),
                )
                .first()
            )
            if existing_gap:
                existing_gap.to_tick = max(existing_gap.to_tick, to_tick)
            else:
                db.add(SyncGap(
                    wallet_id=wallet_id,
                    from_tick=gap_from,
                    to_tick=to_tick,
                    detected_at=now_utc_iso(),
                    gap_type="EVENT",
                ))
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
            gap_type="EVENT",
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
    from ..models.address_label import AddressLabel
    state = db.query(SyncState).filter(SyncState.wallet_id == wallet_id).first()
    # Addresses listed as smart contracts / token issuers (assets) — transfers
    # to/from these count as EVENTs, not user TXs. Covers SCs (QX, Qearn, …)
    # and all token issuer addresses from the Qubic assets registry.
    sc_addresses = {
        row[0] for row in db.query(AddressLabel.address)
        .filter(
            (AddressLabel.category == "smart_contract")
            | (AddressLabel.source.in_(["smart_contract", "issuance", "token"]))
        )
        .all()
    }
    inserted = 0
    new_events = []
    price_cache: dict = {}
    seen_ids: set = set()

    for log in logs:
        log_id = log.get("logId")
        if not log_id:
            continue
        # The archiver's getEventLogs response exposes the 60-char Qubic
        # TxID under `transactionHash` — the explorer's primary identifier.
        # Use it as our primary key so `id` matches the explorer's TxID.
        # Falls back to logId for SC-internal events where the archiver
        # provides no transactionHash.
        real_tx_id = None
        for c in (log.get("transactionHash"), log.get("transactionId"),
                  log.get("txId"), log.get("digest")):
            if isinstance(c, str) and len(c) == 60 and c.isalpha() and c.islower():
                real_tx_id = c
                break
        effective_id = real_tx_id if real_tx_id else str(log_id)
        # Dedup within the current batch (API can return same id with different log_type).
        if effective_id in seen_ids:
            continue
        seen_ids.add(effective_id)
        # Dedup: an existing row may use either key (transactionHash from
        # new code, logId from older code). Skip if either matches.
        dedup_keys = {effective_id, str(log_id)}
        if db.query(Event.id).filter(
            Event.wallet_id == wallet_id,
            Event.id.in_(dedup_keys),
        ).first():
            continue

        qu = log.get("quTransfer", {})
        source = qu.get("source")
        dest = qu.get("destination")
        amount = int(qu.get("amount", "0")) if qu.get("amount") else 0

        # Only persist events that actually involve this wallet.
        # BOB and some RPC responses may return unfiltered network-wide data.
        if source != wallet_id and dest != wallet_id:
            continue

        ts_iso = unix_ms_to_iso(log.get("timestamp", "0"))
        date_str = iso_to_date(ts_iso)
        if date_str not in price_cache:
            price_cache[date_str] = await get_price_for_date(db, date_str)
        price = price_cache[date_str]

        is_internal = 1 if (source in owned_addresses and dest in owned_addresses) else 0

        # Classification:
        #   - logType == 0 (QuTransfer) AND neither side is a known smart contract → TX
        #   - logType == 0 but source or destination IS a smart contract → EVENT
        #     (SC-triggered transfer, no user-initiated archiver TX)
        #   - logType != 0 (asset events, burns, etc.) → EVENT
        log_type = log.get("logType")
        touches_sc = (source in sc_addresses) or (dest in sc_addresses)
        src_type = "TX" if (log_type == 0 and not touches_sc) else "EVENT"
        event = Event(
            id=effective_id,
            epoch=log.get("epoch"),
            tick_number=log.get("tickNumber"),
            timestamp_raw=log.get("timestamp"),
            timestamp=ts_iso,
            log_type=log_type,
            log_digest=real_tx_id or log.get("logDigest"),
            categories=json.dumps(log.get("categories", [])),
            source_address=source,
            destination_addr=dest,
            wallet_id=wallet_id,
            is_internal=is_internal,
            amount_qubic=amount,
            qubic_eur_rate=price.get("eur"),
            qubic_usd_rate=price.get("usd"),
            source_type=src_type,
            verified=0,
            created_at=now_utc_iso(),
        )
        db.add(event)
        inserted += 1
        new_events.append({
            "id": effective_id,
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
            "log_digest": event.log_digest,
            "log_type": event.log_type,
            "source_type": event.source_type,
        })

    if inserted > 0:
        state.total_events = (state.total_events or 0) + inserted
        _apply_balance_delta(db, wallet_id, new_events)
        db.commit()
        logger.info(f"Wallet {wallet_id}: persisted {inserted} new events")
        if broadcast:
            for ev in new_events:
                await manager.broadcast("event.new", ev)
            # Webhook notifications (best-effort, only for live events —
            # initial/backfill syncs run with broadcast=False and stay silent)
            from .notification_service import notify_incoming
            await notify_incoming(db, new_events)


TX_WINDOW_SIZE = 500_000  # max ticks per API call


def _epoch_for_tick(db: Session, tick_number: int | None) -> int | None:
    """Look up epoch from existing events that share the same tick number."""
    if tick_number is None:
        return None
    row = db.query(Event.epoch).filter(
        Event.tick_number == tick_number,
        Event.epoch.isnot(None),
    ).first()
    return row[0] if row else None


async def _epoch_from_api(tick_number: int, cache: dict, http_client=None) -> int | None:
    """Fetch epoch for a tick from the Qubic API, with in-memory cache."""
    if tick_number in cache:
        return cache[tick_number]
    try:
        if http_client is not None:
            r = await http_client.get(
                f"https://rpc.qubic.org/v1/ticks/{tick_number}/tick-data",
                timeout=10,
            )
        else:
            async with httpx.AsyncClient() as c:
                r = await c.get(
                    f"https://rpc.qubic.org/v1/ticks/{tick_number}/tick-data",
                    timeout=10,
                )
        if r.status_code == 200:
            epoch = r.json().get("tickData", {}).get("epoch")
            cache[tick_number] = epoch
            return epoch
    except Exception:
        pass
    cache[tick_number] = None
    return None


async def backfill_tx_epochs(db: Session) -> int:
    """Fill epoch=NULL on TX records: DB lookup first, API fallback."""
    rows = db.query(Event).filter(
        Event.source_type == "TX",
        Event.epoch.is_(None),
        Event.tick_number.isnot(None),
    ).all()
    updated = 0
    api_cache: dict = {}
    async with httpx.AsyncClient() as http_client:
        for ev in rows:
            epoch = _epoch_for_tick(db, ev.tick_number)
            if epoch is None:
                epoch = await _epoch_from_api(ev.tick_number, api_cache, http_client)
            if epoch is not None:
                ev.epoch = epoch
                updated += 1
    if updated:
        db.commit()
        logger.info(f"backfill_tx_epochs: updated {updated} TX records")
    return updated


async def _tick_timestamp_from_api(tick_number: int, cache: dict, http_client, base_url: str) -> str | None:
    """Fetch the Unix-ms timestamp for a tick from the archiver, with cache."""
    if tick_number in cache:
        return cache[tick_number]
    ts = None
    try:
        r = await http_client.get(f"{base_url}/v1/ticks/{tick_number}/tick-data", timeout=10)
        if r.status_code == 200:
            raw = r.json().get("tickData", {}).get("timestamp")
            if raw and int(raw) > 0:
                ts = str(raw)
    except Exception:
        pass
    cache[tick_number] = ts
    return ts


async def backfill_missing_timestamps(limit: int = 500) -> int:
    """Scheduler job — fix events stored without a usable timestamp.

    Old BOB imports (before tick-timestamp resolution existed) persisted
    events with timestamp 0 → 1970-01-01, which breaks price lookup and the
    tax engine's holding-period logic. Resolve the real timestamp via the
    archiver's tick-data endpoint and fill the EUR/USD rate in the same pass.
    """
    db = SessionLocal()
    try:
        rows = db.query(Event).filter(
            Event.tick_number.isnot(None),
            (Event.timestamp.is_(None))
            | (Event.timestamp < "2020")
            | (Event.timestamp_raw == "0"),
        ).limit(limit).all()
        if not rows:
            return 0

        base_url = _get_rpc_client(db).base_url
        tick_cache: dict = {}
        price_cache: dict = {}
        updated = 0
        async with httpx.AsyncClient() as http_client:
            for ev in rows:
                raw_ms = await _tick_timestamp_from_api(ev.tick_number, tick_cache, http_client, base_url)
                if raw_ms is None:
                    continue
                ts_iso = unix_ms_to_iso(raw_ms)
                ev.timestamp_raw = raw_ms
                ev.timestamp = ts_iso
                date_str = iso_to_date(ts_iso)
                if date_str not in price_cache:
                    price_cache[date_str] = await get_price_for_date(db, date_str)
                price = price_cache[date_str]
                if price.get("eur") is not None:
                    ev.qubic_eur_rate = price.get("eur")
                    ev.qubic_usd_rate = price.get("usd")
                updated += 1
        if updated:
            db.commit()
            logger.info(f"backfill_missing_timestamps: fixed {updated} events")
            log_buffer.add("INFO", "sync", f"Timestamp backfill: fixed {updated} events", node=base_url)
        return updated
    finally:
        db.close()


async def sync_wallet_tx(db: Session, wallet_id: str, current_tick: int, client=None):
    if client is None:
        client = RPCClient()
    state = db.query(SyncState).filter(SyncState.wallet_id == wallet_id).first()
    if state is None:
        return

    # The archiver only keeps a rolling window of recent ticks. On first run
    # (last_tx_tick == 0), walking from tick 1 causes every chunk before the
    # retention horizon to 404 and aborts the whole sync before checkpointing,
    # so the next cycle restarts at 1 forever. Baseline to the last window.
    if (state.last_tx_tick or 0) == 0:
        from_tick = max(1, current_tick - TX_WINDOW_SIZE)
    else:
        from_tick = state.last_tx_tick + 1
    to_tick = current_tick

    if from_tick > to_tick:
        return

    owned_addresses = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}
    total_inserted = 0

    chunk_start = from_tick
    while chunk_start <= to_tick:
        chunk_end = min(chunk_start + TX_WINDOW_SIZE - 1, to_tick)
        try:
            inserted = await _sync_transactions(db, wallet_id, chunk_start, chunk_end, owned_addresses, client)
            total_inserted += inserted
            # Checkpoint per chunk so a later failure never rewinds progress.
            state.last_tx_tick = chunk_end
            if inserted > 0:
                state.total_events = (state.total_events or 0) + inserted
            db.commit()
        except Exception as e:
            db.rollback()
            db.add(SyncGap(
                wallet_id=wallet_id,
                from_tick=chunk_start,
                to_tick=chunk_end,
                detected_at=now_utc_iso(),
                gap_type="TX",
            ))
            db.commit()
            logger.warning(f"TX chunk {chunk_start}-{chunk_end} failed for {wallet_id}: {e}")
        chunk_start = chunk_end + 1

    logger.info(f"TX sync done for wallet {wallet_id}: {total_inserted} new records (ticks {from_tick}–{to_tick})")


async def _sync_transactions(db: Session, wallet_id: str, from_tick: int, to_tick: int, owned_addresses: set, client) -> int:
    page = 1
    total_inserted = 0
    epoch_cache: dict = {}
    price_cache: dict = {}

    async with httpx.AsyncClient() as http_client:
        while True:
            resp = await client.get_transfer_transactions(wallet_id, from_tick, to_tick, page=page, page_size=100)
            tick_groups = resp.get("transactions", [])
            inserted = 0
            new_tx_events = []

            for tick_group in tick_groups:
                tick_number = tick_group.get("tickNumber")
                epoch = _epoch_for_tick(db, tick_number)
                if epoch is None:
                    epoch = await _epoch_from_api(tick_number, epoch_cache, http_client)
                for tx_data in tick_group.get("transactions", []):
                    if not tx_data.get("moneyFlew", False):
                        continue

                    tx = tx_data.get("transaction", {})
                    # Prefer the 60-char lowercase Qubic TxID format that matches
                    # explorer.qubic.org. Different RPC / archiver variants expose
                    # it under different keys, so try the common ones and pick the
                    # first 60-char lowercase value, falling back to whatever we
                    # have if none match.
                    candidates = [
                        tx_data.get("transactionId"), tx_data.get("txId"), tx_data.get("id"),
                        tx_data.get("digest"), tx_data.get("hash"),
                        tx.get("transactionId"), tx.get("txId"), tx.get("id"),
                        tx.get("digest"), tx.get("hash"),
                    ]
                    tx_id = None
                    for c in candidates:
                        if isinstance(c, str) and len(c) == 60 and c.isalpha() and c.islower():
                            tx_id = c
                            break
                    if tx_id is None:
                        for c in candidates:
                            if c:
                                tx_id = str(c)
                                break
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
                    # TX API returns Unix seconds; unix_ms_to_iso expects milliseconds.
                    ts_unix_s = tx_data.get("timestamp", 0)
                    ts_iso = unix_ms_to_iso(int(ts_unix_s) * 1000)
                    date_str = iso_to_date(ts_iso)
                    if date_str not in price_cache:
                        price_cache[date_str] = await get_price_for_date(db, date_str)
                    price = price_cache[date_str]
                    is_internal = 1 if (source in owned_addresses and dest in owned_addresses) else 0

                    # Reconcile with an event-log stub for the same transaction.
                    # getEventLogs only gives us a numeric logId + 16-char hex
                    # logDigest, not the explorer's 60-char txId. Match by
                    # (tick, source, dest, amount) and upgrade the id/log_digest
                    # in place, preserving any user-entered columns (comment,
                    # item tags, verified). length(id) != 60 filters out rows
                    # that were already reconciled on a previous pass.
                    # ORDER BY id makes the match deterministic when duplicate
                    # stubs exist (e.g. two identical transfers in the same tick).
                    stub = db.query(Event).filter(
                        Event.wallet_id == wallet_id,
                        Event.tick_number == tick_number,
                        Event.source_address == source,
                        Event.destination_addr == dest,
                        Event.amount_qubic == amount,
                        func.length(Event.id) != 60,
                    ).order_by(Event.id).first()
                    if stub is not None:
                        db.execute(
                            update(Event)
                            .where(Event.id == stub.id, Event.wallet_id == wallet_id)
                            .values(id=tx_id, log_digest=tx_id, epoch=epoch or stub.epoch)
                        )
                        inserted += 1
                        continue
                    event = Event(
                        id=tx_id,
                        wallet_id=wallet_id,
                        epoch=epoch,
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
                    db.add(event)
                    inserted += 1
                    new_tx_events.append({
                        "tick_number": tick_number,
                        "amount_qubic": amount,
                        "source_address": source,
                        "destination_addr": dest,
                    })

            if inserted > 0:
                _apply_balance_delta(db, wallet_id, new_tx_events)
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


async def retry_sync_gaps():
    """Scheduler job — retry all unresolved sync gaps (EVENT and TX).

    Gaps are recorded whenever the archiver can't serve a tick range or an API
    call fails mid-chunk.  This job picks them up and retries the exact range so
    data is never permanently lost just because a node was temporarily offline.
    On success the gap is marked resolved; on failure it stays open and will be
    retried on the next run.
    """
    db = SessionLocal()
    try:
        gaps = (
            db.query(SyncGap)
            .filter(SyncGap.resolved_at.is_(None))
            .order_by(SyncGap.detected_at)
            .all()
        )
        if not gaps:
            return

        logger.info(f"Gap retry: {len(gaps)} unresolved gap(s) found")
        log_buffer.add("INFO", "sync", f"Gap retry: {len(gaps)} unresolved gap(s) found")

        client = _get_active_client(db)
        try:
            current_tick = await client.get_current_tick()
        except Exception as e:
            logger.warning(f"retry_sync_gaps: could not get current tick ({e}) — skipping")
            log_buffer.add("WARNING", "sync", f"Gap retry skipped: could not get current tick ({e})")
            return

        # Gap filling always uses RPC — BOB only streams the live tick and cannot backfill history
        rpc_event_client = _get_rpc_client(db)
        rpc_event_url = getattr(rpc_event_client, 'base_url', settings.qubic_rpc_url)
        owned_addresses = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}

        resolved = 0
        for gap in gaps:
            gap_type = gap.gap_type or "EVENT"
            effective_to = min(gap.to_tick, current_tick)
            if gap.from_tick > effective_to:
                # Gap is in the future — shouldn't happen, resolve silently.
                gap.resolved_at = now_utc_iso()
                db.commit()
                continue
            try:
                if gap_type == "TX":
                    await _sync_transactions(db, gap.wallet_id, gap.from_tick, effective_to, owned_addresses, client)
                else:
                    await _sync_window(db, gap.wallet_id, gap.from_tick, effective_to, owned_addresses, rpc_event_client)
                gap.resolved_at = now_utc_iso()
                db.commit()
                resolved += 1
                logger.info(
                    f"Gap resolved: wallet {gap.wallet_id} ticks {gap.from_tick}-{effective_to} ({gap_type})"
                )
                log_buffer.add(
                    "INFO", "sync",
                    f"Gap resolved: wallet {gap.wallet_id} ticks {gap.from_tick}-{effective_to} ({gap_type})",
                    node=rpc_event_url,
                )
            except Exception as e:
                db.rollback()
                logger.warning(
                    f"Gap retry failed: wallet {gap.wallet_id} ticks {gap.from_tick}-{effective_to} ({gap_type}): {e}"
                )
                log_buffer.add(
                    "WARNING", "sync",
                    f"Gap retry failed: wallet {gap.wallet_id} ticks {gap.from_tick}-{effective_to}: {e}",
                    node=rpc_event_url,
                )

        if resolved:
            logger.info(f"Gap retry complete: {resolved}/{len(gaps)} resolved")
            log_buffer.add("INFO", "sync", f"Gap retry complete: {resolved}/{len(gaps)} resolved")
    finally:
        db.close()


async def _trigger_balance_resync(db: Session, wallet_id: str, since_tick: int, current_tick: int):
    """Reset the event/TX sync pointers to re-fetch data from *since_tick*.

    Called when the hourly balance check detects a mismatch between the
    RPC-reported live balance and the balance computed from stored events.
    Instead of a full reset (which would re-import everything), we only go
    back to the wallet's balance baseline tick so the re-scan is minimal.
    """
    state = db.query(SyncState).filter(SyncState.wallet_id == wallet_id).first()
    if state is None:
        return

    new_event_tick = max(0, since_tick - 1)
    new_tx_tick = max(0, since_tick - TX_WINDOW_SIZE)

    if (state.last_tick or 0) <= new_event_tick and (state.last_tx_tick or 0) <= new_tx_tick:
        return

    logger.warning(
        f"Balance mismatch for {wallet_id}: resetting event sync "
        f"from tick {state.last_tick} → {new_event_tick}, "
        f"TX sync from {state.last_tx_tick} → {new_tx_tick}"
    )
    active_client = _get_rpc_client(db)
    active_node_url = getattr(active_client, 'base_url', settings.qubic_rpc_url)
    log_buffer.add(
        "WARNING", "sync",
        f"Balance mismatch for {wallet_id}: re-sync triggered from tick {since_tick}",
        node=active_node_url,
    )

    state.last_tick = new_event_tick
    state.last_tx_tick = new_tx_tick
    db.commit()
