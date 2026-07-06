"""
Tests for the QX price service (last trade price per asset, cached).
"""
import pytest

from app.services import qx_price_service as qps


class TestExtractLastPrice:
    def test_first_trade_wins(self):
        trades = [
            {"tickTime": "2026-07-04T10:00:00Z", "price": 5, "numberOfShares": 10},
            {"tickTime": "2026-07-03T10:00:00Z", "price": 3, "numberOfShares": 20},
        ]
        assert qps._extract_last_price(trades) == 5.0

    def test_skips_entries_without_price(self):
        trades = [{"tickTime": "2026-07-04T10:00:00Z"}, {"price": 2}]
        assert qps._extract_last_price(trades) == 2.0

    def test_empty_list_returns_none(self):
        assert qps._extract_last_price([]) is None


class TestCache:
    @pytest.mark.asyncio
    async def test_price_is_cached(self, monkeypatch):
        qps._price_cache.clear()
        calls = []

        class FakeResponse:
            status_code = 200
            def json(self):
                return [{"price": 7}]

        class FakeClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url, timeout=None):
                calls.append(url)
                return FakeResponse()

        monkeypatch.setattr(qps.httpx, "AsyncClient", FakeClient)

        p1 = await qps.get_last_trade_price("ISSUER", "QX")
        p2 = await qps.get_last_trade_price("ISSUER", "QX")
        assert p1 == 7.0
        assert p2 == 7.0
        assert len(calls) == 1  # second call served from cache

    @pytest.mark.asyncio
    async def test_api_failure_returns_none(self, monkeypatch):
        qps._price_cache.clear()

        class FakeClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url, timeout=None):
                raise RuntimeError("connection refused")

        monkeypatch.setattr(qps.httpx, "AsyncClient", FakeClient)
        assert await qps.get_last_trade_price("ISSUER", "DOWN") is None
