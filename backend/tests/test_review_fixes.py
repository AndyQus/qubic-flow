"""
Tests for all 7 fixes from the code review + security audit (2026-05-08).

Fix 1 (CRITICAL): health_monitor.py — BOB-Node health status indentation bug
Fix 2 (CRITICAL): nodes.py — _run_diagnose uses own SessionLocal, not request session
Fix 3 (HIGH):     nodes.py — _fetch_raw only called on BOBClient, not RPCClient
Fix 4 (HIGH):     nodes.py — sync-now and diagnose endpoints have running-guard (429)
Fix 5 (HIGH):     EventsTable + WalletDetail — source_type filter sent to backend
Fix 6 (MEDIUM):   schemas/node.py — node_type must be "RPC" or "BOB_NODE"
Fix 7 (MEDIUM):   schemas/node.py — SSRF URL validation blocks private/localhost IPs
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(db, url="https://rpc.qubic.org", node_type="RPC", is_active=1, priority=1):
    from app.models.node import Node
    from app.utils.time import now_utc_iso
    n = Node(
        url=url,
        node_type=node_type,
        label=None,
        priority=priority,
        is_active=is_active,
        health_status="UNKNOWN",
        fail_count=0,
        last_checked=now_utc_iso(),
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


# ─────────────────────────────────────────────────────────────────────────────
# Fix 1 — health_monitor.py: BOB-Node gets tick/health_status after check
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthMonitorBOBNode:
    """BOB-Node must have tick, response_time_ms, health_status set after a successful check."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_bob_node_health_status_set_to_online(self, db):
        from app.services.health_monitor import _check_node
        node = _make_node(db, url="https://bobnet.qubic.li", node_type="BOB_NODE")

        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": 20_000_000}

        async def _fake_post(*a, **kw):
            return rpc_resp

        async def _fake_get(*a, **kw):
            return rpc_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_instance.post = AsyncMock(return_value=rpc_resp)
            mock_client_instance.get = AsyncMock(return_value=rpc_resp)
            MockClient.return_value = mock_client_instance

            self._run(_check_node(db, node))

        assert node.health_status in ("ONLINE", "DEGRADED"), (
            f"Expected ONLINE or DEGRADED, got {node.health_status!r} — "
            "indentation bug still present"
        )

    def test_bob_node_tick_set_after_check(self, db):
        from app.services.health_monitor import _check_node
        node = _make_node(db, url="https://bobnet.qubic.li", node_type="BOB_NODE")

        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": 20_000_000}

        with patch("httpx.AsyncClient") as MockClient:
            mock_ci = AsyncMock()
            mock_ci.__aenter__ = AsyncMock(return_value=mock_ci)
            mock_ci.__aexit__ = AsyncMock(return_value=False)
            mock_ci.post = AsyncMock(return_value=rpc_resp)
            mock_ci.get = AsyncMock(return_value=rpc_resp)
            MockClient.return_value = mock_ci
            self._run(_check_node(db, node))

        assert node.tick == 20_000_000

    def test_bob_node_response_time_set_after_check(self, db):
        from app.services.health_monitor import _check_node
        node = _make_node(db, url="https://bobnet.qubic.li", node_type="BOB_NODE")

        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": 20_000_000}

        with patch("httpx.AsyncClient") as MockClient:
            mock_ci = AsyncMock()
            mock_ci.__aenter__ = AsyncMock(return_value=mock_ci)
            mock_ci.__aexit__ = AsyncMock(return_value=False)
            mock_ci.post = AsyncMock(return_value=rpc_resp)
            mock_ci.get = AsyncMock(return_value=rpc_resp)
            MockClient.return_value = mock_ci
            self._run(_check_node(db, node))

        assert node.response_time_ms is not None and node.response_time_ms >= 0

    def test_bob_node_fail_count_reset_on_success(self, db):
        from app.services.health_monitor import _check_node
        node = _make_node(db, url="https://bobnet.qubic.li", node_type="BOB_NODE")
        node.fail_count = 5
        db.commit()

        rpc_resp = MagicMock()
        rpc_resp.raise_for_status = MagicMock()
        rpc_resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": 20_000_000}

        with patch("httpx.AsyncClient") as MockClient:
            mock_ci = AsyncMock()
            mock_ci.__aenter__ = AsyncMock(return_value=mock_ci)
            mock_ci.__aexit__ = AsyncMock(return_value=False)
            mock_ci.post = AsyncMock(return_value=rpc_resp)
            mock_ci.get = AsyncMock(return_value=rpc_resp)
            MockClient.return_value = mock_ci
            self._run(_check_node(db, node))

        assert node.fail_count == 0

    def test_rpc_node_health_status_still_set(self, db):
        """RPC nodes must still get health_status — regression guard."""
        from app.services.health_monitor import _check_node
        node = _make_node(db, url="https://rpc.qubic.org", node_type="RPC")

        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()
        ok_resp.json.return_value = {"tickInfo": {"tick": 19_000_000}}

        with patch("httpx.AsyncClient") as MockClient:
            mock_ci = AsyncMock()
            mock_ci.__aenter__ = AsyncMock(return_value=mock_ci)
            mock_ci.__aexit__ = AsyncMock(return_value=False)
            mock_ci.get = AsyncMock(return_value=ok_resp)
            MockClient.return_value = mock_ci
            self._run(_check_node(db, node))

        assert node.health_status in ("ONLINE", "DEGRADED")
        assert node.tick == 19_000_000


# ─────────────────────────────────────────────────────────────────────────────
# Fix 2 — _run_diagnose uses its own SessionLocal (not the request session)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunDiagnoseOwnSession:
    """_run_diagnose must open its own DB session via SessionLocal."""

    def test_run_diagnose_does_not_require_request_session(self):
        """_run_diagnose must not have a `db` parameter — fix removed it."""
        from app.api.v1.nodes import _run_diagnose
        import inspect
        sig = inspect.signature(_run_diagnose)
        assert "db" not in sig.parameters, (
            "_run_diagnose still takes a `db` parameter — it must use its own SessionLocal"
        )

    def test_run_diagnose_opens_session_local(self):
        """SessionLocal must be called inside _run_diagnose."""
        from app.api.v1 import nodes as nodes_module

        opened = []

        class FakeSession:
            def query(self, *a): return self
            def filter(self, *a): return self
            def order_by(self, *a): return self
            def all(self): return []
            def close(self): opened.append("closed")

        loop = asyncio.new_event_loop()
        try:
            with patch.object(nodes_module, "SessionLocal", return_value=FakeSession()):
                with patch("app.services.sync_engine._get_event_client", new=AsyncMock(side_effect=Exception("skip"))):
                    with patch("app.services.sync_engine._get_rpc_client", side_effect=Exception("skip")):
                        loop.run_until_complete(nodes_module._run_diagnose())
        finally:
            loop.close()

        assert "closed" in opened, "SessionLocal session was never closed — missing finally block"


# ─────────────────────────────────────────────────────────────────────────────
# Fix 3 — _fetch_raw only called on BOBClient, not RPCClient
# ─────────────────────────────────────────────────────────────────────────────

class TestDiagnoseNoFetchRawOnRPC:
    """When event_client is RPCClient, _fetch_raw must NOT be called."""

    def test_rpc_client_fetch_raw_not_called(self):
        """A real RPCClient object must not trigger _fetch_raw in _run_diagnose.
        isinstance(rpc_client, BOBClient) is False, so the guard works correctly."""
        from app.api.v1 import nodes as nodes_module
        from app.services.qubic_client import RPCClient

        # Use actual RPCClient so isinstance(client, BOBClient) is genuinely False
        rpc_client = RPCClient.__new__(RPCClient)
        rpc_client.base_url = "https://rpc.qubic.org"
        rpc_client.get_current_tick = AsyncMock(return_value=20_000_000)

        fetch_raw_called = []
        rpc_client._fetch_raw = lambda *a, **kw: fetch_raw_called.append(True)

        class FakeSession:
            def query(self, *a): return self
            def filter(self, *a): return self
            def order_by(self, *a): return self
            def all(self): return []
            def close(self): pass

        loop = asyncio.new_event_loop()
        try:
            with patch.object(nodes_module, "SessionLocal", return_value=FakeSession()):
                with patch("app.services.sync_engine._get_event_client", new=AsyncMock(return_value=rpc_client)):
                    with patch("app.services.sync_engine._get_rpc_client", return_value=rpc_client):
                        loop.run_until_complete(nodes_module._run_diagnose())
        finally:
            loop.close()

        assert not fetch_raw_called, "_fetch_raw was called on RPCClient — isinstance guard missing"

    def test_bob_client_fetch_raw_is_called(self):
        from app.api.v1 import nodes as nodes_module
        from app.services.qubic_client import BOBClient

        fake_bob = MagicMock(spec=BOBClient)
        fake_bob.base_url = "https://bobnet.qubic.li"
        fake_bob.get_current_tick = AsyncMock(return_value=20_000_000)
        fake_bob._fetch_raw = AsyncMock(return_value=([], 20_000_000))

        fake_rpc = MagicMock()
        fake_rpc.base_url = "https://rpc.qubic.org"
        fake_rpc.get_current_tick = AsyncMock(return_value=20_000_000)

        class FakeSession:
            def query(self, *a): return self
            def filter(self, *a): return self
            def order_by(self, *a): return self
            def all(self): return []
            def close(self): pass

        loop = asyncio.new_event_loop()
        try:
            with patch.object(nodes_module, "SessionLocal", return_value=FakeSession()):
                with patch("app.services.sync_engine._get_event_client", new=AsyncMock(return_value=fake_bob)):
                    with patch("app.services.sync_engine._get_rpc_client", return_value=fake_rpc):
                        loop.run_until_complete(nodes_module._run_diagnose())
        finally:
            loop.close()

        fake_bob._fetch_raw.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Fix 4 — sync-now and diagnose: 429 when already running
# ─────────────────────────────────────────────────────────────────────────────

class TestRunningGuard:
    """POST /nodes/sync-now and /nodes/diagnose return 429 when already running."""

    def test_sync_now_returns_202_when_idle(self, client, db):
        import app.api.v1.nodes as nodes_module
        nodes_module._sync_running = False
        with patch("app.services.sync_engine.sync_all_wallets", new=AsyncMock()):
            resp = client.post("/api/v1/nodes/sync-now")
        nodes_module._sync_running = False
        assert resp.status_code == 202

    def test_sync_now_returns_429_when_running(self, client, db):
        import app.api.v1.nodes as nodes_module
        nodes_module._sync_running = True
        try:
            resp = client.post("/api/v1/nodes/sync-now")
            assert resp.status_code == 429
        finally:
            nodes_module._sync_running = False

    def test_diagnose_returns_202_when_idle(self, client, db):
        import app.api.v1.nodes as nodes_module
        nodes_module._diagnose_running = False

        class FakeSession:
            def query(self, *a): return self
            def filter(self, *a): return self
            def order_by(self, *a): return self
            def all(self): return []
            def close(self): pass

        with patch.object(nodes_module, "SessionLocal", return_value=FakeSession()):
            resp = client.post("/api/v1/nodes/diagnose")
        nodes_module._diagnose_running = False
        assert resp.status_code == 202

    def test_diagnose_returns_429_when_running(self, client, db):
        import app.api.v1.nodes as nodes_module
        nodes_module._diagnose_running = True
        try:
            resp = client.post("/api/v1/nodes/diagnose")
            assert resp.status_code == 429
        finally:
            nodes_module._diagnose_running = False


# ─────────────────────────────────────────────────────────────────────────────
# Fix 5 — Events API: source_type filter is forwarded to the backend
# ─────────────────────────────────────────────────────────────────────────────

class TestSourceTypeFilter:
    """GET /events and /events/count must accept and apply source_type."""

    def _make_wallet(self, db):
        from app.models.wallet import Wallet
        from app.utils.time import now_utc_iso
        addr = "A" * 60
        w = Wallet(id=addr, label="test", active=1, wallet_type="PRIVATE", created_at=now_utc_iso())
        db.add(w)
        db.commit()
        return addr

    def _make_events(self, db, wallet_id):
        from app.models.event import Event
        import datetime
        now = datetime.datetime.now(datetime.UTC).isoformat()
        for i, src_type in enumerate(("TX", "EVENT", "TX")):
            e = Event(
                id=f"evt_{i}_{src_type}",
                wallet_id=wallet_id,
                source_type=src_type,
                amount_qubic=100,
                timestamp=now,
                epoch=100,
            )
            db.add(e)
        db.commit()

    def test_list_events_filter_tx_only(self, client, db):
        wid = self._make_wallet(db)
        self._make_events(db, wid)

        resp = client.get(f"/api/v1/events?wallet_id={wid}&source_type=TX")
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["source_type"] == "TX" for e in data), (
            f"source_type=TX filter returned non-TX events: {data}"
        )

    def test_list_events_filter_event_only(self, client, db):
        wid = self._make_wallet(db)
        self._make_events(db, wid)

        resp = client.get(f"/api/v1/events?wallet_id={wid}&source_type=EVENT")
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["source_type"] == "EVENT" for e in data)

    def test_list_events_filter_all_returns_all(self, client, db):
        wid = self._make_wallet(db)
        self._make_events(db, wid)

        resp_all = client.get(f"/api/v1/events?wallet_id={wid}")
        resp_filtered = client.get(f"/api/v1/events?wallet_id={wid}&source_type=ALL")
        assert len(resp_all.json()) == len(resp_filtered.json())

    def test_count_events_respects_source_type(self, client, db):
        wid = self._make_wallet(db)
        self._make_events(db, wid)  # 2 TX + 1 EVENT

        resp_tx = client.get(f"/api/v1/events/count?wallet_id={wid}&source_type=TX")
        resp_ev = client.get(f"/api/v1/events/count?wallet_id={wid}&source_type=EVENT")
        assert resp_tx.json()["count"] == 2
        assert resp_ev.json()["count"] == 1

    def test_count_and_list_consistent(self, client, db):
        wid = self._make_wallet(db)
        self._make_events(db, wid)

        for src in ("TX", "EVENT"):
            cnt = client.get(f"/api/v1/events/count?wallet_id={wid}&source_type={src}").json()["count"]
            lst = client.get(f"/api/v1/events?wallet_id={wid}&source_type={src}").json()
            assert cnt == len(lst), (
                f"count endpoint ({cnt}) and list endpoint ({len(lst)}) disagree for source_type={src}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Fix 6 — node_type must be "RPC" or "BOB_NODE"
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeTypeValidation:
    """NodeCreate.node_type must only accept 'RPC' or 'BOB_NODE'."""

    def test_rpc_is_valid(self):
        from app.schemas.node import NodeCreate
        n = NodeCreate(url="https://rpc.qubic.org", node_type="RPC")
        assert n.node_type == "RPC"

    def test_bob_node_is_valid(self):
        from app.schemas.node import NodeCreate
        n = NodeCreate(url="https://bobnet.qubic.li", node_type="BOB_NODE")
        assert n.node_type == "BOB_NODE"

    def test_invalid_node_type_rejected(self):
        from app.schemas.node import NodeCreate
        with pytest.raises(ValidationError):
            NodeCreate(url="https://rpc.qubic.org", node_type="EVIL")

    def test_empty_node_type_rejected(self):
        from app.schemas.node import NodeCreate
        with pytest.raises(ValidationError):
            NodeCreate(url="https://rpc.qubic.org", node_type="")

    def test_api_rejects_invalid_node_type(self, client, db):
        resp = client.post("/api/v1/nodes", json={
            "url": "https://rpc.qubic.org",
            "node_type": "UNKNOWN",
            "priority": 1,
        })
        assert resp.status_code == 422

    def test_api_accepts_rpc_node_type(self, client, db):
        resp = client.post("/api/v1/nodes", json={
            "url": "https://rpc.qubic.org",
            "node_type": "RPC",
            "priority": 1,
        })
        assert resp.status_code == 201


# ─────────────────────────────────────────────────────────────────────────────
# Fix 7 — SSRF: URL validator blocks localhost and private IPs
# ─────────────────────────────────────────────────────────────────────────────

class TestSSRFUrlValidation:
    """NodeCreate.url must block localhost, private IPs, and non-http(s) schemes."""

    @pytest.mark.parametrize("url", [
        "https://rpc.qubic.org",
        "https://bobnet.qubic.li",
        "http://public-node.example.com",
        "https://public-node.example.com:8080",
    ])
    def test_valid_public_urls_accepted(self, url):
        from app.schemas.node import NodeCreate
        n = NodeCreate(url=url, node_type="RPC")
        assert n.url == url

    @pytest.mark.parametrize("url", [
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
        "http://0.0.0.0",
    ])
    def test_localhost_urls_rejected(self, url):
        from app.schemas.node import NodeCreate
        with pytest.raises(ValidationError, match="localhost"):
            NodeCreate(url=url, node_type="RPC")

    @pytest.mark.parametrize("url", [
        "http://10.0.0.1",
        "http://10.255.255.255",
        "http://192.168.1.1",
        "http://192.168.0.100",
        "http://169.254.169.254",      # AWS metadata
        "http://172.16.0.1",
    ])
    def test_private_ip_ranges_rejected(self, url):
        from app.schemas.node import NodeCreate
        with pytest.raises(ValidationError):
            NodeCreate(url=url, node_type="RPC")

    @pytest.mark.parametrize("url", [
        "ftp://rpc.qubic.org",
        "file:///etc/passwd",
        "ssh://rpc.qubic.org",
    ])
    def test_non_http_schemes_rejected(self, url):
        from app.schemas.node import NodeCreate
        with pytest.raises(ValidationError, match="http"):
            NodeCreate(url=url, node_type="RPC")

    def test_notes_max_length_enforced(self):
        from app.schemas.node import NodeCreate
        with pytest.raises(ValidationError):
            NodeCreate(url="https://rpc.qubic.org", node_type="RPC", notes="x" * 2001)

    def test_notes_at_max_length_accepted(self):
        from app.schemas.node import NodeCreate
        n = NodeCreate(url="https://rpc.qubic.org", node_type="RPC", notes="x" * 2000)
        assert len(n.notes) == 2000

    def test_api_rejects_localhost_url(self, client, db):
        resp = client.post("/api/v1/nodes", json={
            "url": "http://localhost:8000",
            "node_type": "RPC",
            "priority": 1,
        })
        assert resp.status_code == 422

    def test_api_rejects_private_ip(self, client, db):
        resp = client.post("/api/v1/nodes", json={
            "url": "http://192.168.1.1",
            "node_type": "RPC",
            "priority": 1,
        })
        assert resp.status_code == 422
