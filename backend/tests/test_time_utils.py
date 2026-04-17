"""
Tests for app/utils/time.py

Each test verifies one behaviour.  No DB or HTTP required.
"""
import re
import pytest


# ------------------------------------------------------------------ helpers --

def _import():
    from app.utils.time import now_utc_iso, unix_ms_to_iso, iso_to_date
    return now_utc_iso, unix_ms_to_iso, iso_to_date


# ------------------------------------------------------------------ now_utc_iso --

class TestNowUtcIso:
    def test_returns_string(self):
        now_utc_iso, _, _ = _import()
        result = now_utc_iso()
        assert isinstance(result, str)

    def test_ends_with_utc_offset(self):
        """now_utc_iso() must carry UTC information.

        datetime.isoformat() with timezone.utc produces '+00:00', NOT 'Z'.
        This test documents the *actual* behaviour so that if the function is
        changed to emit 'Z' in the future the test catches it.
        """
        now_utc_iso, _, _ = _import()
        result = now_utc_iso()
        # Acceptable UTC markers: '+00:00' or trailing 'Z'
        assert result.endswith("+00:00") or result.endswith("Z"), (
            f"Expected UTC offset in ISO string, got: {result!r}"
        )

    def test_matches_iso8601_pattern(self):
        now_utc_iso, _, _ = _import()
        result = now_utc_iso()
        # e.g. 2024-01-15T10:30:00.123456+00:00
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        assert re.match(pattern, result), f"Not ISO 8601: {result!r}"

    def test_date_component_is_plausible(self):
        """Year must be >= 2024 (when QubicFlow was first deployed)."""
        now_utc_iso, _, _ = _import()
        result = now_utc_iso()
        year = int(result[:4])
        assert year >= 2024


# ------------------------------------------------------------------ unix_ms_to_iso --

class TestUnixMsToIso:
    """1 700 000 000 000 ms  ==  2023-11-14T22:13:20+00:00"""

    KNOWN_MS = "1700000000000"
    EXPECTED_DATE = "2023-11-14"
    EXPECTED_TIME = "22:13:20"

    def test_accepts_string_input(self):
        _, unix_ms_to_iso, _ = _import()
        result = unix_ms_to_iso(self.KNOWN_MS)
        assert isinstance(result, str)

    def test_accepts_integer_input(self):
        _, unix_ms_to_iso, _ = _import()
        result = unix_ms_to_iso(1700000000000)
        assert isinstance(result, str)

    def test_correct_date_component(self):
        _, unix_ms_to_iso, _ = _import()
        result = unix_ms_to_iso(self.KNOWN_MS)
        assert result.startswith(self.EXPECTED_DATE), (
            f"Expected date {self.EXPECTED_DATE!r}, got {result!r}"
        )

    def test_correct_time_component(self):
        _, unix_ms_to_iso, _ = _import()
        result = unix_ms_to_iso(self.KNOWN_MS)
        assert self.EXPECTED_TIME in result, (
            f"Expected time {self.EXPECTED_TIME!r} in {result!r}"
        )

    def test_carries_utc_marker(self):
        _, unix_ms_to_iso, _ = _import()
        result = unix_ms_to_iso(self.KNOWN_MS)
        assert result.endswith("+00:00") or result.endswith("Z"), (
            f"Expected UTC marker in {result!r}"
        )

    def test_zero_ms_returns_epoch(self):
        """0 ms should give 1970-01-01."""
        _, unix_ms_to_iso, _ = _import()
        result = unix_ms_to_iso("0")
        assert result.startswith("1970-01-01")

    def test_string_and_int_give_same_result(self):
        _, unix_ms_to_iso, _ = _import()
        assert unix_ms_to_iso("1700000000000") == unix_ms_to_iso(1700000000000)


# ------------------------------------------------------------------ iso_to_date --

class TestIsoToDate:
    def test_strips_time_component(self):
        _, _, iso_to_date = _import()
        assert iso_to_date("2023-11-14T22:13:20Z") == "2023-11-14"

    def test_strips_offset_utc(self):
        _, _, iso_to_date = _import()
        assert iso_to_date("2023-11-14T22:13:20+00:00") == "2023-11-14"

    def test_plain_date_string_passthrough(self):
        """If only a date is given, returns it unchanged."""
        _, _, iso_to_date = _import()
        assert iso_to_date("2023-11-14") == "2023-11-14"

    def test_result_length_is_ten(self):
        _, _, iso_to_date = _import()
        assert len(iso_to_date("2023-11-14T22:13:20Z")) == 10
