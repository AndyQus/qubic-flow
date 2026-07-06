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

    # Assets issued directly by the QX smart contract (e.g. QX, QEARN, QVAULT,
    # QSWAP) represent shares in that contract/project. Assets issued by any
    # other identity (CFB, QFT, community project tokens, ...) are tokens.
    QX_ISSUER = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFXIB"

    async def get_owned_assets(self, wallet_id: str) -> list[dict]:
        """Fetch token/asset holdings for an identity.

        Returns a flat list of {name, issuer, units, managing_contract, kind}
        entries mapped from /v1/assets/{identity}/owned. `kind` is "share" for
        assets issued by the QX smart contract itself, "token" otherwise.
        """
        data = await self._request("GET", f"/v1/assets/{wallet_id}/owned")
        result = []
        for entry in data.get("ownedAssets", []):
            d = entry.get("data", {}) if isinstance(entry, dict) else {}
            issued = d.get("issuedAsset", {}) or {}
            try:
                units = int(d.get("numberOfUnits") or 0)
            except (TypeError, ValueError):
                units = 0
            if units <= 0:
                continue
            issuer = issued.get("issuerIdentity")
            result.append({
                "name": issued.get("name") or "?",
                "issuer": issuer,
                "units": units,
                "decimals": issued.get("numberOfDecimalPlaces", 0),
                "managing_contract": d.get("managingContractIndex"),
                "kind": "share" if issuer == self.QX_ISSUER else "token",
            })
        return result


_bob_rpc_id_counter = 0


def _next_bob_rpc_id() -> int:
    global _bob_rpc_id_counter
    _bob_rpc_id_counter += 1
    return _bob_rpc_id_counter


def _ts_to_ms(ts_raw) -> str:
    """Convert a raw BOB timestamp (Unix seconds or ms) to Unix-ms string."""
    try:
        ts = int(ts_raw)
        if 0 < ts < 1_000_000_000_000:
            ts *= 1000  # seconds → ms
        return str(ts) if ts else "0"
    except (TypeError, ValueError):
        return "0"


def _map_bob_transfer(t: dict) -> dict:
    """Map a BOB transfer entry to RPC-compatible eventLog format.

    Handles the confirmed qubic_getTransfers / qubic_getLogs response shapes:
      qubic_getTransfers: {body:{from,to,amount}, tick, epoch, txHash, timestamp, logId, type}
      qubic_getLogs:      {source, destination, amount, tick, epoch, transactionHash, logId, logType}
    """
    # qubic_getTransfers wraps addresses in body:{from, to, amount}
    body = t.get("body") or {}
    source = (
        body.get("from") or body.get("source") or
        t.get("source") or t.get("from") or ""
    )
    dest = (
        body.get("to") or body.get("destination") or
        t.get("destination") or t.get("to") or ""
    )
    amount_raw = body.get("amount") or t.get("amount") or 0
    try:
        amount = int(amount_raw)
    except (TypeError, ValueError):
        amount = 0

    log_id = (
        t.get("txHash") or t.get("transactionHash") or
        t.get("logDigest") or str(t.get("logId", ""))
    )
    tick = t.get("tick")
    epoch = t.get("epoch")
    log_type = t.get("type") or t.get("logType") or 0

    # Timestamp: present in qubic_getTransfers (Unix seconds), absent in qubic_getLogs
    ts_raw = t.get("timestamp")
    timestamp = _ts_to_ms(ts_raw) if ts_raw else "0"

    return {
        "logId": log_id,
        "epoch": epoch,
        "tickNumber": tick,
        "timestamp": timestamp,
        "logType": log_type,
        "logDigest": log_id,
        "categories": [],
        "quTransfer": {
            "source": source,
            "destination": dest,
            "amount": str(amount),
        },
    }


class BOBClient:
    """Client for Qubic BOB nodes using JSON-RPC 2.0 over POST /qubic.

    Implements the same interface as RPCClient so all sync paths work identically.
    Transfer retrieval uses qubic_getTransfers with object-in-array params:
      [{"address": identity, "startTick": N, "endTick": M}]
    Fallback: qubic_getLogs with same params format.
    Reference: https://github.com/qubic/Qubic.Net/tree/main/src/Qubic.Bob
    """

    def __init__(self, url: str):
        self.base_url = url.rstrip('/')
        self._cache: dict[tuple, list] = {}
        self._tick_ts_cache: dict[int, str] = {}

    async def _rpc(self, rpc_method: str, params=None) -> object:
        """Execute a JSON-RPC 2.0 call on POST /qubic and return result."""
        payload: dict = {"jsonrpc": "2.0", "id": _next_bob_rpc_id(), "method": rpc_method}
        if params is not None:
            payload["params"] = params
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    r = await client.post(f"{self.base_url}/qubic", json=payload, timeout=30)
                    r.raise_for_status()
                    data = r.json()
                    if data.get("error"):
                        raise RuntimeError(f"BOB RPC error [{rpc_method}]: {data['error']}")
                    return data.get("result")
            except RuntimeError:
                raise
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_exc = e
                wait = 2 ** attempt
                logger.warning(f"BOB RPC {rpc_method} attempt {attempt+1} failed: {e}, retry in {wait}s")
                await asyncio.sleep(wait)
        raise last_exc if last_exc else RuntimeError(f"BOB RPC {rpc_method} failed")

    async def _http_get(self, path: str) -> dict:
        """HTTP GET with retry, SSL disabled."""
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    r = await client.get(f"{self.base_url}{path}", timeout=15)
                    r.raise_for_status()
                    return r.json()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_exc = e
                await asyncio.sleep(2 ** attempt)
        raise last_exc if last_exc else RuntimeError(f"BOB GET {path} failed")

    # ------------------------------------------------------------------ tick

    async def get_tick_info(self) -> dict:
        """Return tick info in RPC-compatible format."""
        try:
            tick = await self._rpc("qubic_getTickNumber")
            return {"tickInfo": {"tick": int(tick or 0)}}
        except Exception as e:
            logger.warning(f"BOB {self.base_url} qubic_getTickNumber failed: {e} — trying /status")
        try:
            data = await self._http_get("/status")
            tick = (
                data.get("currentTick") or data.get("currentFetchingTick") or
                data.get("verifiedTick") or 0
            )
            return {"tickInfo": {"tick": int(tick)}}
        except Exception as e:
            raise RuntimeError(f"BOB {self.base_url}: cannot get tick: {e}")

    async def get_current_tick(self) -> int:
        info = await self.get_tick_info()
        return int(info.get("tickInfo", {}).get("tick", 0))

    # ------------------------------------------------------------------ balance

    async def get_balance(self, wallet_id: str) -> int | None:
        """Fetch QU balance — tries JSON-RPC then REST /balance/{id}."""
        try:
            result = await self._rpc("qubic_getBalance", [wallet_id])
            if result and isinstance(result, dict):
                raw = result.get("balance", 0)
                return int(raw) if raw is not None else None
        except Exception as e:
            logger.warning(f"BOB qubic_getBalance failed: {e} — trying REST")
        try:
            data = await self._http_get(f"/balance/{wallet_id}")
            return data.get("balance")
        except Exception:
            return None

    # ------------------------------------------------------------------ timestamp

    async def _get_tick_timestamp(self, tick: int) -> str:
        """Resolve Unix-ms timestamp for a tick number."""
        if tick in self._tick_ts_cache:
            return self._tick_ts_cache[tick]
        result = "0"
        try:
            data = await self._rpc("qubic_getTickByNumber", [tick])
            if isinstance(data, dict) and data.get("timestamp"):
                result = _ts_to_ms(data["timestamp"])
        except Exception:
            pass
        if result == "0":
            try:
                data = await self._http_get(f"/tick/{tick}")
                td = data.get("tickdata") if isinstance(data, dict) else None
                if td and td.get("month") and td.get("day"):
                    year = datetime.now(timezone.utc).year
                    dt = datetime(year, int(td["month"]), int(td["day"]),
                                  int(td.get("hour", 0)), int(td.get("minute", 0)),
                                  int(td.get("second", 0)), tzinfo=timezone.utc)
                    result = str(int(dt.timestamp() * 1000))
                elif isinstance(data, dict):
                    ts_raw = data.get("timestamp") or data.get("time") or 0
                    result = _ts_to_ms(ts_raw)
            except Exception as e:
                logger.debug(f"BOB tick {tick} timestamp fallback failed: {e}")
        self._tick_ts_cache[tick] = result
        return result

    # ------------------------------------------------------------------ transfers

    def _transfer_involves_wallet(self, t: dict, wallet_id: str) -> bool:
        """Return True if this transfer involves wallet_id as source or destination."""
        body = t.get("body") or {}
        source = body.get("from") or body.get("source") or t.get("source") or t.get("from") or ""
        dest = body.get("to") or body.get("destination") or t.get("destination") or t.get("to") or ""
        return source == wallet_id or dest == wallet_id

    async def _fetch_raw(self, wallet_id: str, from_tick: int, to_tick: int) -> tuple[list, int | None]:
        """Fetch raw transfers from BOB. Returns (transfers, actual_tick_served).

        BOB ignores startTick/endTick and always returns data for the current live tick.
        We return the actual tick BOB served so callers can report validForTick correctly.
        """
        try:
            result = await self._rpc(
                "qubic_getTransfers",
                [{"address": wallet_id, "startTick": from_tick, "endTick": to_tick}],
            )
            if isinstance(result, dict):
                transfers = [t for t in (result.get("transfers") or []) if isinstance(t, dict)]
                # BOB returns fromTick=toTick equal to the actual live tick served
                actual_tick = result.get("toTick") or result.get("fromTick")
                return transfers, actual_tick
            if isinstance(result, list):
                return [t for t in result if isinstance(t, dict)], None
        except Exception as e:
            logger.warning(f"BOB qubic_getTransfers failed: {e} — trying qubic_getLogs")
        try:
            result = await self._rpc(
                "qubic_getLogs",
                [{"address": wallet_id, "startTick": from_tick, "endTick": to_tick}],
            )
            logs = [t for t in (result if isinstance(result, list) else []) if isinstance(t, dict)]
            return logs, None
        except Exception as e:
            logger.warning(f"BOB qubic_getLogs also failed: {e}")
        return [], None

    async def _fetch_transfers(self, wallet_id: str, from_tick: int, to_tick: int) -> tuple[list, int]:
        """Fetch transfers involving wallet_id and return (matching_transfers, valid_for_tick).

        BOB serves only its current live tick — it cannot retrieve historical data.
        valid_for_tick is the actual tick BOB served data for (or to_tick if unknown).
        Callers should use valid_for_tick (not to_tick) to advance state.last_tick so
        gaps are recorded instead of silently skipped.
        """
        raw, actual_tick = await self._fetch_raw(wallet_id, from_tick, to_tick)
        matching = [t for t in raw if self._transfer_involves_wallet(t, wallet_id)]
        valid_for_tick = actual_tick if actual_tick is not None else to_tick
        logger.debug(
            f"BOB fetch {from_tick}-{to_tick}: actual_tick={actual_tick}, "
            f"total={len(raw)}, wallet={len(matching)}"
        )
        return matching, valid_for_tick

    # ------------------------------------------------------------------ event_logs (QubicEventSource protocol)

    async def get_event_logs(self, wallet_id: str, from_tick: int, to_tick: int, offset: int = 0, size: int = 1000) -> dict:
        key = (wallet_id, from_tick, to_tick)
        if key not in self._cache:
            raw, valid_for_tick = await self._fetch_transfers(wallet_id, from_tick, to_tick)

            # Resolve missing timestamps via qubic_getTickByNumber
            needs_ts = {t.get("tick") for t in raw if t.get("tick") and not t.get("timestamp")}
            tick_ts: dict[int, str] = {}
            for tick in needs_ts:
                tick_ts[tick] = await self._get_tick_timestamp(tick)

            mapped = []
            for t in raw:
                entry = _map_bob_transfer(t)
                if entry["timestamp"] == "0" and t.get("tick") in tick_ts:
                    entry["timestamp"] = tick_ts[t["tick"]]
                mapped.append(entry)

            self._cache[key] = (mapped, valid_for_tick)

        all_logs, valid_for_tick = self._cache[key]
        return {
            "hits": {"total": len(all_logs)},
            "validForTick": valid_for_tick,
            "eventLogs": all_logs[offset: offset + size],
        }

    async def get_transfer_transactions(self, wallet_id: str, from_tick: int, to_tick: int, page: int = 1, page_size: int = 100) -> dict:
        # Transfers are captured via get_event_logs for BOB nodes
        return {"transactions": [], "pagination": {"totalPages": 1}}

    async def supports_event_logs(self) -> bool:
        """Probe whether this BOB node supports transfer retrieval.

        Cached permanently on success, retried after _BOB_CAPABILITY_RETRY_HOURS on failure.
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
            tick = await self._rpc("qubic_getTickNumber")
            if tick:
                result = await self._rpc(
                    "qubic_getTransfers",
                    [{"address": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                      "startTick": int(tick) - 10, "endTick": int(tick)}],
                )
                # Any response (even empty transfers) means the endpoint works
                _bob_capability_cache[self.base_url] = (True, now)
                logger.info(f"BOB {self.base_url}: qubic_getTransfers available — using as event source")
                return True
        except Exception as e:
            logger.info(f"BOB {self.base_url}: transfer probe failed ({e}) — not using as event source")
            _bob_capability_cache[self.base_url] = (False, now)
            return False
        _bob_capability_cache[self.base_url] = (False, now)
        return False
