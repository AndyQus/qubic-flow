"""
Unit tests for the hourly rate capture and the hourly rate lookup
in app.services.coingecko.
"""
import asyncio
import pytest

import app.services.coingecko as cg_mod
from app.models.price_hourly import PriceHourly
from app.services.coingecko import capture_hourly_price, get_current_hourly_price, get_hourly_price
from app.utils.time import now_utc_iso


def _seed_hour(db, hour: str, eur: float, usd: float):
    db.add(PriceHourly(hour=hour, qubic_eur=eur, qubic_usd=usd, source="test", fetched_at=now_utc_iso()))
    db.flush()


NONE = {"eur": None, "usd": None}


class TestGetHourlyPrice:
    def test_uses_rate_of_same_hour(self, db):
        _seed_hour(db, "2026-10-07T13", 0.1, 0.2)
        _seed_hour(db, "2026-10-07T14", 0.3, 0.4)

        assert asyncio.run(get_hourly_price(db, "2026-10-07T14:59:59Z")) == {"eur": 0.3, "usd": 0.4}

    def test_missing_hour_keeps_last_known_rate(self, db):
        _seed_hour(db, "2026-10-07T10", 0.1, 0.2)

        assert asyncio.run(get_hourly_price(db, "2026-10-07T15:20:00Z")) == {"eur": 0.1, "usd": 0.2}

    def test_ignores_later_hours(self, db):
        _seed_hour(db, "2026-10-07T16", 0.5, 0.6)

        assert asyncio.run(get_hourly_price(db, "2026-10-07T15:20:00Z")) == NONE

    def test_no_rate_when_last_capture_too_old(self, db):
        _seed_hour(db, "2026-10-05T12", 0.1, 0.2)

        assert asyncio.run(get_hourly_price(db, "2026-10-07T15:00:00Z")) == NONE

    def test_accepts_offset_timestamps(self, db):
        _seed_hour(db, "2026-10-07T14", 0.3, 0.4)

        assert asyncio.run(get_hourly_price(db, "2026-10-07T14:10:00+00:00")) == {"eur": 0.3, "usd": 0.4}

    def test_invalid_timestamp_returns_none(self, db):
        assert asyncio.run(get_hourly_price(db, None)) == NONE


class TestCaptureHourlyPrice:
    def test_stores_complete_pair(self, db, monkeypatch):
        async def _live():
            return {"eur": 0.7, "usd": 0.8}

        monkeypatch.setattr(cg_mod, "get_live_price", _live)

        assert asyncio.run(capture_hourly_price(db)) is True
        rows = db.query(PriceHourly).all()
        assert len(rows) == 1
        assert (rows[0].qubic_eur, rows[0].qubic_usd) == (0.7, 0.8)
        assert len(rows[0].hour) == 13

    def test_failed_fetch_writes_nothing(self, db, monkeypatch):
        async def _live():
            return {"eur": None, "usd": None}

        monkeypatch.setattr(cg_mod, "get_live_price", _live)

        assert asyncio.run(capture_hourly_price(db)) is False
        assert db.query(PriceHourly).count() == 0


class TestGetCurrentHourlyPrice:
    def test_returns_latest_captured_hour(self, db):
        _seed_hour(db, "2026-10-07T13", 0.1, 0.2)
        _seed_hour(db, "2026-10-07T14", 0.3, 0.4)

        result = asyncio.run(get_current_hourly_price(db))

        assert (result["eur"], result["usd"]) == (0.3, 0.4)
        assert result["fetched_at"]

    def test_falls_back_to_live_price_without_captures(self, db, monkeypatch):
        async def _live():
            return {"eur": 0.7, "usd": 0.8}

        monkeypatch.setattr(cg_mod, "get_live_price", _live)

        assert asyncio.run(get_current_hourly_price(db)) == {"eur": 0.7, "usd": 0.8, "fetched_at": None}
