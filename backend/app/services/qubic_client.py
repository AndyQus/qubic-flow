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
    def __init__(self):
        self.base_url = settings.qubic_rpc_url

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

    async def get_transfer_transactions(self, wallet_id: str, from_tick: int, to_tick: int, page: int = 1, page_size: int = 100) -> dict:
        params = {
            "start_tick": from_tick,
            "end_tick": to_tick,
            "page": page,
            "page_size": page_size,
        }
        return await self._request("GET", f"/v2/identities/{wallet_id}/transfer-transactions", params=params)
