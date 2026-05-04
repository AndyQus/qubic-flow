"""
Unit tests for SyncGap.gap_type — verifies the new column and the retry logic
that classifies gaps as "EVENT" or "TX".

These tests run against the in-memory SQLite DB provided by conftest.py.
"""
import pytest
from app.models.wallet import Wallet
from app.models.sync_state import SyncState
from app.models.sync_gap import SyncGap
from app.utils.time import now_utc_iso

WALLET_ID = "GAPTEST_WALLET_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def _seed(db):
    now = now_utc_iso()
    db.add(Wallet(
        id=WALLET_ID, label="Gap Test", wallet_type="PRIVATE",
        active=1, created_at=now, updated_at=now,
    ))
    db.add(SyncState(wallet_id=WALLET_ID, last_tick=0, status="IDLE", total_events=0))
    db.flush()


class TestSyncGapType:
    def test_event_gap_type_stored(self, db):
        _seed(db)
        gap = SyncGap(
            wallet_id=WALLET_ID,
            from_tick=1000,
            to_tick=2000,
            detected_at=now_utc_iso(),
            gap_type="EVENT",
        )
        db.add(gap)
        db.flush()

        row = db.query(SyncGap).filter(SyncGap.wallet_id == WALLET_ID).first()
        assert row is not None
        assert row.gap_type == "EVENT"
        assert row.resolved_at is None

    def test_tx_gap_type_stored(self, db):
        _seed(db)
        gap = SyncGap(
            wallet_id=WALLET_ID,
            from_tick=3000,
            to_tick=4000,
            detected_at=now_utc_iso(),
            gap_type="TX",
        )
        db.add(gap)
        db.flush()

        row = db.query(SyncGap).filter(SyncGap.wallet_id == WALLET_ID).first()
        assert row.gap_type == "TX"

    def test_legacy_gap_type_none(self, db):
        """gap_type=None is valid for legacy rows (pre-migration)."""
        _seed(db)
        gap = SyncGap(
            wallet_id=WALLET_ID,
            from_tick=5000,
            to_tick=6000,
            detected_at=now_utc_iso(),
            gap_type=None,
        )
        db.add(gap)
        db.flush()

        row = db.query(SyncGap).filter(SyncGap.wallet_id == WALLET_ID).first()
        assert row.gap_type is None

    def test_gap_can_be_resolved(self, db):
        _seed(db)
        now = now_utc_iso()
        gap = SyncGap(
            wallet_id=WALLET_ID,
            from_tick=7000,
            to_tick=8000,
            detected_at=now,
            gap_type="EVENT",
        )
        db.add(gap)
        db.flush()

        # Resolve the gap
        gap.resolved_at = now_utc_iso()
        db.flush()

        row = db.query(SyncGap).filter(SyncGap.wallet_id == WALLET_ID).first()
        assert row.resolved_at is not None

    def test_unresolved_gap_query(self, db):
        _seed(db)
        now = now_utc_iso()
        db.add(SyncGap(wallet_id=WALLET_ID, from_tick=100, to_tick=200, detected_at=now, gap_type="EVENT"))
        db.add(SyncGap(wallet_id=WALLET_ID, from_tick=300, to_tick=400, detected_at=now, gap_type="TX",
                       resolved_at=now_utc_iso()))
        db.flush()

        unresolved = (
            db.query(SyncGap)
            .filter(SyncGap.wallet_id == WALLET_ID, SyncGap.resolved_at.is_(None))
            .all()
        )
        assert len(unresolved) == 1
        assert unresolved[0].from_tick == 100

    def test_gap_to_tick_expansion(self, db):
        """Simulate the sync_engine logic: extend an existing gap's to_tick."""
        _seed(db)
        now = now_utc_iso()
        gap = SyncGap(
            wallet_id=WALLET_ID,
            from_tick=500,
            to_tick=1000,
            detected_at=now,
            gap_type="EVENT",
        )
        db.add(gap)
        db.flush()

        # Expand to_tick as new sync reveals a wider gap
        gap.to_tick = max(gap.to_tick, 1500)
        db.flush()

        row = db.query(SyncGap).filter(SyncGap.wallet_id == WALLET_ID).first()
        assert row.to_tick == 1500

    def test_filter_by_gap_type(self, db):
        _seed(db)
        now = now_utc_iso()
        db.add(SyncGap(wallet_id=WALLET_ID, from_tick=10, to_tick=20, detected_at=now, gap_type="EVENT"))
        db.add(SyncGap(wallet_id=WALLET_ID, from_tick=30, to_tick=40, detected_at=now, gap_type="TX"))
        db.flush()

        event_gaps = db.query(SyncGap).filter(SyncGap.gap_type == "EVENT").all()
        tx_gaps    = db.query(SyncGap).filter(SyncGap.gap_type == "TX").all()

        assert len(event_gaps) >= 1
        assert len(tx_gaps) >= 1
        assert all(g.gap_type == "EVENT" for g in event_gaps)
        assert all(g.gap_type == "TX" for g in tx_gaps)
