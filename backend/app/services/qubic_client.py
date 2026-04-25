from typing import Protocol, runtime_checkable
import asyncio
import logging
from datetime import datetime, timezone
import httpx
from ..config import settings

logger = logging.getLogger(__name__)

_RPC_RATE_LIMIT = 100
_rpc_lock = asyncio.Lock()
_rpc_request_times: list[float] = []

# Capability cache: url → (supported, checked_at)
# False entries are retried once per day; True entries are permanent until a 404 is received.
_BOB_CAPABILITY_RETRY_HOURS = 24
_bob_capability_cache: dict[str, tuple[bool, datetime]] = {}


async def _rpc_rate_limit():
    async with _rpc_lock:
        now = datetime.now(timezone.utc).timestamp()
        global _rpc_request_times
        _rpc_request_times = [t for t in _rpc_request_times if now - t < 60]
        if len(_rpc_request_times) >= _RPC_RATE_LIMIT:
            wait = 60 - (now - _rpc_request_times[0])
            logger.info(f"RPC rate limit reached, waiting {wait:.1f}s")
            await asyncio.sleep(wait)
        _rpc_request_times.append(datetime.now(timezone.utc).timestamp())


@runtime_checkable
class QubicEventSource(Protocol):
    async def get_event_logs(self, wallet_id: str, from_tick: int, to_tick: int, offset: int, size: int) -> dict: ...
    async def get_tick_info(self) -> dict: ...


class RPCClient:
    def __init__(self, url: str | None = None):
        self.base_url = (url or settings.qubic_rpc_url).rstrip('/')

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        await _rpc_rate_limit()
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.request(method, f"{self.base_url}{path}", timeout=30, **kwargs)
                    r.raise_for_status()
                    return r.json()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_exc = e
                wait = 2 ** attempt
                logger.warning(f"RPC {path} attempt {attempt+1} failed: {e}, retry in {wait}s")
                await asyncio.sleep(wait)
        raise last_exc if last_exc else RuntimeError("RPC request failed")

    async def get_tick_info(self) -> dict:
        return await self._request("GET", "/v1/tick-info")

    async def get_current_tick(self) -> int:
        info = await self.get_tick_info()
        return int(info.get("tickInfo", {}).get("tick", 0))

    async def get_event_logs(self, wallet_id: str, from_tick: int, to_tick: int, offset: int = 0, size: int = 1000) -> dict:
        payload = {
            "should": [{"terms": {"source": wallet_id, "destination": wallet_id}}],
            "ranges": {"tickNumber": {"gte": str(from_tick), "lte": str(to_tick)}},
            "pagination": {"offset": offset, "size": size},
        }
        return await self._request("POST", "/query/v1/getEventLogs", json=payload)

    async def get_balance(self, wallet_id: str) -> int | None:
        try:
            data = await self._request("GET", f"/v1/balances/{wallet_id}")
            return data.get("balance", {}).get("balance")
        except Exception:
            return None

    async def get_transfer_transactions(self, wallet_id: str, from_tick: int, to_tick: int, page: int = 1, page_size: int = 100) -> dict:
        params = {
            "start_tick": from_tick,
            "end_tick": to_tick,
            "page": page,
            "page_size": page_size,
        }
        return await self._request("GET", f"/v2/identities/{wallet_id}/transfers", params=params)


def _map_bob_transfer(t: dict, timestamp: str = "0") -> dict:
    """Map a BOB LogEvent to RPC-compatible eventLog format."""
    msg = t.get("message") or {}
    # QU_TRANSFER message fields — try multiple naming conventions
    source = (
        msg.get("sourceId") or msg.get("source_id") or
        msg.get("source") or msg.get("from") or ""
    )
    dest = (
        msg.get("destId") or msg.get("dest_id") or
        msg.get("destination") or msg.get("to") or ""
    )
    amount = msg.get("amount", 0)
    log_id = str(t.get("logId", ""))
    return {
        "logId": log_id,
        "epoch": t.get("epoch"),
        "tickNumber": t.get("tick"),
        "timestamp": timestamp,
        "logType": t.get("logType", 0),
        "logDigest": log_id,
        "categories": [],
        "quTransfer": {
            "source": source,
            "destination": dest,
            "amount": str(amount),
        },
    }


class BOBClient:
    def __init__(self, url: str):
        self.base_url = url.rstrip('/')
        # Cache transfers per (wallet_id, from_tick, to_tick) within one sync cycle
        self._cache: dict[tuple, list] = {}
        # Cache tick timestamps to avoid duplicate lookups across wallets
        self._tick_ts_cache: dict[int, str] = {}

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    r = await client.request(method, f"{self.base_url}{path}", timeout=30, **kwargs)
                    r.raise_for_status()
                    return r.json()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_exc = e
                wait = 2 ** attempt
                logger.warning(f"BOB {path} attempt {attempt+1} failed: {e}, retry in {wait}s")
                await asyncio.sleep(wait)
        raise last_exc if last_exc else RuntimeError("BOB request failed")

    async def get_tick_info(self) -> dict:
        data = await self._request("GET", "/status")
        tick = (
            data.get("currentTick") or
            data.get("currentFetchingTick") or
            data.get("verifiedTick") or 0
        )
        return {"tickInfo": {"tick": int(tick)}}

    async def _get_tick_timestamp(self, tick: int) -> str:
        """Fetch the Unix-ms timestamp for a tick via GET /tick/{tick}."""
        if tick in self._tick_ts_cache:
            return self._tick_ts_cache[tick]
        try:
            data = await self._request("GET", f"/tick/{tick}")
            # New BOB format: {"tick": N, "tickdata": {day, month, hour, minute, second, ...}}
            td = data.get("tickdata") if isinstance(data, dict) else None
            if td and isinstance(td, dict) and td.get("month") and td.get("day"):
                from datetime import datetime, timezone
                year = datetime.now(timezone.utc).year
                try:
                    dt = datetime(year, int(td["month"]), int(td["day"]),
                                  int(td.get("hour", 0)), int(td.get("minute", 0)),
                                  int(td.get("second", 0)), tzinfo=timezone.utc)
                    result = str(int(dt.timestamp() * 1000))
                except (ValueError, TypeError):
                    result = "0"
            else:
                # Legacy flat response shapes
                ts_raw = (
                    data.get("timestamp") or
                    data.get("tick", {}).get("timestamp") or
                    data.get("time") or
                    data.get("tickTimestamp") or
                    0
                ) if isinstance(data, dict) else 0
                ts = int(ts_raw)
                if 0 < ts < 1_000_000_000_000:
                    ts *= 1000
                result = str(ts) if ts else "0"
        except Exception as e:
            logger.debug(f"BOB tick {tick} timestamp lookup failed: {e}")
            result = "0"
        self._tick_ts_cache[tick] = result
        return result

    async def get_current_tick(self) -> int:
        info = await self.get_tick_info()
        return int(info.get("tickInfo", {}).get("tick", 0))

    _BOB_CHUNK = 999  # BOB API: toTick - fromTick must be < 1000

    async def _fetch_transfers_chunked(self, wallet_id: str, from_tick: int, to_tick: int) -> list:
        """Fetch all transfers, splitting the range into BOB-compatible chunks."""
        raw: list = []
        chunk_start = from_tick
        while chunk_start <= to_tick:
            chunk_end = min(chunk_start + self._BOB_CHUNK - 1, to_tick)
            payload = {"fromTick": chunk_start, "toTick": chunk_end, "identity": wallet_id}
            data = await self._request("POST", "/getQuTransfersForIdentity", json=payload)
            raw.extend(data.get("transfers") or [])
            chunk_start = chunk_end + 1
        return raw

    async def get_event_logs(self, wallet_id: str, from_tick: int, to_tick: int, offset: int = 0, size: int = 1000) -> dict:
        key = (wallet_id, from_tick, to_tick)
        if key not in self._cache:
            raw = await self._fetch_transfers_chunked(wallet_id, from_tick, to_tick)

            # Fetch timestamps for all unique ticks (BOB transfers have no timestamp field)
            unique_ticks = {t.get("tick") for t in raw if t.get("tick")}
            tick_ts: dict[int, str] = {}
            for tick in unique_ticks:
                tick_ts[tick] = await self._get_tick_timestamp(tick)

            mapped = []
            for t in raw:
                tick = t.get("tick")
                ts = tick_ts.get(tick, "0") if tick else "0"
                mapped.append(_map_bob_transfer(t, timestamp=ts))

            self._cache[key] = mapped
            logger.debug(f"BOB: fetched {len(self._cache[key])} transfers for {wallet_id} ticks {from_tick}-{to_tick}")

        all_logs = self._cache[key]
        return {
            "hits": {"total": len(all_logs)},
            "validForTick": to_tick,
            "eventLogs": all_logs[offset: offset + size],
        }

    async def get_transfer_transactions(self, wallet_id: str, from_tick: int, to_tick: int, page: int = 1, page_size: int = 100) -> dict:
        # Transfers are already captured via get_event_logs for BOB nodes
        return {"transactions": [], "pagination": {"totalPages": 1}}

    async def supports_event_logs(self) -> bool:
        """Return True if this BOB node has the getEventLogs endpoint.

        Result is cached permanently on success, and retried once per day on failure.
        Transient errors (timeout, 5xx) are not cached so the next sync cycle retries.
        """
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        cached = _bob_capability_cache.get(self.base_url)
        if cached is not None:
            supported, checked_at = cached
            if supported:
                return True
            if now - checked_at < timedelta(hours=_BOB_CAPABILITY_RETRY_HOURS):
                return False

        try:
            async with httpx.AsyncClient(verify=False) as client:
                r = await client.post(
                    f"{self.base_url}/query/v1/getEventLogs",
                    json={"should": [], "ranges": {}, "pagination": {"offset": 0, "size": 1}},
                    timeout=10,
                )
            if r.status_code == 404:
                _bob_capability_cache[self.base_url] = (False, now)
                logger.info(f"BOB {self.base_url}: getEventLogs not available (404) — retry in {_BOB_CAPABILITY_RETRY_HOURS}h")
                return False
            _bob_capability_cache[self.base_url] = (True, now)
            logger.info(f"BOB {self.base_url}: getEventLogs available — switching event source")
            return True
        except Exception as e:
            logger.debug(f"BOB {self.base_url}: getEventLogs probe failed ({e}) — using RPC this cycle")
            return False
