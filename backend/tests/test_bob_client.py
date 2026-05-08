"""
Unit-Tests für BOBClient und _map_bob_transfer.
Alle HTTP-Anfragen werden mit unittest.mock gemockt — kein Netz nötig.

Nach dem Refactoring (2026-05-08) verwendet BOBClient:
  - _rpc(method, params)   statt _request("POST", ...)
  - _http_get(path)        statt _request("GET", ...)
  - _map_bob_transfer unterstützt jetzt body:{from,to} (qubic_getTransfers)
    sowie source/destination direkt auf dem Transfer (qubic_getLogs)
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.qubic_client import BOBClient, _map_bob_transfer


# ─────────────────────────────────────────────────────────────
# Hilfsfunktion: _rpc und _http_get patchen
# ─────────────────────────────────────────────────────────────

def _patch_rpc(return_value=None, side_effect=None):
    """Patch BOBClient._rpc mit einer fixen Antwort."""
    if side_effect:
        return patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=side_effect))
    return patch.object(BOBClient, "_rpc", new=AsyncMock(return_value=return_value))


def _patch_http_get(return_value=None, side_effect=None):
    """Patch BOBClient._http_get mit einer fixen Antwort."""
    if side_effect:
        return patch.object(BOBClient, "_http_get", new=AsyncMock(side_effect=side_effect))
    return patch.object(BOBClient, "_http_get", new=AsyncMock(return_value=return_value))


# ═════════════════════════════════════════════════════════════
# _map_bob_transfer
# ═════════════════════════════════════════════════════════════

class TestMapBobTransfer:
    def test_standard_fields_qubic_get_transfers(self):
        """qubic_getTransfers format: body.from/to with top-level timestamp."""
        t = {
            "logId": 42, "epoch": 210, "tick": 50000000, "type": 0,
            "timestamp": 1700000000,
            "body": {"from": "AAAA", "to": "BBBB", "amount": 1000},
        }
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["source"] == "AAAA"
        assert result["quTransfer"]["destination"] == "BBBB"
        assert result["quTransfer"]["amount"] == "1000"
        assert result["epoch"] == 210
        assert result["tickNumber"] == 50000000
        assert result["timestamp"] == "1700000000000"

    def test_qubic_get_transfers_body_format(self):
        """qubic_getTransfers format: addresses in body.from/to."""
        t = {
            "logId": 1, "epoch": 1, "tick": 1, "type": 0,
            "body": {"from": "CCCC", "to": "DDDD", "amount": 500},
        }
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["source"] == "CCCC"
        assert result["quTransfer"]["destination"] == "DDDD"
        assert result["quTransfer"]["amount"] == "500"

    def test_qubic_get_logs_direct_fields(self):
        """qubic_getLogs format: source/destination directly on transfer."""
        t = {
            "logId": 1, "epoch": 1, "tick": 1, "logType": 0,
            "source": "EEEE", "destination": "FFFF", "amount": 250,
        }
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["source"] == "EEEE"
        assert result["quTransfer"]["destination"] == "FFFF"
        assert result["quTransfer"]["amount"] == "250"

    def test_alternative_field_names_from_to(self):
        """from/to as top-level keys (some BOB variants)."""
        t = {
            "logId": 1, "epoch": 1, "tick": 1, "logType": 0,
            "from": "CCCC", "to": "DDDD", "amount": 500,
        }
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["source"] == "CCCC"
        assert result["quTransfer"]["destination"] == "DDDD"

    def test_alternative_field_names_source_destination(self):
        """source/destination as top-level fields (qubic_getLogs format)."""
        t = {
            "logId": 1, "epoch": 1, "tick": 1, "logType": 0,
            "source": "EEEE", "destination": "FFFF", "amount": 250,
        }
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["source"] == "EEEE"
        assert result["quTransfer"]["destination"] == "FFFF"

    def test_missing_message_returns_empty_strings(self):
        t = {"logId": 1, "epoch": 1, "tick": 1, "logType": 0}
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["source"] == ""
        assert result["quTransfer"]["destination"] == ""
        assert result["quTransfer"]["amount"] == "0"

    def test_log_digest_set(self):
        t = {"logId": 99, "epoch": 1, "tick": 1, "logType": 0, "message": {}}
        result = _map_bob_transfer(t)
        assert result["logDigest"] == result["logId"]

    def test_zero_amount(self):
        t = {"logId": 1, "epoch": 1, "tick": 1, "logType": 0,
             "message": {"sourceId": "A", "destId": "B", "amount": 0}}
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["amount"] == "0"

    def test_transaction_hash_used_as_log_id(self):
        """txHash/transactionHash takes priority over logId as the event key."""
        t = {
            "logId": 1, "epoch": 1, "tick": 1, "logType": 0,
            "txHash": "abcdef" * 10, "message": {},
        }
        result = _map_bob_transfer(t)
        assert result["logId"] == "abcdef" * 10


# ═════════════════════════════════════════════════════════════
# BOBClient.get_current_tick
# ═════════════════════════════════════════════════════════════

class TestBobGetCurrentTick:
    @pytest.mark.asyncio
    async def test_uses_rpc_tick_number(self):
        """Primary path: qubic_getTickNumber via JSON-RPC."""
        with _patch_rpc(return_value=50214322):
            tick = await BOBClient("http://bob:40420").get_current_tick()
        assert tick == 50214322

    @pytest.mark.asyncio
    async def test_falls_back_to_http_status(self):
        """If RPC fails, falls back to GET /status."""
        import httpx
        with _patch_rpc(side_effect=httpx.TimeoutException("timeout")):
            with _patch_http_get(return_value={"currentTick": 50214000}):
                tick = await BOBClient("http://bob:40420").get_current_tick()
        assert tick == 50214000

    @pytest.mark.asyncio
    async def test_falls_back_to_fetching_tick(self):
        """Falls back to currentFetchingTick in /status response."""
        import httpx
        with _patch_rpc(side_effect=httpx.TimeoutException("timeout")):
            with _patch_http_get(return_value={"currentFetchingTick": 50214000}):
                tick = await BOBClient("http://bob:40420").get_current_tick()
        assert tick == 50214000

    @pytest.mark.asyncio
    async def test_falls_back_to_verified_tick(self):
        import httpx
        with _patch_rpc(side_effect=httpx.TimeoutException("timeout")):
            with _patch_http_get(return_value={"verifiedTick": 50210000}):
                tick = await BOBClient("http://bob:40420").get_current_tick()
        assert tick == 50210000

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_tick_field(self):
        import httpx
        with _patch_rpc(side_effect=httpx.TimeoutException("timeout")):
            with _patch_http_get(return_value={"status": "ok"}):
                tick = await BOBClient("http://bob:40420").get_current_tick()
        assert tick == 0


# ═════════════════════════════════════════════════════════════
# BOBClient.get_event_logs
# ═════════════════════════════════════════════════════════════

WALLET = "A" * 60

BOB_TRANSFER_RESPONSE = {
    "transfers": [
        {"logId": 1, "epoch": 210, "tick": 50214000, "logType": 0,
         "body": {"from": "B" * 60, "to": WALLET, "amount": 12}},
        {"logId": 2, "epoch": 210, "tick": 50214001, "logType": 0,
         "body": {"from": WALLET, "to": "C" * 60, "amount": 500}},
    ],
    "fromTick": 50214000,
    "toTick": 50214001,
}


class TestBobGetEventLogs:
    @pytest.mark.asyncio
    async def test_returns_mapped_transfers(self):
        async def mock_rpc(method, params=None):
            if method == "qubic_getTransfers":
                return BOB_TRANSFER_RESPONSE
            if method == "qubic_getTickByNumber":
                return {"timestamp": 1700000000}
            return None

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            result = await client.get_event_logs(WALLET, 50214000, 50214500)

        logs = result["eventLogs"]
        assert len(logs) == 2
        assert logs[0]["quTransfer"]["destination"] == WALLET
        assert logs[0]["quTransfer"]["amount"] == "12"
        assert logs[1]["quTransfer"]["source"] == WALLET

    @pytest.mark.asyncio
    async def test_empty_transfers_returns_zero_count(self):
        async def mock_rpc(method, params=None):
            return {"transfers": [], "fromTick": 1, "toTick": 1}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            result = await client.get_event_logs(WALLET, 1, 100)

        assert result["hits"]["total"] == 0
        assert result["eventLogs"] == []

    @pytest.mark.asyncio
    async def test_result_is_cached(self):
        """get_event_logs für denselben (wallet, from, to) darf nur einen API-Call machen."""
        call_count = 0

        async def mock_rpc(method, params=None):
            nonlocal call_count
            if method == "qubic_getTransfers":
                call_count += 1
            return {"transfers": [], "fromTick": 1, "toTick": 1}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            await client.get_event_logs(WALLET, 1, 100)
            await client.get_event_logs(WALLET, 1, 100)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_null_transfers_field_handled(self):
        """Wenn 'transfers' None ist, soll keine Exception auftreten."""
        async def mock_rpc(method, params=None):
            return {"transfers": None}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            result = await client.get_event_logs(WALLET, 1, 100)

        assert result["hits"]["total"] == 0

    @pytest.mark.asyncio
    async def test_falls_back_to_qubic_get_logs_on_rpc_failure(self):
        """If qubic_getTransfers fails, falls back to qubic_getLogs."""
        import httpx

        async def mock_rpc(method, params=None):
            if method == "qubic_getTransfers":
                raise httpx.TimeoutException("timeout")
            if method == "qubic_getLogs":
                return [{"logId": 99, "epoch": 1, "tick": 1, "logType": 0,
                         "source": WALLET, "destination": "B" * 60, "amount": 10}]
            if method == "qubic_getTickByNumber":
                return {"timestamp": 1700000000}
            return None

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            result = await client.get_event_logs(WALLET, 1, 100)

        assert result["hits"]["total"] == 1


# ═════════════════════════════════════════════════════════════
# BOBClient._get_tick_timestamp
# ═════════════════════════════════════════════════════════════

class TestBobTickTimestamp:
    @pytest.mark.asyncio
    async def test_converts_unix_seconds_to_ms(self):
        """Wenn BOB Unix-Sekunden zurückgibt (<1e12), muss mit 1000 multipliziert werden."""
        async def mock_rpc(method, params=None):
            return {"timestamp": 1700000000}  # Sekunden

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            ts = await client._get_tick_timestamp(12345)

        assert ts == "1700000000000"

    @pytest.mark.asyncio
    async def test_unix_ms_not_doubled(self):
        """Wenn BOB bereits Millisekunden zurückgibt (>1e12), nicht nochmal x1000."""
        async def mock_rpc(method, params=None):
            return {"timestamp": 1700000000000}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            ts = await client._get_tick_timestamp(12345)

        assert ts == "1700000000000"

    @pytest.mark.asyncio
    async def test_nested_tick_timestamp(self):
        """Timestamp kann direkt im result-dict sein (nicht verschachtelt in tick)."""
        async def mock_rpc(method, params=None):
            # qubic_getTickByNumber returns the tick object directly as result
            return {"timestamp": 1700000000}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            ts = await client._get_tick_timestamp(12345)

        assert ts == "1700000000000"

    @pytest.mark.asyncio
    async def test_returns_zero_on_rpc_error_with_no_http_fallback(self):
        """Bei RPC-Fehler und ohne /tick-Daten wird '0' zurückgegeben."""
        import httpx
        async def mock_rpc(method, params=None):
            raise httpx.TimeoutException("timeout")

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            with _patch_http_get(return_value={}):
                ts = await client._get_tick_timestamp(12345)

        assert ts == "0"

    @pytest.mark.asyncio
    async def test_result_is_cached(self):
        """Gleicher Tick wird nur einmal nachgeschlagen."""
        call_count = 0

        async def mock_rpc(method, params=None):
            nonlocal call_count
            call_count += 1
            return {"timestamp": 1700000000}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            await client._get_tick_timestamp(99)
            await client._get_tick_timestamp(99)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_new_tickdata_format_via_http(self):
        """Neues BOB-Format via /tick/{n}: {'tickdata': {day, month, hour, minute, second}}."""
        import httpx
        async def mock_rpc(method, params=None):
            raise httpx.TimeoutException("rpc down")

        async def mock_http_get(path):
            return {"tick": 12345, "tickdata": {"day": 24, "month": 4, "hour": 21, "minute": 18, "second": 13}}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_rpc", new=AsyncMock(side_effect=mock_rpc)):
            with patch.object(BOBClient, "_http_get", new=AsyncMock(side_effect=mock_http_get)):
                ts = await client._get_tick_timestamp(12345)

        assert ts != "0"
        assert int(ts) > 1_700_000_000_000
