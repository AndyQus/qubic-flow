import asyncio
import logging
import httpx
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..config import settings
from ..models.price_cache import PriceCache
from ..utils.time import now_utc_iso

logger = logging.getLogger(__name__)

_RATE_LIMIT_PER_MIN = 25
_lock = asyncio.Lock()
_request_times: list[float] = []


async def _rate_limit_wait():
    async with _lock:
        now = datetime.now(timezone.utc).timestamp()
        global _request_times
        _request_times = [t for t in _request_times if now - t < 60]
        if len(_request_times) >= _RATE_LIMIT_PER_MIN:
            wait = 60 - (now - _request_times[0])
            logger.info(f"CoinGecko rate limit reached, waiting {wait:.1f}s")
            await asyncio.sleep(wait)
        _request_times.append(datetime.now(timezone.utc).timestamp())


_live_price_cache: dict = {"at": 0.0, "eur": None, "usd": None}
_LIVE_PRICE_TTL_SECONDS = 300


async def get_live_price() -> dict:
    """Returns the current QUBIC price {'eur': float|None, 'usd': float|None}.

    Cached in-memory for a few minutes so hourly snapshot runs across many
    wallets cost a single CoinGecko call.
    """
    now = datetime.now(timezone.utc).timestamp()
    if _live_price_cache["eur"] is not None and now - _live_price_cache["at"] < _LIVE_PRICE_TTL_SECONDS:
        return {"eur": _live_price_cache["eur"], "usd": _live_price_cache["usd"]}

    try:
        await _rate_limit_wait()
        headers = {}
        if settings.coingecko_api_key:
            headers["x-cg-demo-api-key"] = settings.coingecko_api_key
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.coingecko_api_url}/simple/price",
                params={"ids": "qubic-network", "vs_currencies": "eur,usd"},
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            data = r.json().get("qubic-network", {})
            eur = data.get("eur")
            usd = data.get("usd")
            if eur is not None and usd is not None:
                _live_price_cache.update({"at": now, "eur": eur, "usd": usd})
            return {"eur": eur, "usd": usd}
    except Exception as e:
        logger.warning(f"CoinGecko live price fetch failed: {e}")
        return {"eur": None, "usd": None}


async def get_price_for_date(db: Session, date_str: str) -> dict:
    """Returns {'eur': float|None, 'usd': float|None}. Reads cache first."""
    cached = db.query(PriceCache).filter(PriceCache.date == date_str).first()
    if cached:
        return {"eur": cached.qubic_eur, "usd": cached.qubic_usd}

    try:
        await _rate_limit_wait()
        yyyy, mm, dd = date_str.split("-")
        headers = {}
        if settings.coingecko_api_key:
            headers["x-cg-demo-api-key"] = settings.coingecko_api_key
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.coingecko_api_url}/coins/qubic-network/history",
                params={"date": f"{dd}-{mm}-{yyyy}", "localization": "false"},
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            prices = data.get("market_data", {}).get("current_price", {})
            eur = prices.get("eur")
            usd = prices.get("usd")
    except Exception as e:
        logger.warning(f"CoinGecko fetch failed for {date_str}: {e}")
        return {"eur": None, "usd": None}

    # Only cache complete pairs — persisting a missing rate as 0.0 would
    # permanently poison cost-basis calculations for that date. Partial
    # responses are retried by the backfill_missing_rates job.
    if eur is not None and usd is not None:
        entry = PriceCache(
            date=date_str,
            qubic_eur=eur,
            qubic_usd=usd,
            source="coingecko",
            fetched_at=now_utc_iso(),
        )
        db.merge(entry)
        db.commit()

    return {"eur": eur, "usd": usd}
