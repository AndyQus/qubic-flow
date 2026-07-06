import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.address_label import AddressLabel
from ..models.wallet import Wallet
from .coingecko import get_price_for_date
from .qx_price_service import get_last_trade_price

logger = logging.getLogger(__name__)

# Owned-asset lookups hit the RPC node once per wallet, so cache them for a
# few minutes — the portfolio page would otherwise fire N RPC calls on every
# view switch.
_OWNED_CACHE_TTL = 300  # seconds
_owned_cache: dict[str, tuple[list, float]] = {}


async def _get_owned_assets_cached(client, wallet_id: str) -> list:
    now = time.monotonic()
    cached = _owned_cache.get(wallet_id)
    if cached is not None and now - cached[1] < _OWNED_CACHE_TTL:
        return cached[0]
    try:
        assets = await client.get_owned_assets(wallet_id)
    except Exception as e:
        logger.warning(f"Owned-asset lookup failed for {wallet_id}: {e}")
        # Keep serving stale data if we have any; otherwise report no assets.
        return cached[0] if cached is not None else []
    _owned_cache[wallet_id] = (assets, now)
    return assets


async def enrich_assets(db: Session, assets: list, qu_rate: dict) -> list:
    """Add issuer labels, current QX price and QU/fiat values to raw assets."""
    issuers = [a["issuer"] for a in assets if a.get("issuer")]
    labels = {}
    if issuers:
        labels = {
            row.address: row.label
            for row in db.query(AddressLabel).filter(AddressLabel.address.in_(issuers)).all()
        }
    for a in assets:
        a["issuer_label"] = labels.get(a.get("issuer"))
        price_qu = None
        if a.get("issuer") and a.get("name"):
            price_qu = await get_last_trade_price(a["issuer"], a["name"])
        a["price_qu"] = price_qu
        if price_qu is not None:
            value_qu = a["units"] * price_qu
            a["value_qubic"] = value_qu
            # No rounding here — QU micro-rates make small fiat values vanish
            # at 2 decimals; the frontend formats for display.
            a["value_eur"] = value_qu * qu_rate["eur"] if qu_rate.get("eur") else None
            a["value_usd"] = value_qu * qu_rate["usd"] if qu_rate.get("usd") else None
        else:
            a["value_qubic"] = None
            a["value_eur"] = None
            a["value_usd"] = None
    return assets


async def get_today_qu_rate(db: Session) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    return await get_price_for_date(db, today)


async def build_assets_summary(db: Session, client) -> dict:
    """Token/share holdings for all active wallets, with prices and totals.

    Wallets are fetched concurrently (bounded) against the RPC node; results
    are cached for a few minutes per wallet. A wallet whose lookup fails is
    reported with an empty asset list instead of failing the whole response.
    """
    wallets = db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()
    qu_rate = await get_today_qu_rate(db)

    sem = asyncio.Semaphore(5)

    async def fetch(w):
        async with sem:
            return w.id, await _get_owned_assets_cached(client, w.id)

    results = await asyncio.gather(*(fetch(w) for w in wallets))

    out: dict[str, dict] = {}
    for wallet_id, assets in results:
        assets = await enrich_assets(db, assets, qu_rate)
        total_qu = sum(a["value_qubic"] for a in assets if a["value_qubic"] is not None)
        total_eur = sum(a["value_eur"] for a in assets if a["value_eur"] is not None)
        total_usd = sum(a["value_usd"] for a in assets if a["value_usd"] is not None)
        out[wallet_id] = {
            "assets": assets,
            "total_value_qubic": total_qu if assets else 0,
            "total_value_eur": total_eur if assets else 0,
            "total_value_usd": total_usd if assets else 0,
        }

    return {"wallets": out, "qu_rate": qu_rate}
