"""Tests for duplicate-event detection and automatic cleanup.

The critical property under test is asymmetric:
  - a leftover stub next to a reconciled row MUST be removed
  - two *genuinely distinct* transfers with the same tick/amount/addresses
    MUST both survive (a wallet can legitimately send the same amount to the
    same address twice within one tick)
"""
import pytest

from app.models.wallet import Wallet
from app.models.event import Event
from app.services.dedup_service import (
    dedup_events, find_duplicate_groups, is_real_txid,
)
from app.utils.time import now_utc_iso


WALLET = "ADDR_WALLET_A_000000000000000000000000000000000000000001"
SENDER = "ADDR_SENDER_00000000000000000000000000000000000000000002"

# 60 chars, lowercase alpha - the real Qubic TxID shape
TXID_1 = "bzymx" + "a" * 55
TXID_2 = "ekxph" + "b" * 55


def _seed_wallet(db, balance=None, since_tick=None):
    now = now_utc_iso()
    db.add(Wallet(
        id=WALLET, label="W", wallet_type="PRIVATE", active=1,
        balance=balance, balance_since_tick=since_tick,
        created_at=now, updated_at=now,
    ))
    db.flush()


def _add_event(db, ev_id, tick=75606, amount=10_000_000, **kw):
    defaults = dict(
        id=ev_id, wallet_id=WALLET, epoch=227, tick_number=tick,
        timestamp="2026-08-21T15:24:31Z", log_type=0,
        log_digest=ev_id if is_real_txid(ev_id) else "d",
        source_address=SENDER, destination_addr=WALLET,
        is_internal=0, amount_qubic=amount, source_type="TX",
        verified=0, created_at=now_utc_iso(),
    )
    defaults.update(kw)
    ev = Event(**defaults)
    db.add(ev)
    db.flush()
    return ev


class TestDuplicateDetection:

    def test_stub_left_next_to_reconciled_row_is_removed(self, db):
        """The exact bug: TX sync upgraded one stub, the twin stub stayed."""
        _seed_wallet(db)
        _add_event(db, TXID_1)      # reconciled row
        _add_event(db, "12345")     # leftover stub of the same transfer

        result = dedup_events(db)

        assert result["removed"] == 1
        remaining = db.query(Event).all()
        assert len(remaining) == 1
        # the explorer-verifiable row is the one that survives
        assert remaining[0].id == TXID_1

    def test_two_distinct_txids_both_survive(self, db):
        """Two real transfers in one tick must NOT be collapsed."""
        _seed_wallet(db)
        _add_event(db, TXID_1)
        _add_event(db, TXID_2)

        result = dedup_events(db)

        assert result["removed"] == 0
        assert db.query(Event).count() == 2

    def test_two_real_transfers_with_one_surplus_stub(self, db):
        """2 genuine transfers + 1 orphan stub -> keep 2, drop 1."""
        _seed_wallet(db)
        _add_event(db, TXID_1)
        _add_event(db, TXID_2)
        _add_event(db, "99999")

        result = dedup_events(db)

        assert result["removed"] == 1
        ids = {e.id for e in db.query(Event).all()}
        assert ids == {TXID_1, TXID_2}

    def test_clean_database_is_untouched(self, db):
        _seed_wallet(db)
        _add_event(db, TXID_1, tick=100)
        _add_event(db, TXID_2, tick=200)

        assert find_duplicate_groups(db) == []
        assert dedup_events(db)["removed"] == 0
        assert db.query(Event).count() == 2

    def test_different_amount_is_not_a_duplicate(self, db):
        _seed_wallet(db)
        _add_event(db, "1", amount=10_000_000)
        _add_event(db, "2", amount=40_000_000)

        assert dedup_events(db)["removed"] == 0
        assert db.query(Event).count() == 2

    def test_two_bare_stubs_collapse_to_one(self, db):
        """No TxID anywhere -> the stubs describe one transfer."""
        _seed_wallet(db)
        _add_event(db, "111")
        _add_event(db, "222")

        assert dedup_events(db)["removed"] == 1
        assert db.query(Event).count() == 1


class TestUserDataPreservation:

    def test_note_from_removed_row_is_kept(self, db):
        _seed_wallet(db)
        _add_event(db, TXID_1)
        _add_event(db, "12345", note="wichtige Notiz", verified=1)

        dedup_events(db)

        survivor = db.query(Event).one()
        assert survivor.id == TXID_1
        assert survivor.note == "wichtige Notiz"
        assert survivor.verified == 1

    def test_survivor_note_wins_over_loser_note(self, db):
        _seed_wallet(db)
        _add_event(db, TXID_1, note="behalten")
        _add_event(db, "12345", note="verworfen")

        dedup_events(db)

        assert db.query(Event).one().note == "behalten"

    def test_epoch_backfilled_from_removed_row(self, db):
        _seed_wallet(db)
        _add_event(db, TXID_1, epoch=None)
        _add_event(db, "12345", epoch=227)

        dedup_events(db)

        assert db.query(Event).one().epoch == 227


class TestBalanceCorrection:

    def test_incoming_duplicate_reduces_inflated_balance(self, db):
        """The phantom row had inflated the balance; removing it corrects it."""
        _seed_wallet(db, balance=1_990_902_657, since_tick=1000)
        _add_event(db, TXID_1, tick=75606)
        _add_event(db, "12345", tick=75606)

        dedup_events(db)

        wallet = db.query(Wallet).one()
        assert wallet.balance == 1_990_902_657 - 10_000_000

    def test_duplicate_below_baseline_tick_does_not_touch_balance(self, db):
        """Only events after the baseline were ever applied to the balance."""
        _seed_wallet(db, balance=5_000, since_tick=99_999)
        _add_event(db, TXID_1, tick=500)
        _add_event(db, "12345", tick=500)

        dedup_events(db)

        assert db.query(Wallet).one().balance == 5_000

    def test_untracked_balance_is_left_alone(self, db):
        _seed_wallet(db, balance=None, since_tick=None)
        _add_event(db, TXID_1)
        _add_event(db, "12345")

        dedup_events(db)

        assert db.query(Wallet).one().balance is None


class TestDryRun:

    def test_dry_run_reports_but_changes_nothing(self, db):
        _seed_wallet(db, balance=1_000_000, since_tick=1)
        _add_event(db, TXID_1)
        _add_event(db, "12345")

        result = dedup_events(db, dry_run=True)

        assert result["removed"] == 1
        assert result["dry_run"] is True
        assert db.query(Event).count() == 2
        assert db.query(Wallet).one().balance == 1_000_000


class TestTxidRecognition:

    @pytest.mark.parametrize("value,expected", [
        (TXID_1, True),
        ("12345", False),
        ("a" * 59, False),
        ("a" * 61, False),
        ("A" * 60, False),      # uppercase is the address format, not a TxID
        ("a" * 59 + "1", False),  # digits are not part of the TxID alphabet
        (None, False),
        (12345, False),
    ])
    def test_is_real_txid(self, value, expected):
        assert is_real_txid(value) is expected
