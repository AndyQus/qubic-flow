"""
Unit tests for pure functions in app.services.tax_engine.

_match_lots() and _parse_date() are pure (no DB required for most tests).
TAX_RULES is tested for structural completeness.
"""
import pytest
from collections import deque
from datetime import datetime

from app.services.tax_engine import _match_lots, _parse_date, TAX_RULES


# ------------------------------------------------------------------ helpers --

D1 = datetime(2024, 1, 1)
D2 = datetime(2024, 6, 1)
D3 = datetime(2024, 11, 1)
SELL_DATE = datetime(2025, 2, 1)


def _lot(amount: int, price_eur: float, price_usd: float, date: datetime) -> dict:
    return {
        "amount": amount,
        "price_eur": price_eur,
        "price_usd": price_usd,
        "date": date,
    }


# ------------------------------------------------------------------ _parse_date --

class TestParseDate:
    """Tests for _parse_date()."""

    def test_iso_datetime_with_z_suffix_returns_naive(self):
        result = _parse_date("2024-03-15T10:30:00Z")
        assert result == datetime(2024, 3, 15, 10, 30, 0)
        assert result.tzinfo is None

    def test_iso_date_only_parses_correctly(self):
        result = _parse_date("2024-07-20")
        assert result == datetime(2024, 7, 20)

    def test_empty_string_returns_epoch(self):
        result = _parse_date("")
        assert result == datetime(1970, 1, 1)

    def test_invalid_string_returns_epoch(self):
        result = _parse_date("not-a-date")
        assert result == datetime(1970, 1, 1)

    def test_datetime_with_timezone_offset_strips_tzinfo(self):
        result = _parse_date("2024-05-01T08:00:00+02:00")
        assert result.tzinfo is None
        assert result == datetime(2024, 5, 1, 8, 0, 0)


# ------------------------------------------------------------------ FIFO --

class TestMatchLotsFIFO:
    """Tests for _match_lots() with method='FIFO'."""

    def test_fifo_consumes_oldest_lot_first(self):
        q = deque([
            _lot(100, 0.10, 0.11, D1),
            _lot(100, 0.20, 0.22, D2),
        ])
        disposals, total_cost = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=SELL_DATE,
            method="FIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        # The oldest lot (D1, 0.10) should be consumed first
        assert len(disposals) == 1
        assert disposals[0]["cost_basis"] == pytest.approx(100 * 0.10)
        # Only the 0.20 lot should remain in the queue
        assert len(q) == 1
        assert q[0]["price_eur"] == pytest.approx(0.20)

    def test_fifo_spans_multiple_lots(self):
        q = deque([
            _lot(50, 0.10, 0.11, D1),
            _lot(100, 0.20, 0.22, D2),
        ])
        disposals, total_cost = _match_lots(
            q=q,
            amount=120,
            disposal_value_per_qu=0.30,
            ts=SELL_DATE,
            method="FIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        # Two sub-disposals: 50 from D1, 70 from D2
        assert len(disposals) == 2
        assert disposals[0]["amount_qubic"] == 50
        assert disposals[1]["amount_qubic"] == 70
        # 30 should remain in the queue
        assert len(q) == 1
        assert q[0]["amount"] == 30

    def test_fifo_partial_lot_consumption(self):
        q = deque([_lot(500, 0.15, 0.16, D1)])
        disposals, total_cost = _match_lots(
            q=q,
            amount=200,
            disposal_value_per_qu=0.25,
            ts=SELL_DATE,
            method="FIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        assert len(disposals) == 1
        assert disposals[0]["amount_qubic"] == 200
        # 300 should remain
        assert len(q) == 1
        assert q[0]["amount"] == 300

    def test_fifo_empty_queue_produces_zero_cost_remainder(self):
        q = deque()
        disposals, total_cost = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=SELL_DATE,
            method="FIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        assert len(disposals) == 1
        assert disposals[0]["cost_basis"] == 0.0
        assert disposals[0]["acquired_date"] is None


# ------------------------------------------------------------------ LIFO --

class TestMatchLotsLIFO:
    """Tests for _match_lots() with method='LIFO'."""

    def test_lifo_consumes_newest_lot_first(self):
        q = deque([
            _lot(100, 0.10, 0.11, D1),
            _lot(100, 0.20, 0.22, D2),
        ])
        disposals, total_cost = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=SELL_DATE,
            method="LIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        # The newest lot (D2, 0.20) should be consumed first
        assert len(disposals) == 1
        assert disposals[0]["cost_basis"] == pytest.approx(100 * 0.20)
        # D1 lot should remain
        assert len(q) == 1
        assert q[0]["price_eur"] == pytest.approx(0.10)

    def test_lifo_three_lots_consumes_newest_first(self):
        q = deque([
            _lot(100, 0.10, 0.11, D1),
            _lot(100, 0.20, 0.22, D2),
            _lot(100, 0.30, 0.33, D3),
        ])
        disposals, total_cost = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.40,
            ts=SELL_DATE,
            method="LIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        # D3 (0.30) should be consumed first
        assert len(disposals) == 1
        assert disposals[0]["cost_basis"] == pytest.approx(100 * 0.30)
        assert len(q) == 2


# ------------------------------------------------------------------ HIFO --

class TestMatchLotsHIFO:
    """Tests for _match_lots() with method='HIFO'."""

    def test_hifo_consumes_highest_cost_lot_first(self):
        q = deque([
            _lot(100, 0.10, 0.11, D1),
            _lot(100, 0.50, 0.55, D2),
            _lot(100, 0.20, 0.22, D3),
        ])
        disposals, total_cost = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.60,
            ts=SELL_DATE,
            method="HIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        # The highest cost lot (0.50) should be consumed
        assert len(disposals) == 1
        assert disposals[0]["cost_basis"] == pytest.approx(100 * 0.50)
        assert len(q) == 2

    def test_hifo_minimises_taxable_gain(self):
        lots_for_hifo = deque([
            _lot(100, 0.10, 0.11, D1),
            _lot(100, 0.50, 0.55, D2),
            _lot(100, 0.20, 0.22, D3),
        ])
        lots_for_fifo = deque([
            _lot(100, 0.10, 0.11, D1),
            _lot(100, 0.50, 0.55, D2),
            _lot(100, 0.20, 0.22, D3),
        ])
        sell_value = 0.60

        hifo_disposals, hifo_cost = _match_lots(
            q=lots_for_hifo,
            amount=100,
            disposal_value_per_qu=sell_value,
            ts=SELL_DATE,
            method="HIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        fifo_disposals, fifo_cost = _match_lots(
            q=lots_for_fifo,
            amount=100,
            disposal_value_per_qu=sell_value,
            ts=SELL_DATE,
            method="FIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        hifo_gain = hifo_disposals[0]["gain"]
        fifo_gain = fifo_disposals[0]["gain"]
        assert hifo_gain < fifo_gain


# ------------------------------------------------------------------ AVCO --

class TestMatchLotsAVCO:
    """Tests for _match_lots() with method='AVCO'."""

    def test_avco_uses_weighted_average_cost(self):
        q = deque([
            _lot(100, 0.10, 0.11, D1),
            _lot(100, 0.30, 0.33, D2),
        ])
        disposals, total_cost = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.40,
            ts=SELL_DATE,
            method="AVCO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        # avg cost = (100*0.10 + 100*0.30) / 200 = 0.20
        expected_cost = 100 * 0.20
        assert len(disposals) == 1
        assert disposals[0]["cost_basis"] == pytest.approx(expected_cost)

    def test_avco_consumes_lots_proportionally(self):
        q = deque([
            _lot(100, 0.10, 0.11, D1),
            _lot(100, 0.30, 0.33, D2),
        ])
        disposals, total_cost = _match_lots(
            q=q,
            amount=50,
            disposal_value_per_qu=0.40,
            ts=SELL_DATE,
            method="AVCO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        # 50 consumed from 200 total → 150 remaining
        total_remaining = sum(lot["amount"] for lot in q)
        assert total_remaining == 150

    def test_avco_empty_queue_zero_cost(self):
        q = deque()
        disposals, total_cost = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=SELL_DATE,
            method="AVCO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        assert total_cost == 0.0
        assert disposals[0]["cost_basis"] == 0.0

    def test_avco_usd_currency(self):
        q = deque([
            _lot(100, 0.10, 0.20, D1),
            _lot(100, 0.30, 0.60, D2),
        ])
        disposals, total_cost = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.80,
            ts=SELL_DATE,
            method="AVCO",
            holding_days_threshold=365,
            mode="private",
            currency="USD",
        )
        # avg usd cost = (100*0.20 + 100*0.60) / 200 = 0.40
        expected_cost = 100 * 0.40
        assert disposals[0]["cost_basis"] == pytest.approx(expected_cost)

    def test_avco_holding_days_is_none(self):
        q = deque([_lot(100, 0.10, 0.11, D1)])
        disposals, _ = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=SELL_DATE,
            method="AVCO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        assert disposals[0]["holding_days"] is None


# ------------------------------------------------------------------ Holding days / tax-free --

class TestHoldingDays:
    """Tests for the holding_days and tax_free logic inside _match_lots."""

    def test_tax_free_when_held_longer_than_threshold(self):
        buy_date = datetime(2023, 1, 1)
        sell_date = datetime(2024, 1, 10)  # 375 days
        q = deque([_lot(100, 0.10, 0.11, buy_date)])
        disposals, _ = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=sell_date,
            method="FIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        assert disposals[0]["holding_days"] == 374
        assert disposals[0]["tax_free"] is True

    def test_taxable_when_held_less_than_threshold(self):
        buy_date = datetime(2024, 1, 1)
        sell_date = datetime(2024, 6, 1)  # 152 days
        q = deque([_lot(100, 0.10, 0.11, buy_date)])
        disposals, _ = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=sell_date,
            method="FIFO",
            holding_days_threshold=365,
            mode="private",
            currency="EUR",
        )
        assert disposals[0]["holding_days"] == 152
        assert disposals[0]["tax_free"] is False

    def test_business_mode_never_tax_free(self):
        buy_date = datetime(2021, 1, 1)
        sell_date = datetime(2024, 1, 1)  # ~3 years
        q = deque([_lot(100, 0.10, 0.11, buy_date)])
        disposals, _ = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=sell_date,
            method="FIFO",
            holding_days_threshold=365,
            mode="business",
            currency="EUR",
        )
        assert disposals[0]["tax_free"] is False

    def test_no_threshold_country_never_tax_free(self):
        buy_date = datetime(2021, 1, 1)
        sell_date = datetime(2024, 1, 1)
        q = deque([_lot(100, 0.10, 0.11, buy_date)])
        disposals, _ = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=sell_date,
            method="FIFO",
            holding_days_threshold=None,
            mode="private",
            currency="EUR",
        )
        assert disposals[0]["tax_free"] is False

    def test_exact_threshold_boundary(self):
        buy_date = datetime(2024, 1, 1)
        sell_date = datetime(2025, 1, 1)  # exactly 366 days (2024 is a leap year)
        days_held = (sell_date - buy_date).days
        q = deque([_lot(100, 0.10, 0.11, buy_date)])
        disposals, _ = _match_lots(
            q=q,
            amount=100,
            disposal_value_per_qu=0.30,
            ts=sell_date,
            method="FIFO",
            holding_days_threshold=days_held,
            mode="private",
            currency="EUR",
        )
        # >= threshold → tax_free
        assert disposals[0]["holding_days"] == days_held
        assert disposals[0]["tax_free"] is True


# ------------------------------------------------------------------ TAX_RULES --

class TestTaxRules:
    """Tests for the TAX_RULES constant."""

    def test_germany_rules(self):
        de = TAX_RULES["DE"]
        assert de["holding_days"] == 365
        assert de["threshold"] == 1000
        assert de["currency"] == "EUR"

    def test_switzerland_no_tax(self):
        ch = TAX_RULES["CH"]
        assert ch["holding_days"] is None
        assert ch["threshold"] is None

    def test_us_rules(self):
        us = TAX_RULES["US"]
        assert us["holding_days"] == 365
        assert us["currency"] == "USD"

    def test_all_countries_have_required_keys(self):
        required_keys = {"currency", "holding_days", "threshold"}
        for country, rules in TAX_RULES.items():
            missing = required_keys - rules.keys()
            assert not missing, (
                f"Country '{country}' is missing required keys: {missing}"
            )
