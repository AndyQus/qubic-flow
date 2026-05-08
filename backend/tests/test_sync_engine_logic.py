"""
Unit tests for the is_internal detection logic inside _persist_logs.

We mock only the two external I/O points:
  - `_client.get_event_logs`  (replaced via monkeypatch on the module-level object)
  - `get_price_for_date`      (replaced with a coroutine stub)

Everything else — the DB writes, the is_internal calculation — runs for real
against the in-memory SQLite session.
"""
import asyncio
import pytest
from app.models.wallet import Wallet
from app.models.sync_state import SyncState
from app.models.event import Event
from app.utils.time import now_utc_iso


# ------------------------------------------------------------------ helpers --

WALLET_A = "ADDR_WALLET_A_000000000000000000000000000000000000000001"
WALLET_B = "ADDR_WALLET_B_000000000000000000000000000000000000000002"
EXTERNAL = "ADDR_EXTERNAL_00000000000000000000000000000000000000003"


def _seed_wallets(db):
    now = now_utc_iso()
    for wid, label in [(WALLET_A, "Wallet A"), (WALLET_B, "Wallet B")]:
        db.add(Wallet(
            id=wid, label=label, wallet_type="PRIVATE",
            active=1, created_at=now, updated_at=now,
        ))
    db.flush()


def _seed_sync_state(db, wallet_id):
    db.add(SyncState(wallet_id=wallet_id, last_tick=0, status="SYNCING", total_events=0))
    db.flush()


def _make_log(log_id: str, source: str, dest: str, amount: int = 100) -> dict:
    return {
        "logId": log_id,
        "epoch": 100,
        "tickNumber": 10000,
        "timestamp": "1700000000000",
        "logType": 1,
        "logDigest": "digest",
        "categories": [],
        "quTransfer": {
            "source": source,
            "destination": dest,
            "amount": str(amount),
        },
    }


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# ------------------------------------------------------------------ tests --

class TestIsInternalDetection:
    """
    Tests verify that _persist_logs sets is_internal correctly based on
    whether both source and destination are owned wallet addresses.
    """

    def test_both_addresses_owned_sets_is_internal_1(self, db, monkeypatch):
        """
        When source AND destination are both in owned_addresses, is_internal=1.
        """
        _seed_wallets(db)
        _seed_sync_state(db, WALLET_A)

        logs = [_make_log("LOG_INTERNAL_01", source=WALLET_A, dest=WALLET_B)]
        owned = {WALLET_A, WALLET_B}

        # Stub out price fetch
        async def _fake_price(_db, _date):
            return {"eur": 0.00015, "usd": 0.00017}

        import app.services.sync_engine as engine_mod
        monkeypatch.setattr(engine_mod, "get_price_for_date", _fake_price)

        # Stub out manager broadcast to avoid WebSocket setup
        async def _noop_broadcast(_event_type, _payload):
            pass

        monkeypatch.setattr(engine_mod.manager, "broadcast", _noop_broadcast)

        _run(engine_mod._persist_logs(db, WALLET_A, logs, owned))

        event = db.query(Event).filter(Event.id == "LOG_INTERNAL_01").first()
        assert event is not None, "Event was not persisted"
        assert event.is_internal == 1, (
            f"Expected is_internal=1 for intra-wallet transfer, got {event.is_internal}"
        )

    def test_only_source_owned_sets_is_internal_0(self, db, monkeypatch):
        """
        When only the source is in owned_addresses (outgoing to external),
        is_internal=0.
        """
        _seed_wallets(db)
        _seed_sync_state(db, WALLET_A)

        logs = [_make_log("LOG_OUT_01", source=WALLET_A, dest=EXTERNAL)]
        owned = {WALLET_A, WALLET_B}  # EXTERNAL is not owned

        async def _fake_price(_db, _date):
            return {"eur": 0.00015, "usd": 0.00017}

        import app.services.sync_engine as engine_mod
        monkeypatch.setattr(engine_mod, "get_price_for_date", _fake_price)

        async def _noop_broadcast(_event_type, _payload):
            pass

        monkeypatch.setattr(engine_mod.manager, "broadcast", _noop_broadcast)

        _run(engine_mod._persist_logs(db, WALLET_A, logs, owned))

        event = db.query(Event).filter(Event.id == "LOG_OUT_01").first()
        assert event is not None
        assert event.is_internal == 0, (
            f"Expected is_internal=0 for outgoing transfer, got {event.is_internal}"
        )

    def test_only_destination_owned_sets_is_internal_0(self, db, monkeypatch):
        """
        When only the destination is owned (incoming from external), is_internal=0.
        """
        _seed_wallets(db)
        _seed_sync_state(db, WALLET_A)

        logs = [_make_log("LOG_IN_01", source=EXTERNAL, dest=WALLET_A)]
        owned = {WALLET_A, WALLET_B}

        async def _fake_price(_db, _date):
            return {"eur": 0.00015, "usd": 0.00017}

        import app.services.sync_engine as engine_mod
        monkeypatch.setattr(engine_mod, "get_price_for_date", _fake_price)

        async def _noop_broadcast(_event_type, _payload):
            pass

        monkeypatch.setattr(engine_mod.manager, "broadcast", _noop_broadcast)

        _run(engine_mod._persist_logs(db, WALLET_A, logs, owned))

        event = db.query(Event).filter(Event.id == "LOG_IN_01").first()
        assert event is not None
        assert event.is_internal == 0, (
            f"Expected is_internal=0 for incoming transfer from external, got {event.is_internal}"
        )

    def test_transfer_not_involving_wallet_is_skipped(self, db, monkeypatch):
        """
        Transfers where neither source nor destination is the synced wallet
        must be filtered out. BOB/RPC responses can contain unfiltered
        network-wide data; only events that actually touch wallet_id are stored.
        """
        _seed_wallets(db)
        _seed_sync_state(db, WALLET_A)

        logs = [_make_log("LOG_UNKNOWN_01", source=EXTERNAL, dest="ADDR_ANOTHER_EXTERNAL")]
        owned = {WALLET_A, WALLET_B}

        async def _fake_price(_db, _date):
            return {"eur": None, "usd": None}

        import app.services.sync_engine as engine_mod
        monkeypatch.setattr(engine_mod, "get_price_for_date", _fake_price)

        async def _noop_broadcast(_event_type, _payload):
            pass

        monkeypatch.setattr(engine_mod.manager, "broadcast", _noop_broadcast)

        _run(engine_mod._persist_logs(db, WALLET_A, logs, owned))

        event = db.query(Event).filter(Event.id == "LOG_UNKNOWN_01").first()
        assert event is None, (
            "Transfer between two external addresses must not be persisted for WALLET_A"
        )

    def test_duplicate_log_id_not_inserted_twice(self, db, monkeypatch):
        """
        If the same logId is processed a second time it should be skipped (idempotent).
        """
        _seed_wallets(db)
        _seed_sync_state(db, WALLET_A)

        log = _make_log("LOG_DUP_01", source=EXTERNAL, dest=WALLET_A)
        owned = {WALLET_A, WALLET_B}

        async def _fake_price(_db, _date):
            return {"eur": 0.00015, "usd": 0.00017}

        import app.services.sync_engine as engine_mod
        monkeypatch.setattr(engine_mod, "get_price_for_date", _fake_price)

        async def _noop_broadcast(_event_type, _payload):
            pass

        monkeypatch.setattr(engine_mod.manager, "broadcast", _noop_broadcast)

        # First call
        _run(engine_mod._persist_logs(db, WALLET_A, [log], owned))
        # Second call with the same log
        _run(engine_mod._persist_logs(db, WALLET_A, [log], owned))

        count = db.query(Event).filter(Event.id == "LOG_DUP_01").count()
        assert count == 1, f"Expected 1 event but found {count} (duplicate insertion)"

    def test_log_without_log_id_skipped(self, db, monkeypatch):
        """
        Logs that have no logId should be silently skipped.
        """
        _seed_wallets(db)
        _seed_sync_state(db, WALLET_A)

        log = {
            "epoch": 100, "tickNumber": 10000, "timestamp": "1700000000000",
            "quTransfer": {"source": EXTERNAL, "destination": WALLET_A, "amount": "50"},
        }
        owned = {WALLET_A}

        async def _fake_price(_db, _date):
            return {"eur": None, "usd": None}

        import app.services.sync_engine as engine_mod
        monkeypatch.setattr(engine_mod, "get_price_for_date", _fake_price)

        async def _noop_broadcast(_event_type, _payload):
            pass

        monkeypatch.setattr(engine_mod.manager, "broadcast", _noop_broadcast)

        # Should not raise
        _run(engine_mod._persist_logs(db, WALLET_A, [log], owned))

        # Nothing should have been inserted (no logId)
        count = db.query(Event).count()
        assert count == 0

    def test_price_stored_on_event(self, db, monkeypatch):
        """
        The EUR rate returned by get_price_for_date must be stored on the event.
        """
        _seed_wallets(db)
        _seed_sync_state(db, WALLET_A)

        logs = [_make_log("LOG_PRICE_01", source=EXTERNAL, dest=WALLET_A, amount=500)]
        owned = {WALLET_A}

        async def _fake_price(_db, _date):
            return {"eur": 0.00042, "usd": 0.00045}

        import app.services.sync_engine as engine_mod
        monkeypatch.setattr(engine_mod, "get_price_for_date", _fake_price)

        async def _noop_broadcast(_event_type, _payload):
            pass

        monkeypatch.setattr(engine_mod.manager, "broadcast", _noop_broadcast)

        _run(engine_mod._persist_logs(db, WALLET_A, logs, owned))

        event = db.query(Event).filter(Event.id == "LOG_PRICE_01").first()
        assert event is not None
        assert event.qubic_eur_rate == pytest.approx(0.00042)
        assert event.qubic_usd_rate == pytest.approx(0.00045)

    def test_total_events_counter_incremented(self, db, monkeypatch):
        """
        After persisting N new events, SyncState.total_events should increase by N.
        """
        _seed_wallets(db)
        _seed_sync_state(db, WALLET_A)

        logs = [
            _make_log("LOG_CNT_01", source=EXTERNAL, dest=WALLET_A),
            _make_log("LOG_CNT_02", source=EXTERNAL, dest=WALLET_A),
        ]
        owned = {WALLET_A}

        async def _fake_price(_db, _date):
            return {"eur": 0.00015, "usd": 0.00017}

        import app.services.sync_engine as engine_mod
        monkeypatch.setattr(engine_mod, "get_price_for_date", _fake_price)

        async def _noop_broadcast(_event_type, _payload):
            pass

        monkeypatch.setattr(engine_mod.manager, "broadcast", _noop_broadcast)

        _run(engine_mod._persist_logs(db, WALLET_A, logs, owned))

        state = db.query(SyncState).filter(SyncState.wallet_id == WALLET_A).first()
        assert state.total_events == 2
