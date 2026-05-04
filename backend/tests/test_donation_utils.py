"""
Unit tests for donation_utils.py — pure parsing logic, no I/O.
"""
import pytest
from app.services.donation_utils import (
    parse_v2_transfers,
    DONATION_ADDRESS,
    DONATION_QU_PER_MONTH,
    DONATION_QU_FOREVER,
    TICKS_PER_DAY,
)


def _page(transactions: list) -> dict:
    return {"transactions": transactions}


def _tick_group(tick: int, txs: list) -> dict:
    return {"tickNumber": tick, "transactions": txs}


def _tx(source: str, dest: str, amount: int, money_flew: bool = True) -> dict:
    return {
        "moneyFlew": money_flew,
        "transaction": {
            "sourceId": source,
            "destId": dest,
            "amount": amount,
        },
    }


SENDER = "SENDERAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
RECVR  = "RECEIVERAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


class TestParseV2Transfers:
    def test_empty_pages_returns_empty(self):
        assert parse_v2_transfers([]) == []

    def test_empty_transactions_returns_empty(self):
        assert parse_v2_transfers([{"transactions": []}]) == []

    def test_single_valid_transfer(self):
        page = _page([_tick_group(1000, [_tx(SENDER, RECVR, 500)])])
        result = parse_v2_transfers([page])
        assert result == [(1000, SENDER, RECVR, 500)]

    def test_money_flew_false_skipped(self):
        page = _page([_tick_group(1000, [_tx(SENDER, RECVR, 500, money_flew=False)])])
        assert parse_v2_transfers([page]) == []

    def test_amount_zero_skipped(self):
        page = _page([_tick_group(1000, [_tx(SENDER, RECVR, 0)])])
        assert parse_v2_transfers([page]) == []

    def test_multiple_ticks_across_pages(self):
        page1 = _page([_tick_group(1000, [_tx(SENDER, RECVR, 100)])])
        page2 = _page([_tick_group(2000, [_tx(SENDER, RECVR, 200)])])
        result = parse_v2_transfers([page1, page2])
        assert (1000, SENDER, RECVR, 100) in result
        assert (2000, SENDER, RECVR, 200) in result
        assert len(result) == 2

    def test_multiple_txs_within_tick_group(self):
        txs = [_tx(SENDER, RECVR, 100), _tx(RECVR, SENDER, 50)]
        page = _page([_tick_group(3000, txs)])
        result = parse_v2_transfers([page])
        assert len(result) == 2

    def test_missing_tick_number_defaults_to_zero(self):
        tick_group = {"transactions": [_tx(SENDER, RECVR, 100)]}  # no tickNumber key
        page = {"transactions": [tick_group]}
        result = parse_v2_transfers([page])
        assert result == [(0, SENDER, RECVR, 100)]

    def test_none_transactions_key_skipped(self):
        page = {"transactions": None}
        assert parse_v2_transfers([page]) == []

    def test_alternative_source_dest_keys(self):
        """Handles 'source'/'destination' fallback keys instead of 'sourceId'/'destId'."""
        tx = {
            "moneyFlew": True,
            "transaction": {
                "source": SENDER,
                "destination": RECVR,
                "amount": 999,
            },
        }
        page = _page([_tick_group(5000, [tx])])
        result = parse_v2_transfers([page])
        assert result == [(5000, SENDER, RECVR, 999)]


class TestDonationConstants:
    def test_donation_qu_forever_gte_100_months(self):
        """Forever threshold must be at least 100 months of donations."""
        assert DONATION_QU_FOREVER >= DONATION_QU_PER_MONTH * 100

    def test_ticks_per_day_is_86400(self):
        assert TICKS_PER_DAY == 86_400

    def test_donation_address_is_non_empty(self):
        assert isinstance(DONATION_ADDRESS, str) and len(DONATION_ADDRESS) > 0
