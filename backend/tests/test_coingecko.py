"""
Unit tests for get_price_for_date() in app.services.coingecko.

Uses the `db` fixture from conftest.py (in-memory SQLite, rolled back after each test).
Async calls are run synchronously via asyncio.run(), matching the project pattern.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.coingecko import get_price_for_date
import app.services.coingecko as cg_mod


# ------------------------------------------------------------------ helpers --

def _seed_price_cache(db, date_str: str, eur: float, usd: float):
    from app.models.price_cache import PriceCache
    from app.utils.time import now_utc_iso
    entry = PriceCache(
        date=date_str,
        qubic_eur=eur,
        qubic_usd=usd,
        source="test",
        fetched_at=now_utc_iso(),
    )
    db.add(entry)
    db.flush()


def _make_mock_http_client(api_response: dict):
    """Build an async context manager mock that returns api_response from .get()."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=api_response)

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_resp)
    return mock_http


async def _noop():
    pass


# ------------------------------------------------------------------ cache hit --

class TestCacheHit:
    """Tests where a PriceCache row already exists for the requested date."""

    def test_returns_cached_eur_and_usd(self, db):
        _seed_price_cache(db, "2024-03-15", eur=0.00042, usd=0.00045)

        result = asyncio.run(get_price_for_date(db, "2024-03-15"))

        assert result == {"eur": pytest.approx(0.00042), "usd": pytest.approx(0.00045)}

    def test_cache_hit_does_not_call_api(self, db, monkeypatch):
        _seed_price_cache(db, "2024-04-01", eur=0.00042, usd=0.00045)

        call_count = {"n": 0}

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        async def _spy_get(*args, **kwargs):
            call_count["n"] += 1
            return MagicMock()

        mock_http.get = _spy_get

        with patch("app.services.coingecko.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http
            asyncio.run(get_price_for_date(db, "2024-04-01"))

        assert call_count["n"] == 0, "API should not have been called on a cache hit"


# ------------------------------------------------------------------ cache miss / API --

class TestCacheMiss:
    """Tests where no PriceCache row exists and the real API must be called (mocked)."""

    def test_api_called_on_miss_and_result_returned(self, db, monkeypatch):
        monkeypatch.setattr(cg_mod, "_rate_limit_wait", _noop)

        api_response = {
            "market_data": {
                "current_price": {"eur": 0.00055, "usd": 0.00060}
            }
        }
        mock_http = _make_mock_http_client(api_response)

        with patch("app.services.coingecko.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http
            result = asyncio.run(get_price_for_date(db, "2024-07-15"))

        assert result["eur"] == pytest.approx(0.00055)
        assert result["usd"] == pytest.approx(0.00060)

    def test_api_result_stored_in_cache(self, db, monkeypatch):
        monkeypatch.setattr(cg_mod, "_rate_limit_wait", _noop)

        api_response = {
            "market_data": {
                "current_price": {"eur": 0.00055, "usd": 0.00060}
            }
        }
        mock_http = _make_mock_http_client(api_response)

        with patch("app.services.coingecko.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http
            asyncio.run(get_price_for_date(db, "2024-08-20"))

        from app.models.price_cache import PriceCache
        cached = db.query(PriceCache).filter(PriceCache.date == "2024-08-20").first()
        assert cached is not None
        assert cached.qubic_eur == pytest.approx(0.00055)
        assert cached.qubic_usd == pytest.approx(0.00060)

    def test_network_failure_returns_none_prices(self, db, monkeypatch):
        monkeypatch.setattr(cg_mod, "_rate_limit_wait", _noop)

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(side_effect=Exception("timeout"))

        with patch("app.services.coingecko.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http
            result = asyncio.run(get_price_for_date(db, "2024-09-10"))

        assert result == {"eur": None, "usd": None}

    def test_network_failure_does_not_store_in_cache(self, db, monkeypatch):
        monkeypatch.setattr(cg_mod, "_rate_limit_wait", _noop)

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(side_effect=Exception("timeout"))

        with patch("app.services.coingecko.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http
            asyncio.run(get_price_for_date(db, "2024-10-05"))

        from app.models.price_cache import PriceCache
        cached = db.query(PriceCache).filter(PriceCache.date == "2024-10-05").first()
        assert cached is None, "No cache row should be stored after a network failure"
