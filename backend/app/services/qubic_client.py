from typing import Protocol, runtime_checkable
import logging
import httpx
from ..config import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class QubicEventSource(Protocol):
    async def get_event_logs(self, wallet_id: str, from_tick: int, to_tick: int, offset: int, size: int) -> dict: ...
    async def get_tick_info(self) -> dict: ...


class RPCClient:
    def __init__(self):
        self.base_url = settings.qubic_rpc_url

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
                logger.warning(f"RPC {path} attempt {attempt+1} failed: {e}, retry in {wait}s")
                import asyncio
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
