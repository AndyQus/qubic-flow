"""
DB-backed tests for the tax-report fixes:

  1. Income (EVENT) lots get a market-value cost basis (no double taxation).
  2. Year-end holdings are not reduced by disposals in later years.
  3. Countries without tracked local rates (CH, GB, DK, …) report in EUR.
  4. Denmark: FIFO is forced and losses are reported separately
     (not netted against gains).
"""
from app.models.event import Event
from app.services.tax_engine import calculate_tax_report, calc_currency, TAX_RULES

W = "WALLET_A"


def _event(db, id_, ts, source, dest, amount, rate_eur, source_type="TX"):
    db.add(Event(
        id=id_,
        wallet_id=W,
        tick_number=1,
        timestamp=ts,
        source_address=source,
        destination_addr=dest,
        is_internal=0,
        amount_qubic=amount,
        qubic_eur_rate=rate_eur,
        qubic_usd_rate=rate_eur * 1.1,
        source_type=source_type,
        verified=0,
        created_at=ts,
    ))
    db.commit()


class TestIncomeCostBasis:
    def test_income_lot_uses_market_value_at_receipt(self, db):
        # 1000 QU reward at 0.5 EUR/QU → income 500 EUR
        _event(db, "e1", "2026-02-01T12:00:00Z", "SC_ADDR", W, 1000, 0.5, source_type="EVENT")
        # Disposal of the same 1000 QU at the same rate → gain must be ~0
        _event(db, "e2", "2026-06-01T12:00:00Z", W, "EXT_ADDR", 1000, 0.5, source_type="TX")

        report = calculate_tax_report(db, [W], 2026, "private", "DE", "FIFO")

        assert report["summary"]["income_eur"] == 500.0
        assert report["summary"]["taxable_gains_eur"] == 0.0
        assert report["disposals"][0]["cost_basis"] == 500.0


class TestYearEndHoldings:
    def test_later_year_disposals_do_not_reduce_holdings(self, db):
        _event(db, "e1", "2026-01-15T00:00:00Z", "EXT_ADDR", W, 1000, 0.1)
        # Disposal in the following year must not affect the 2026 report
        _event(db, "e2", "2027-01-05T00:00:00Z", W, "EXT_ADDR", 1000, 0.2)

        report = calculate_tax_report(db, [W], 2026, "private", "DE", "FIFO")

        assert report["disposals"] == []
        holdings = report["year_end_holdings"]
        assert len(holdings) == 1
        assert holdings[0]["amount_qubic"] == 1000


class TestReportCurrency:
    def test_calc_currency_falls_back_to_eur(self):
        assert calc_currency(TAX_RULES["CH"]) == "EUR"
        assert calc_currency(TAX_RULES["GB"]) == "EUR"
        assert calc_currency(TAX_RULES["DK"]) == "EUR"
        assert calc_currency(TAX_RULES["US"]) == "USD"
        assert calc_currency(TAX_RULES["DE"]) == "EUR"

    def test_report_exposes_calculation_currency(self, db):
        _event(db, "e1", "2026-01-15T00:00:00Z", "EXT_ADDR", W, 100, 0.1)
        report = calculate_tax_report(db, [W], 2026, "private", "CH", "FIFO")
        assert report["currency"] == "EUR"


class TestDenmark:
    def test_dk_profile_exists(self):
        dk = TAX_RULES["DK"]
        assert dk["forced_method"] == "FIFO"
        assert dk["separate_losses"] is True
        assert dk["holding_days"] is None

    def test_dk_forces_fifo(self, db):
        # Two lots: cheap first (0.1), expensive second (0.3).
        _event(db, "e1", "2026-01-01T00:00:00Z", "EXT_ADDR", W, 1000, 0.1)
        _event(db, "e2", "2026-02-01T00:00:00Z", "EXT_ADDR", W, 1000, 0.3)
        # Sell at 0.2 — FIFO must consume the 0.1 lot (gain), HIFO would pick 0.3.
        _event(db, "e3", "2026-03-01T00:00:00Z", W, "EXT_ADDR", 1000, 0.2)

        report = calculate_tax_report(db, [W], 2026, "private", "DK", "HIFO")

        assert report["method"] == "FIFO"
        assert report["disposals"][0]["cost_basis"] == 100.0  # 1000 × 0.1

    def test_dk_separates_gains_and_losses(self, db):
        _event(db, "e1", "2026-01-01T00:00:00Z", "EXT_ADDR", W, 1000, 0.1)
        _event(db, "e2", "2026-02-01T00:00:00Z", "EXT_ADDR", W, 1000, 0.3)
        # First sell consumes the 0.1 lot → +100 gain
        _event(db, "e3", "2026-03-01T00:00:00Z", W, "EXT_ADDR", 1000, 0.2)
        # Second sell consumes the 0.3 lot → −100 loss
        _event(db, "e4", "2026-04-01T00:00:00Z", W, "EXT_ADDR", 1000, 0.2)

        report = calculate_tax_report(db, [W], 2026, "private", "DK", "FIFO")
        s = report["summary"]
        assert s["taxable_gains_eur"] == 100.0
        assert s["deductible_losses_eur"] == 100.0

    def test_other_countries_net_losses(self, db):
        _event(db, "e1", "2026-01-01T00:00:00Z", "EXT_ADDR", W, 1000, 0.1)
        _event(db, "e2", "2026-02-01T00:00:00Z", "EXT_ADDR", W, 1000, 0.3)
        _event(db, "e3", "2026-03-01T00:00:00Z", W, "EXT_ADDR", 1000, 0.2)
        _event(db, "e4", "2026-04-01T00:00:00Z", W, "EXT_ADDR", 1000, 0.2)

        report = calculate_tax_report(db, [W], 2026, "private", "DE", "FIFO")
        s = report["summary"]
        assert s["taxable_gains_eur"] == 0.0  # +100 and −100 netted
        assert s["deductible_losses_eur"] is None
