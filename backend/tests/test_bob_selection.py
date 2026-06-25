"""
Tests for tick-based BOB-node selection in sync_engine._select_best_bob.

The live-sync source is no longer chosen by priority alone. Among all active
ONLINE/DEGRADED BOB nodes, the one with the highest tick wins; a node lagging
more than MAX_BOB_LAG ticks behind the RPC tip is skipped so a stalled primary
node can no longer block live sync.
"""
import pytest

from app.models.node import Node
from app.utils.time import now_utc_iso
from app.services import sync_engine
from app.services.sync_engine import _select_best_bob, MAX_BOB_LAG


def _bob(db, url, tick, priority=1, status="ONLINE", is_active=1):
    n = Node(
        url=url,
        node_type="BOB_NODE",
        label=None,
        priority=priority,
        is_active=is_active,
        health_status=status,
        tick=tick,
        fail_count=0,
        last_checked=now_utc_iso(),
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


class TestSelectBestBob:
    def test_highest_tick_wins_over_priority(self, db):
        """A lower-priority BOB with a higher tick beats a stalled primary."""
        primary = _bob(db, "https://bob-primary", tick=1000, priority=1)
        secondary = _bob(db, "https://bob-secondary", tick=1500, priority=2)
        rpc_tick = 1500

        best = _select_best_bob(db, rpc_tick)
        assert best.id == secondary.id

    def test_priority_breaks_tie_on_equal_tick(self, db):
        a = _bob(db, "https://bob-a", tick=2000, priority=5)
        b = _bob(db, "https://bob-b", tick=2000, priority=2)

        best = _select_best_bob(db, rpc_tick=2000)
        assert best.id == b.id  # lower priority number wins the tie

    def test_stalled_best_bob_rejected_when_lag_exceeds_threshold(self, db):
        """If even the best BOB lags > MAX_BOB_LAG, fall back to RPC (None)."""
        _bob(db, "https://bob-1", tick=1000, priority=1)
        _bob(db, "https://bob-2", tick=1200, priority=2)
        rpc_tick = 1200 + MAX_BOB_LAG + 1

        assert _select_best_bob(db, rpc_tick) is None

    def test_best_bob_accepted_within_threshold(self, db):
        node = _bob(db, "https://bob-1", tick=5000, priority=1)
        rpc_tick = 5000 + MAX_BOB_LAG  # exactly at the limit → still accepted

        best = _select_best_bob(db, rpc_tick)
        assert best is not None and best.id == node.id

    def test_no_bob_nodes_returns_none(self, db):
        assert _select_best_bob(db, rpc_tick=1000) is None

    def test_offline_bob_nodes_ignored(self, db):
        _bob(db, "https://bob-off", tick=9999, priority=1, status="OFFLINE")
        online = _bob(db, "https://bob-on", tick=1000, priority=2, status="ONLINE")

        best = _select_best_bob(db, rpc_tick=1000)
        assert best.id == online.id

    def test_inactive_bob_nodes_ignored(self, db):
        _bob(db, "https://bob-inactive", tick=9999, priority=1, is_active=0)
        active = _bob(db, "https://bob-active", tick=1000, priority=2)

        best = _select_best_bob(db, rpc_tick=1000)
        assert best.id == active.id

    def test_no_rpc_tick_skips_lag_check(self, db):
        """Without a known RPC tip we cannot judge lag — accept the best BOB."""
        node = _bob(db, "https://bob-1", tick=1, priority=1)
        best = _select_best_bob(db, rpc_tick=None)
        assert best is not None and best.id == node.id
