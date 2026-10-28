"""Outbound throttle for public Qubic APIs (rpc.qubic.org, public BOB nodes).

Public endpoints sit behind Cloudflare, which limits per public IP — shared by
every device and app in the user's network (Home Node, browser wallet,
explorer). A block returns 429 without CORS headers, so qubic.org web apps in
the same network break too. Therefore:

- one token bucket per public host: small burst, steady rate well below the
  public limit (budget configurable, see settings.public_rpc_rate_limit_per_min);
- one shared cooldown per host: the first 429 pauses *all* requests to that
  host instead of every request retrying on its own;
- LAN / private hosts (Home Node, own BOB node) are not throttled.
"""
import asyncio
import ipaddress
import logging
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from ..config import settings

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_S = 60.0
MAX_COOLDOWN_S = 300.0


class _HostBucket:
    def __init__(self, rate_per_min: int, burst: int):
        self.rate = max(1, rate_per_min) / 60.0        # tokens per second
        self.burst = max(1, burst)
        self.tokens = float(self.burst)
        self.updated = time.monotonic()
        self.cooldown_until = 0.0
        self.lock = asyncio.Lock()
        self.sent: list[float] = []                     # timestamps, last 60 s (status only)

    def _refill(self, now: float):
        self.tokens = min(self.burst, self.tokens + (now - self.updated) * self.rate)
        self.updated = now


_buckets: dict[str, _HostBucket] = {}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_public_host(host: str) -> bool:
    if not host or host == "localhost" or "." not in host:
        return False  # docker service names, localhost
    if host.endswith((".local", ".lan", ".home", ".internal", ".onion")):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return True


def verify_tls(url: str) -> bool:
    """Check TLS certificates for public hosts; LAN nodes often use self-signed certs."""
    return is_public_host(_host(url))


def _bucket(host: str) -> _HostBucket:
    b = _buckets.get(host)
    if b is None:
        b = _buckets[host] = _HostBucket(settings.public_rpc_rate_limit_per_min, settings.public_rpc_burst)
    return b


async def acquire(url: str) -> None:
    """Wait until a request to `url` may be sent (no-op for private hosts)."""
    host = _host(url)
    if not is_public_host(host):
        return
    b = _bucket(host)
    async with b.lock:
        while True:
            now = time.monotonic()
            if b.cooldown_until > now:
                await asyncio.sleep(b.cooldown_until - now)
                continue
            b._refill(now)
            if b.tokens >= 1:
                b.tokens -= 1
                b.sent = [t for t in b.sent if now - t < 60] + [now]
                return
            await asyncio.sleep((1 - b.tokens) / b.rate)


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    try:
        from datetime import datetime, timezone
        return (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
    except (TypeError, ValueError):
        return None


def report(url: str, status_code: int, headers=None) -> None:
    """Feed a response back: 429 (or 503 with Retry-After) pauses the whole host."""
    retry_after = _retry_after_seconds((headers or {}).get("retry-after"))
    if status_code != 429 and not (status_code == 503 and retry_after):
        return
    host = _host(url)
    if not is_public_host(host):
        return
    b = _bucket(host)
    delay = min(MAX_COOLDOWN_S, max(1.0, retry_after or DEFAULT_COOLDOWN_S))
    now = time.monotonic()
    if b.cooldown_until <= now:
        logger.warning(f"{host} throttles us (HTTP {status_code}) — pausing all requests to it for {delay:.0f}s")
    b.cooldown_until = max(b.cooldown_until, now + delay)
    b.tokens = 0


def report_response(url: str, response) -> None:
    """report() for an httpx response (tolerates minimal fakes in tests)."""
    report(url, getattr(response, "status_code", 0), getattr(response, "headers", None))


def cooling_down(url: str) -> bool:
    b = _buckets.get(_host(url))
    return bool(b and b.cooldown_until > time.monotonic())


def status() -> dict:
    now = time.monotonic()
    return {
        "budget_per_min": settings.public_rpc_rate_limit_per_min,
        "burst": settings.public_rpc_burst,
        "hosts": {
            h: {
                "requests_last_min": len([t for t in b.sent if now - t < 60]),
                "cooldown_remaining_s": round(max(0.0, b.cooldown_until - now)),
            }
            for h, b in _buckets.items()
        },
    }


def reset_for_tests() -> None:
    _buckets.clear()
