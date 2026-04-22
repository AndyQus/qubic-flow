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


def _map_bob_transfer(t: dict) -> dict:
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
        "timestamp": "0",
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

    async def _request(self, method: str, path: str, **kwargs) -> dict:
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

    async def get_current_tick(self) -> int:
        info = await self.get_tick_info()
        return int(info.get("tickInfo", {}).get("tick", 0))

    async def get_event_logs(self, wallet_id: str, from_tick: int, to_tick: int, offset: int = 0, size: int = 1000) -> dict:
        key = (wallet_id, from_tick, to_tick)
        if key not in self._cache:
            payload = {"fromTick": from_tick, "toTick": to_tick, "identity": wallet_id}
            data = await self._request("POST", "/getQuTransferForIdentity", json=payload)
            raw = data.get("transfers") or []
            self._cache[key] = [_map_bob_transfer(t) for t in raw]
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
