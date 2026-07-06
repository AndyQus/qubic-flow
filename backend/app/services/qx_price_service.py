import logging
import time

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# Prices come from the official Qubic QX API (qubic/qx-service) — the same
# backend QXBoard uses. The last executed trade defines the current price
# in QU per share/token.
_PRICE_CACHE_TTL = 600  # seconds
_price_cache: dict[tuple[str, str], tuple[float | None, float]] = {}


def _extract_last_price(trades: list) -> float | None:
    """Return the price (QU per share) of the most recent trade."""
    for t in trades:
        if isinstance(t, dict) and t.get("price") is not None:
            try:
                return float(t["price"])
            except (TypeError, ValueError):
                continue
    return None


async def get_last_trade_price(issuer: str, asset_name: str) -> float | None:
    """Latest QX trade price for an asset in QU per share, cached for 10 minutes.

    Returns None if the asset has no trades or the API is unreachable —
    callers must handle missing prices gracefully.
    """
    key = (issuer, asset_name)
    now = time.monotonic()
    cached = _price_cache.get(key)
    if cached is not None and now - cached[1] < _PRICE_CACHE_TTL:
        return cached[0]

    price = None
    try:
        url = f"{settings.qx_api_url}/v1/qx/issuer/{issuer}/asset/{asset_name}/trades"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            if r.status_code == 200:
                price = _extract_last_price(r.json())
    except Exception as e:
        logger.warning(f"QX price lookup failed for {asset_name}: {e}")

    _price_cache[key] = (price, now)
    return price
