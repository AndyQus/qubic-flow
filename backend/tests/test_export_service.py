"""
Tests for app/services/export_service.py

Uses a real SQLite in-memory DB (via the `db` fixture) so SQL queries,
joins and filters are exercised without mocking.
"""
import csv
import io
import pytest
from app.models.wallet import Wallet
from app.models.event import Event
from app.utils.time import now_utc_iso


# ------------------------------------------------------------------ fixtures --

PRIVATE_WALLET_ID = "ADDR_PRIVATE_WALLET_01"
BUSINESS_WALLET_ID = "ADDR_BUSINESS_WALLET_01"
OTHER_ADDR = "ADDR_EXTERNAL_COUNTERPARTY"


def _make_wallet(wallet_id: str, label: str, wallet_type: str) -> Wallet:
    now = now_utc_iso()
    return Wallet(
        id=wallet_id,
        label=label,
        note=None,
        wallet_type=wallet_type,
        active=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


def _make_event(
    event_id: str,
    wallet_id: str,
    source: str,
    dest: str,
    amount: int = 1000,
    rate: float = 0.00015,
    is_internal: int = 0,
    timestamp: str = "2023-11-14T22:13:20+00:00",
) -> Event:
    return Event(
        id=event_id,
        epoch=100,
        tick_number=12345,
        timestamp_raw="1700000000000",
        timestamp=timestamp,
        log_type=1,
        source_address=source,
        destination_addr=dest,
        wallet_id=wallet_id,
        is_internal=is_internal,
        amount_qubic=amount,
        qubic_eur_rate=rate,
        qubic_usd_rate=rate * 1.1,
        source_type="EVENT",
        verified=0,
        created_at=now_utc_iso(),
    )


@pytest.fixture()
def seeded_db(db):
    """
    DB with:
      - one PRIVATE wallet (for CoinTracking tests)
      - one BUSINESS wallet (for Steuerberater tests)
      - one external address (not a wallet)

    Events:
      EV1 – PRIVATE wallet receives from external  -> QUBIC_IN, not internal
      EV2 – PRIVATE wallet sends to external       -> QUBIC_OUT, not internal
      EV3 – PRIVATE wallet internal transfer       -> is_internal=1, EXCLUDED from CT export
      EV4 – BUSINESS wallet receives from external -> included in ST export
    """
    priv = _make_wallet(PRIVATE_WALLET_ID, "My Private Wallet", "PRIVATE")
    biz = _make_wallet(BUSINESS_WALLET_ID, "My Business Wallet", "BUSINESS")
    db.add_all([priv, biz])
    db.flush()

    ev1 = _make_event("EV1", PRIVATE_WALLET_ID, OTHER_ADDR, PRIVATE_WALLET_ID, amount=500)
    ev2 = _make_event("EV2", PRIVATE_WALLET_ID, PRIVATE_WALLET_ID, OTHER_ADDR, amount=200)
    ev3 = _make_event(
        "EV3", PRIVATE_WALLET_ID,
        PRIVATE_WALLET_ID, BUSINESS_WALLET_ID,  # both owned → internal
        amount=100, is_internal=1,
    )
    ev4 = _make_event("EV4", BUSINESS_WALLET_ID, OTHER_ADDR, BUSINESS_WALLET_ID, amount=999)

    db.add_all([ev1, ev2, ev3, ev4])
    db.commit()
    yield db


# ------------------------------------------------------------------ CoinTracking --

class TestExportCointracking:
    def test_returns_string(self, seeded_db):
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db)
        assert isinstance(result, str)

    def test_uses_comma_delimiter(self, seeded_db):
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db)
        # Header row must be comma-separated
        first_line = result.splitlines()[0]
        assert "," in first_line
        assert ";" not in first_line

    def test_header_contains_required_columns(self, seeded_db):
        from app.services.export_service import export_cointracking, COINTRACKING_HEADER
        result = export_cointracking(seeded_db)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        for col in ("Type", "Buy Amount", "Buy Currency", "Sell Amount", "Sell Currency"):
            assert col in header, f"Missing column: {col!r}"

    def test_header_matches_defined_constant(self, seeded_db):
        from app.services.export_service import export_cointracking, COINTRACKING_HEADER
        result = export_cointracking(seeded_db)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert header == COINTRACKING_HEADER

    def test_deposit_row_present(self, seeded_db):
        """EV1 (external → private) must appear as Deposit."""
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db)
        rows = list(csv.reader(io.StringIO(result)))
        types = [r[0] for r in rows[1:]]
        assert "Deposit" in types

    def test_withdrawal_row_present(self, seeded_db):
        """EV2 (private → external) must appear as Withdrawal."""
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db)
        rows = list(csv.reader(io.StringIO(result)))
        types = [r[0] for r in rows[1:]]
        assert "Withdrawal" in types

    def test_internal_transfer_excluded(self, seeded_db):
        """EV3 (is_internal=1) must NOT appear in CoinTracking export."""
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db)
        assert "EV3" not in result, (
            "Internal transfer event EV3 should be excluded from CoinTracking output"
        )

    def test_business_wallet_events_excluded(self, seeded_db):
        """CoinTracking only covers PRIVATE wallets; EV4 (BUSINESS) must be absent."""
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db)
        assert "EV4" not in result

    def test_year_filter_excludes_other_years(self, seeded_db):
        """Filtering by 2022 should return header only (no data rows)."""
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db, year=2022)
        rows = list(csv.reader(io.StringIO(result)))
        # Only the header row should be present
        assert len(rows) == 1

    def test_year_filter_includes_matching_year(self, seeded_db):
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db, year=2023)
        rows = list(csv.reader(io.StringIO(result)))
        # Header + at least EV1 and EV2
        assert len(rows) >= 3

    def test_deposit_buy_amount_is_populated(self, seeded_db):
        """For a Deposit row the Buy Amount column (index 1) should be non-empty."""
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db)
        rows = list(csv.reader(io.StringIO(result)))
        deposit_rows = [r for r in rows[1:] if r[0] == "Deposit"]
        assert deposit_rows, "No Deposit rows found"
        assert deposit_rows[0][1] != "", "Buy Amount should not be empty for Deposit"

    def test_withdrawal_sell_amount_is_populated(self, seeded_db):
        """For a Withdrawal row the Sell Amount column (index 3) should be non-empty."""
        from app.services.export_service import export_cointracking
        result = export_cointracking(seeded_db)
        rows = list(csv.reader(io.StringIO(result)))
        withdrawal_rows = [r for r in rows[1:] if r[0] == "Withdrawal"]
        assert withdrawal_rows, "No Withdrawal rows found"
        assert withdrawal_rows[0][3] != "", "Sell Amount should not be empty for Withdrawal"


# ------------------------------------------------------------------ Steuerberater --

class TestExportSteuerberater:
    def test_returns_string(self, seeded_db):
        from app.services.export_service import export_steuerberater
        result = export_steuerberater(seeded_db)
        assert isinstance(result, str)

    def test_uses_semicolon_delimiter(self, seeded_db):
        from app.services.export_service import export_steuerberater
        result = export_steuerberater(seeded_db)
        first_line = result.splitlines()[0]
        assert ";" in first_line

    def test_header_contains_required_columns(self, seeded_db):
        from app.services.export_service import export_steuerberater, STEUERBERATER_HEADER
        result = export_steuerberater(seeded_db)
        reader = csv.reader(io.StringIO(result), delimiter=";")
        header = next(reader)
        for col in ("Datum", "Typ", "Betrag QUBIC", "Kurs EUR", "Wert EUR"):
            assert col in header, f"Missing column: {col!r}"

    def test_header_matches_defined_constant(self, seeded_db):
        from app.services.export_service import export_steuerberater, STEUERBERATER_HEADER
        result = export_steuerberater(seeded_db)
        reader = csv.reader(io.StringIO(result), delimiter=";")
        header = next(reader)
        assert header == STEUERBERATER_HEADER

    def test_business_wallet_event_present(self, seeded_db):
        """EV4 belongs to a BUSINESS wallet and must appear in Steuerberater export."""
        from app.services.export_service import export_steuerberater
        result = export_steuerberater(seeded_db)
        assert "EV4" in result

    def test_private_wallet_events_excluded(self, seeded_db):
        """Steuerberater only covers BUSINESS wallets; EV1/EV2 must be absent."""
        from app.services.export_service import export_steuerberater
        result = export_steuerberater(seeded_db)
        assert "EV1" not in result
        assert "EV2" not in result

    def test_internal_transfer_included_in_steuerberater(self, seeded_db):
        """
        Steuerberater does NOT filter out is_internal events — accountants need
        the full picture.  EV3 is on a PRIVATE wallet so it is absent for a
        different reason (wallet_type filter), but the function itself does not
        apply an is_internal filter.
        """
        from app.services.export_service import export_steuerberater
        # Add an internal event on the BUSINESS wallet to verify it IS included
        internal_biz = _make_event(
            "EV_INTERNAL_BIZ",
            BUSINESS_WALLET_ID,
            BUSINESS_WALLET_ID, PRIVATE_WALLET_ID,
            amount=50, is_internal=1,
        )
        seeded_db.add(internal_biz)
        seeded_db.flush()
        result = export_steuerberater(seeded_db)
        assert "EV_INTERNAL_BIZ" in result, (
            "Steuerberater export should include internal transfers (no is_internal filter)"
        )

    def test_year_filter_excludes_other_years(self, seeded_db):
        from app.services.export_service import export_steuerberater
        result = export_steuerberater(seeded_db, year=2022)
        rows = list(csv.reader(io.StringIO(result), delimiter=";"))
        assert len(rows) == 1  # header only

    def test_wallet_label_appears_in_row(self, seeded_db):
        """The wallet label ('My Business Wallet') should appear in data rows."""
        from app.services.export_service import export_steuerberater
        result = export_steuerberater(seeded_db)
        assert "My Business Wallet" in result


# ------------------------------------------------------------------ _classify --

class TestClassifyHelper:
    """Unit tests for the internal _classify function."""

    def _evt(self, source, dest, is_internal=0):
        """Return a minimal object that _classify can inspect."""
        from types import SimpleNamespace
        return SimpleNamespace(
            source_address=source,
            destination_addr=dest,
            is_internal=is_internal,
        )

    def test_internal_flag_gives_internal_type(self):
        from app.services.export_service import _classify
        owned = {"ADDR_A", "ADDR_B"}
        e = self._evt("ADDR_A", "ADDR_B", is_internal=1)
        assert _classify(e, owned) == "INTERNAL"

    def test_destination_in_owned_gives_qubic_in(self):
        from app.services.export_service import _classify
        owned = {"ADDR_A"}
        e = self._evt("EXTERNAL", "ADDR_A")
        assert _classify(e, owned) == "QUBIC_IN"

    def test_source_in_owned_gives_qubic_out(self):
        from app.services.export_service import _classify
        owned = {"ADDR_A"}
        e = self._evt("ADDR_A", "EXTERNAL")
        assert _classify(e, owned) == "QUBIC_OUT"

    def test_neither_in_owned_gives_unknown(self):
        from app.services.export_service import _classify
        owned = {"ADDR_A"}
        e = self._evt("EXTERNAL_1", "EXTERNAL_2")
        assert _classify(e, owned) == "UNKNOWN"
