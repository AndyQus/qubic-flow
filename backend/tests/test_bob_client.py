"""
Unit-Tests für BOBClient und _map_bob_transfer.
Alle HTTP-Anfragen werden mit unittest.mock gemockt — kein Netz nötig.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.qubic_client import BOBClient, _map_bob_transfer


# ─────────────────────────────────────────────────────────────
# Hilfsfunktion: httpx-Response mocken
# ─────────────────────────────────────────────────────────────

def _mock_response(json_data: dict, status_code: int = 200):
    """Erstellt ein Mock-Objekt, das wie eine httpx.Response aussieht."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=mock
        )
    return mock


def _patch_bob_request(json_data: dict, status_code: int = 200):
    """Patch BOBClient._request mit einer fixen Antwort."""
    return patch.object(
        BOBClient, "_request",
        new=AsyncMock(return_value=json_data if status_code < 400 else (_ for _ in ()).throw(
            __import__("httpx").HTTPStatusError("err", request=MagicMock(), response=MagicMock())
        ))
    )


# ═════════════════════════════════════════════════════════════
# _map_bob_transfer
# ═════════════════════════════════════════════════════════════

class TestMapBobTransfer:
    def test_standard_fields(self):
        t = {
            "logId": 42, "epoch": 210, "tick": 50000000, "logType": 0,
            "message": {"sourceId": "AAAA", "destId": "BBBB", "amount": 1000},
        }
        result = _map_bob_transfer(t, timestamp="1700000000000")
        assert result["quTransfer"]["source"] == "AAAA"
        assert result["quTransfer"]["destination"] == "BBBB"
        assert result["quTransfer"]["amount"] == "1000"
        assert result["epoch"] == 210
        assert result["tickNumber"] == 50000000
        assert result["timestamp"] == "1700000000000"
        assert result["logId"] == "42"

    def test_alternative_field_names_from_to(self):
        """BOB-Nodes können 'from'/'to' statt 'sourceId'/'destId' liefern."""
        t = {
            "logId": 1, "epoch": 1, "tick": 1, "logType": 0,
            "message": {"from": "CCCC", "to": "DDDD", "amount": 500},
        }
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["source"] == "CCCC"
        assert result["quTransfer"]["destination"] == "DDDD"

    def test_alternative_field_names_source_destination(self):
        t = {
            "logId": 1, "epoch": 1, "tick": 1, "logType": 0,
            "message": {"source": "EEEE", "destination": "FFFF", "amount": 250},
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

    def test_log_digest_equals_log_id(self):
        t = {"logId": 99, "epoch": 1, "tick": 1, "logType": 0, "message": {}}
        result = _map_bob_transfer(t)
        assert result["logDigest"] == "99"
        assert result["logId"] == "99"

    def test_zero_amount(self):
        t = {"logId": 1, "epoch": 1, "tick": 1, "logType": 0,
             "message": {"sourceId": "A", "destId": "B", "amount": 0}}
        result = _map_bob_transfer(t)
        assert result["quTransfer"]["amount"] == "0"


# ═════════════════════════════════════════════════════════════
# BOBClient.get_current_tick
# ═════════════════════════════════════════════════════════════

class TestBobGetCurrentTick:
    @pytest.mark.asyncio
    async def test_uses_current_tick_field(self):
        with patch.object(BOBClient, "_request", new=AsyncMock(return_value={"currentTick": 50214322})):
            client = BOBClient("http://bob:40420")
            tick = await client.get_current_tick()
        assert tick == 50214322

    @pytest.mark.asyncio
    async def test_falls_back_to_fetching_tick(self):
        with patch.object(BOBClient, "_request", new=AsyncMock(
            return_value={"currentFetchingTick": 50214000}
        )):
            tick = await BOBClient("http://bob:40420").get_current_tick()
        assert tick == 50214000

    @pytest.mark.asyncio
    async def test_falls_back_to_verified_tick(self):
        with patch.object(BOBClient, "_request", new=AsyncMock(
            return_value={"verifiedTick": 50210000}
        )):
            tick = await BOBClient("http://bob:40420").get_current_tick()
        assert tick == 50210000

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_tick_field(self):
        with patch.object(BOBClient, "_request", new=AsyncMock(return_value={"status": "ok"})):
            tick = await BOBClient("http://bob:40420").get_current_tick()
        assert tick == 0


# ═════════════════════════════════════════════════════════════
# BOBClient.get_event_logs
# ═════════════════════════════════════════════════════════════

WALLET = "A" * 60

BOB_TRANSFER_RESPONSE = {
    "transfers": [
        {"logId": 1, "epoch": 210, "tick": 50214000, "logType": 0,
         "message": {"sourceId": "B" * 60, "destId": WALLET, "amount": 12}},
        {"logId": 2, "epoch": 210, "tick": 50214001, "logType": 0,
         "message": {"sourceId": WALLET, "destId": "C" * 60, "amount": 500}},
    ]
}


class TestBobGetEventLogs:
    @pytest.mark.asyncio
    async def test_returns_mapped_transfers(self):
        async def mock_request(method, path, **kwargs):
            if path == "/getQuTransfersForIdentity":
                return BOB_TRANSFER_RESPONSE
            if path.startswith("/tick/"):
                return {"timestamp": 1700000000}
            return {}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            result = await client.get_event_logs(WALLET, 50214000, 50214500)  # < 999 Ticks → ein Chunk

        logs = result["eventLogs"]
        assert len(logs) == 2
        assert logs[0]["quTransfer"]["destination"] == WALLET
        assert logs[0]["quTransfer"]["amount"] == "12"
        assert logs[1]["quTransfer"]["source"] == WALLET

    @pytest.mark.asyncio
    async def test_empty_transfers_returns_zero_count(self):
        async def mock_request(method, path, **kwargs):
            return {"transfers": []}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            result = await client.get_event_logs(WALLET, 1, 100)

        assert result["hits"]["total"] == 0
        assert result["eventLogs"] == []

    @pytest.mark.asyncio
    async def test_result_is_cached(self):
        """get_event_logs fuer denselben (wallet, from, to) darf nur einen API-Call machen."""
        call_count = 0

        async def mock_request(method, path, **kwargs):
            nonlocal call_count
            if path == "/getQuTransfersForIdentity":
                call_count += 1
            return {"transfers": []}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            await client.get_event_logs(WALLET, 1, 100)
            await client.get_event_logs(WALLET, 1, 100)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_null_transfers_field_handled(self):
        """Wenn 'transfers' None ist, soll keine Exception auftreten."""
        async def mock_request(method, path, **kwargs):
            return {"transfers": None}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            result = await client.get_event_logs(WALLET, 1, 100)

        assert result["hits"]["total"] == 0


# ═════════════════════════════════════════════════════════════
# BOBClient._get_tick_timestamp
# ═════════════════════════════════════════════════════════════

class TestBobTickTimestamp:
    @pytest.mark.asyncio
    async def test_converts_unix_seconds_to_ms(self):
        """Wenn BOB Unix-Sekunden zurückgibt (<1e12), muss mit 1000 multipliziert werden."""
        async def mock_request(method, path, **kwargs):
            return {"timestamp": 1700000000}  # Sekunden

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            ts = await client._get_tick_timestamp(12345)

        assert ts == "1700000000000"

    @pytest.mark.asyncio
    async def test_unix_ms_not_doubled(self):
        """Wenn BOB bereits Millisekunden zurückgibt (>1e12), nicht nochmal x1000."""
        async def mock_request(method, path, **kwargs):
            return {"timestamp": 1700000000000}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            ts = await client._get_tick_timestamp(12345)

        assert ts == "1700000000000"

    @pytest.mark.asyncio
    async def test_nested_tick_timestamp(self):
        """Timestamp kann in 'tick.timestamp' verschachtelt sein."""
        async def mock_request(method, path, **kwargs):
            return {"tick": {"timestamp": 1700000000}}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            ts = await client._get_tick_timestamp(12345)

        assert ts == "1700000000000"

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self):
        """Bei API-Fehler wird '0' zurückgegeben, keine Exception."""
        import httpx
        async def mock_request(method, path, **kwargs):
            raise httpx.TimeoutException("timeout")

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            ts = await client._get_tick_timestamp(12345)

        assert ts == "0"

    @pytest.mark.asyncio
    async def test_result_is_cached(self):
        """Gleicher Tick wird nur einmal nachgeschlagen."""
        call_count = 0

        async def mock_request(method, path, **kwargs):
            nonlocal call_count
            call_count += 1
            return {"timestamp": 1700000000}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            await client._get_tick_timestamp(99)
            await client._get_tick_timestamp(99)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_new_tickdata_format(self):
        """Neues BOB-Format: {'tick': N, 'tickdata': {day, month, hour, minute, second}}."""
        async def mock_request(method, path, **kwargs):
            return {"tick": 12345, "tickdata": {"day": 24, "month": 4, "hour": 21, "minute": 18, "second": 13}}

        client = BOBClient("http://bob:40420")
        with patch.object(BOBClient, "_request", new=AsyncMock(side_effect=mock_request)):
            ts = await client._get_tick_timestamp(12345)

        assert ts != "0"
        assert int(ts) > 1_700_000_000_000  # Unix-ms im vernuenftigen Bereich
