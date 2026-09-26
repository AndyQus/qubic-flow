"""Qearn principal/interest split, reconstruction and tax treatment.

Fixture values are real on-chain data (rpc.qubic.org, verified 2026-09-26):
  * lock epoch 161, 50 000 000 000 QU, yield 1 600 038 → payout 58 000 190 000
  * payout end of epoch 221 = 58 478 560 000, yield(169) 1 695 712 → principal 50 000 000 000
  * unlock input "AHQ7pAsAAACMAAAA" = 50 000 000 000 QU of the epoch-140 lock
  * lock epoch 158, 10 000 000 000 QU, yield 1 397 182 → expected 11 397 182 000
"""
import asyncio
import json

import pytest

import app.models.qearn  # noqa: F401  (tables for the in-memory DB)
from app.models.event import Event
from app.models.qearn import EventSplit, QearnPosition
from app.models.wallet import Wallet
from app.services import qearn_service as qs
from app.services.tax_engine import calculate_tax_report

Q = qs.QEARN_ADDRESS
W = "W" * 60


def _emap(current=232):
    # synthetic ticks: epoch e spans [e*1000, e*1000+999]
    return qs.EpochMap({e: (e * 1000, e * 1000 + 999) for e in range(130, current + 1)}, current)


def _lock(epoch, amount, n=0, h=None):
    return {"hash": h or f"lock{epoch}{n}", "tick": epoch * 1000 + 10 + n, "ts": f"2025-01-01T00:00:0{n}Z",
            "amount": amount, "input_type": 1, "input_b64": ""}


def _unlock(epoch, b64, n=0):
    return {"hash": f"unlock{epoch}{n}", "tick": epoch * 1000 + 500 + n, "ts": "2025-06-01T00:00:00Z",
            "amount": 0, "input_type": 2, "input_b64": b64}


def _payout(eid, epoch, amount, tick=None, reconstructed=False):
    return {"event_id": eid, "tick": tick or epoch * 1000 + 999, "epoch": epoch, "amount": amount,
            "timestamp": "2026-05-20T12:00:02Z", "reconstructed": reconstructed, "origin": "db"}


# ─────────────────────────── pure helpers ───────────────────────────

def test_decode_unlock_input_real_transaction():
    assert qs.decode_unlock_input("AHQ7pAsAAACMAAAA") == (50_000_000_000, 140)
    assert qs.decode_unlock_input("") is None
    assert qs.decode_unlock_input("AAAA") is None


def test_full_reward_matches_real_payout_epoch_161():
    assert qs.full_reward(50_000_000_000, 1_600_038) == 8_000_190_000


def test_derive_principal_matches_real_payout_epoch_221():
    assert qs.derive_principal(58_478_560_000, 1_695_712) == 50_000_000_000
    # round trip for arbitrary principals (unique preimage)
    for principal in (10_000_000, 123_456_789, 50_000_000_001, 999_999_999_999):
        assert qs.derive_principal(principal + qs.full_reward(principal, 1_695_712), 1_695_712) == principal


def test_early_unlock_percent_buckets():
    assert qs.early_unlock_percent(169, 140) == 30   # 28 locked weeks
    assert qs.early_unlock_percent(140, 140) == 0    # same epoch (uint32 wrap in contract)
    assert qs.early_unlock_percent(144, 140) == 0    # 3 weeks
    assert qs.early_unlock_percent(145, 140) == 5    # 4 weeks
    assert qs.early_unlock_percent(191, 140) == 55   # 50 weeks


def test_epoch_map_from_status_uses_first_interval_start():
    status = {
        "lastProcessedTick": {"tickNumber": 81758003, "epoch": 232},
        "processedTickIntervalsPerEpoch": [
            {"epoch": 213, "intervals": [{"initialProcessedTick": 52320000, "lastProcessedTick": 52748928}]},
            {"epoch": 214, "intervals": [{"initialProcessedTick": 52810000, "lastProcessedTick": 53750899}]},
            {"epoch": 218, "intervals": [{"initialProcessedTick": 59987647, "lastProcessedTick": 59987866},
                                         {"initialProcessedTick": 59400000, "lastProcessedTick": 60968390}]},
        ],
    }
    m = qs.EpochMap.from_status(status)
    assert m.current_epoch == 232
    assert m.epoch_of_tick(52748930) == 213   # real END_EPOCH payout tick (in the skipped gap)
    assert m.epoch_of_tick(59500000) == 218
    assert m.last_tick(213) == 52748928


# ─────────────────────────── matching ───────────────────────────

def test_regular_payout_split_exact():
    a = qs.compute_analysis(W, [_lock(161, 50_000_000_000)],
                            [_payout("p213", 213, 58_000_190_000)], {161: 1_600_038}, _emap())
    s = a["splits"]["p213"]
    assert (s["principal"], s["interest"], s["estimated"]) == (50_000_000_000, 8_000_190_000, False)
    assert s["meta"]["lock_epoch"] == 161 and s["meta"]["payout_epoch"] == 213
    assert s["meta"]["yield_mismatch"] is False
    pos = a["positions"][0]
    assert pos["status"] == "PAID" and pos["interest"] == 8_000_190_000
    assert a["classification"]["p213"] == qs.KIND_PAYOUT
    assert a["candidates"] == [] and a["issues"] == []


def test_multiple_locks_in_one_epoch_are_one_position():
    a = qs.compute_analysis(W, [_lock(161, 20_000_000_000, 0), _lock(161, 30_000_000_000, 1)],
                            [_payout("p", 213, 58_000_190_000)], {161: 1_600_038}, _emap())
    assert len(a["positions"]) == 1
    assert a["splits"]["p"]["principal"] == 50_000_000_000


def test_payout_without_known_lock_is_derived_from_yield():
    a = qs.compute_analysis(W, [], [_payout("p221", 221, 58_478_560_000)], {169: 1_695_712}, _emap())
    s = a["splits"]["p221"]
    assert (s["principal"], s["interest"]) == (50_000_000_000, 8_478_560_000)
    assert s["meta"]["derived"] is True
    assert a["positions"][0]["lock_epoch"] == 169


def test_missing_regular_payout_becomes_exact_candidate():
    a = qs.compute_analysis(W, [_lock(158, 10_000_000_000)], [], {158: 1_397_182}, _emap())
    assert a["positions"][0]["status"] == "MISSING"
    c = a["candidates"][0]
    assert c["kind"] == "FULL" and c["event_id"] == "qearn:158:F210"
    assert (c["principal"], c["interest"], c["amount"]) == (10_000_000_000, 1_397_182_000, 11_397_182_000)
    assert c["estimated"] is False
    assert c["tick"] == 210 * 1000 + 999  # last tick of the payout epoch


def test_open_round_is_locked_not_missing():
    a = qs.compute_analysis(W, [_lock(222, 50_000_000_000)], [], {222: 900_000}, _emap(232))
    assert a["positions"][0]["status"] == "LOCKED"
    assert a["positions"][0]["expected_payout"] == 50_000_000_000 + 4_500_000_000
    assert a["candidates"] == []


def test_real_wallet_history_lqmd():
    """3 locks (140, 154, 169), early unlock of the 140 lock in epoch 169, payout 221 in DB."""
    txs = [_lock(140, 50_000_000_000), _lock(154, 50_000_000_000), _unlock(169, "AHQ7pAsAAACMAAAA"),
           _lock(169, 50_000_000_000)]
    yields = {140: 651_477, 154: 1_111_509, 169: 1_695_712}
    a = qs.compute_analysis(W, txs, [_payout("p221", 221, 58_478_560_000)], yields, _emap())
    by_ep = {p["lock_epoch"]: p for p in a["positions"]}
    assert by_ep[140]["status"] == "EARLY_UNLOCKED"
    assert by_ep[154]["status"] == "MISSING"
    assert by_ep[169]["status"] == "PAID"
    assert a["splits"]["p221"]["interest"] == 8_478_560_000
    cands = {c["kind"]: c for c in a["candidates"]}
    # regular payout of the 154 lock at the end of epoch 206 — exact
    assert cands["FULL"]["amount"] == 50_000_000_000 + qs.full_reward(50_000_000_000, 1_111_509)
    # early unlock after 28 weeks → 30 % of the reward, estimated with the final yield
    early = cands["EARLY"]
    expected_reward = (651_477 * 50_000_000_000 // 100) * 30 // 10_000_000
    assert early["principal"] == 50_000_000_000 and early["interest"] == expected_reward
    assert early["estimated"] is True


def test_early_unlock_payout_in_same_tick_is_exact():
    txs = [_lock(200, 50_000_000_000), _unlock(210, "AHQ7pAsAAADIAAAA")]  # 50e9 of epoch 200
    assert qs.decode_unlock_input("AHQ7pAsAAADIAAAA") == (50_000_000_000, 200)
    a = qs.compute_analysis(W, txs, [_payout("early", 210, 50_123_456_789, tick=210 * 1000 + 500)],
                            {200: 1_000_000}, _emap())
    s = a["splits"]["early"]
    assert (s["principal"], s["interest"], s["estimated"]) == (50_000_000_000, 123_456_789, False)
    assert a["positions"][0]["status"] == "EARLY_UNLOCKED"


def test_unlock_leaving_less_than_minimum_unlocks_everything():
    # lock 50e9, request 49.995e9 → remainder 5M < 10M minimum → contract unlocks all 50e9
    import base64, struct
    b64 = base64.b64encode(struct.pack("<QI", 49_995_000_000, 200)).decode()
    a = qs.compute_analysis(W, [_lock(200, 50_000_000_000), _unlock(200, b64)], [], {200: 1_000_000}, _emap())
    c = a["candidates"][0]
    assert c["principal"] == 50_000_000_000 and c["interest"] == 0 and c["estimated"] is False


def test_rejected_lock_refund_is_not_a_position():
    lock = _lock(161, 5_000_000)  # below minimum → refunded in the same tick
    a = qs.compute_analysis(W, [lock], [_payout("refund", 161, 5_000_000, tick=lock["tick"])], {}, _emap())
    assert a["positions"] == []
    assert a["classification"]["refund"] == qs.KIND_REFUND


def test_reconstructed_payout_is_kept_until_real_one_appears():
    rec = _payout("qearn:158:F210", 210, 11_397_182_000, reconstructed=True)
    a = qs.compute_analysis(W, [_lock(158, 10_000_000_000)], [rec], {158: 1_397_182}, _emap())
    assert a["positions"][0]["status"] == "RECONSTRUCTED"
    assert a["splits"]["qearn:158:F210"]["interest"] == 1_397_182_000
    assert a["stale_reconstructed"] == []

    real = _payout("realpayout", 210, 11_397_182_000, tick=210 * 1000 + 1001)
    a = qs.compute_analysis(W, [_lock(158, 10_000_000_000)], [rec, real], {158: 1_397_182}, _emap())
    assert a["positions"][0]["status"] == "PAID"
    assert a["stale_reconstructed"] == ["qearn:158:F210"]


def test_unmatched_payout_is_reported_not_split():
    # mid-epoch transfer without unlock TX → not a regular payout, must not be derived
    a = qs.compute_analysis(W, [], [_payout("odd", 221, 12_345, tick=221 * 1000 + 400)], {169: 1_695_712}, _emap())
    assert "odd" not in a["splits"]
    assert a["issues"][0]["code"] == "unmatched_payout"
    assert a["classification"]["odd"] == qs.KIND_PAYOUT


# ─────────────────────────── persistence + tax ───────────────────────────

def _wallet(db, wid=W):
    db.add(Wallet(id=wid, label="Qearn", wallet_type="PRIVATE", active=1, created_at="2025-01-01T00:00:00Z"))
    db.flush()


def _ev(db, eid, src, dst, amount, ts, epoch, tick, sc_kind=None, rate=1e-6):
    db.add(Event(id=eid, wallet_id=W, epoch=epoch, tick_number=tick, timestamp=ts, source_address=src,
                 destination_addr=dst, amount_qubic=amount, qubic_eur_rate=rate, qubic_usd_rate=rate,
                 source_type="EVENT", is_internal=0, sc_kind=sc_kind, reconstructed=0,
                 created_at="2025-01-01T00:00:00Z"))


@pytest.fixture()
def no_prices(monkeypatch):
    async def _price(db, iso, cache):
        return {"eur": 2e-6, "usd": 2.2e-6}
    monkeypatch.setattr(qs, "_price", _price)


def _apply(db, analysis, confirmed=frozenset()):
    return asyncio.run(qs.apply_analysis(db, analysis, [], _emap(), set(confirmed)))


def test_apply_writes_splits_positions_and_imports_lock(db, no_prices):
    _wallet(db)
    _ev(db, "p213", Q, W, 58_000_190_000, "2026-05-20T12:00:02Z", 213, 213 * 1000 + 999)
    db.flush()
    a = qs.compute_analysis(W, [_lock(161, 50_000_000_000, h="a" * 60)],
                            [_payout("p213", 213, 58_000_190_000)], {161: 1_600_038}, _emap())
    a["txs"] = [_lock(161, 50_000_000_000, h="a" * 60)]
    stats = _apply(db, a)
    assert stats["locks_imported"] == 1 and stats["splits"] == 1
    lock = db.query(Event).filter(Event.id == "a" * 60).one()
    assert lock.sc_kind == qs.KIND_LOCK and lock.destination_addr == Q and lock.epoch == 161
    parts = {s.part: s.amount_qubic for s in db.query(EventSplit).filter(EventSplit.event_id == "p213")}
    assert parts == {"PRINCIPAL": 50_000_000_000, "INTEREST": 8_000_190_000}
    assert db.query(Event).filter(Event.id == "p213").one().sc_kind == qs.KIND_PAYOUT
    pos = db.query(QearnPosition).one()
    assert pos.status == "PAID" and pos.interest_qu == 8_000_190_000

    # idempotent: a second run changes nothing
    stats = _apply(db, a)
    assert stats["locks_imported"] == 0
    assert db.query(EventSplit).count() == 2


def test_reconstruction_only_when_confirmed(db, no_prices):
    _wallet(db)
    txs = [_lock(158, 10_000_000_000, h="b" * 60)]
    a = qs.compute_analysis(W, txs, [], {158: 1_397_182}, _emap())
    a["txs"] = txs
    _apply(db, a)
    assert db.query(Event).filter(Event.reconstructed == 1).count() == 0
    assert db.query(QearnPosition).one().status == "MISSING"

    stats = _apply(db, a, {"qearn:158:F210"})
    assert stats["reconstructed"] == 1
    rec = db.query(Event).filter(Event.id == "qearn:158:F210").one()
    assert rec.reconstructed == 1 and rec.amount_qubic == 11_397_182_000 and rec.epoch == 210
    assert rec.tick_number == 210 * 1000 + 999
    assert db.query(QearnPosition).one().status == "RECONSTRUCTED"
    parts = {s.part: s.amount_qubic for s in db.query(EventSplit).filter(EventSplit.event_id == rec.id)}
    assert parts == {"PRINCIPAL": 10_000_000_000, "INTEREST": 1_397_182_000}


def test_stale_reconstruction_is_removed(db, no_prices):
    _wallet(db)
    txs = [_lock(158, 10_000_000_000, h="c" * 60)]
    a = qs.compute_analysis(W, txs, [], {158: 1_397_182}, _emap())
    a["txs"] = txs
    _apply(db, a, {"qearn:158:F210"})
    _ev(db, "realid", Q, W, 11_397_182_000, "2026-04-29T12:00:01Z", 210, 210 * 1000 + 1001)
    db.flush()
    payouts = [_payout("qearn:158:F210", 210, 11_397_182_000, reconstructed=True),
               _payout("realid", 210, 11_397_182_000, tick=210 * 1000 + 1001)]
    a = qs.compute_analysis(W, txs, payouts, {158: 1_397_182}, _emap())
    a["txs"] = txs
    stats = _apply(db, a)
    assert stats["removed"] == 1
    assert db.query(Event).filter(Event.id == "qearn:158:F210").count() == 0
    assert db.query(EventSplit).filter(EventSplit.event_id == "realid").count() == 2


def test_override_estimated_interest(db, no_prices):
    _wallet(db)
    txs = [_lock(140, 50_000_000_000, h="d" * 60), _unlock(169, "AHQ7pAsAAACMAAAA")]
    a = qs.compute_analysis(W, txs, [], {140: 651_477}, _emap())
    a["txs"] = txs
    eid = next(c["event_id"] for c in a["candidates"] if c["kind"] == "EARLY")
    _apply(db, a, {eid})
    res = asyncio.run(qs.override_interest(db, eid, W, 500_000_000))
    assert res["amount_qubic"] == 50_500_000_000
    interest = db.query(EventSplit).filter(EventSplit.event_id == eid, EventSplit.part == "INTEREST").one()
    assert interest.amount_qubic == 500_000_000 and interest.estimated == 0
    assert json.loads(interest.meta_json)["override"] is True

    # a later analysis keeps the user's value
    payouts = [_payout(eid, 169, 50_500_000_000, tick=169 * 1000 + 500, reconstructed=True)]
    payouts[0]["override"] = True
    a2 = qs.compute_analysis(W, txs, payouts, {140: 651_477}, _emap())
    assert a2["splits"][eid]["interest"] == 500_000_000
    assert a2["splits"][eid]["meta"]["override"] is True


def test_override_rejected_for_exact_payout(db, no_prices):
    _wallet(db)
    _ev(db, "p213", Q, W, 58_000_190_000, "2026-05-20T12:00:02Z", 213, 213 * 1000 + 999)
    db.flush()
    a = qs.compute_analysis(W, [_lock(161, 50_000_000_000, h="e" * 60)],
                            [_payout("p213", 213, 58_000_190_000)], {161: 1_600_038}, _emap())
    a["txs"] = []
    _apply(db, a)
    with pytest.raises(PermissionError):
        asyncio.run(qs.override_interest(db, "p213", W, 1))


def test_tax_lock_is_no_disposal_and_only_interest_is_income(db, no_prices):
    _wallet(db)
    from app.models.opening_position import OpeningPosition
    db.add(OpeningPosition(wallet_id=W, date="2024-01-01", amount_qubic=50_000_000_000,
                           price_eur=1e-6, price_usd=1e-6, created_at="2024-01-01T00:00:00Z"))
    _ev(db, "f" * 60, W, Q, 50_000_000_000, "2025-05-21T11:57:31Z", 161, 161 * 1000 + 10,
        sc_kind=qs.KIND_LOCK, rate=3e-6)
    _ev(db, "p213", Q, W, 58_000_190_000, "2026-05-20T12:00:02Z", 213, 213 * 1000 + 999,
        sc_kind=qs.KIND_PAYOUT, rate=2e-6)
    db.flush()
    a = qs.compute_analysis(W, [_lock(161, 50_000_000_000, h="f" * 60)],
                            [_payout("p213", 213, 58_000_190_000)], {161: 1_600_038}, _emap())
    a["txs"] = []
    _apply(db, a)

    r2025 = calculate_tax_report(db, [W], 2025, "private", "DE", "FIFO")
    assert r2025["disposals"] == []                      # lock is not a sale
    assert r2025["year_end_holdings"][0]["amount_qubic"] == 50_000_000_000  # still owned

    r2026 = calculate_tax_report(db, [W], 2026, "private", "DE", "FIFO")
    assert len(r2026["income"]) == 1
    inc = r2026["income"][0]
    assert inc["amount_qubic"] == 8_000_190_000 and inc["kind"] == "qearn_interest"
    assert inc["value"] == pytest.approx(8_000_190_000 * 2e-6)
    assert r2026["qearn_unsplit"] == 0
    holdings = r2026["year_end_holdings"][0]
    assert holdings["amount_qubic"] == 58_000_190_000
    # principal lot kept its 2024 cost basis, interest lot has the payout-day price
    assert holdings["cost_basis_eur"] == pytest.approx(50_000_000_000 * 1e-6 + 8_000_190_000 * 2e-6)


def test_tax_unsplit_payout_is_flagged(db):
    _wallet(db)
    _ev(db, "p213", Q, W, 58_000_190_000, "2026-05-20T12:00:02Z", 213, 213 * 1000 + 999, sc_kind=qs.KIND_PAYOUT)
    db.flush()
    r = calculate_tax_report(db, [W], 2026, "private", "DE", "FIFO")
    assert r["qearn_unsplit"] == 1
    assert r["income"][0]["amount_qubic"] == 58_000_190_000


def test_events_api_returns_parts(db, client, no_prices):
    _wallet(db)
    _ev(db, "p213", Q, W, 58_000_190_000, "2026-05-20T12:00:02Z", 213, 213 * 1000 + 999)
    db.flush()
    a = qs.compute_analysis(W, [_lock(161, 50_000_000_000, h="g" * 60)],
                            [_payout("p213", 213, 58_000_190_000)], {161: 1_600_038}, _emap())
    a["txs"] = []
    _apply(db, a)
    rows = client.get(f"/api/v1/events?wallet_id={W}").json()
    row = next(r for r in rows if r["id"] == "p213")
    assert row["sc_kind"] == qs.KIND_PAYOUT
    assert [p["part"] for p in row["qearn_parts"]] == ["PRINCIPAL", "INTEREST"]
    assert row["qearn_parts"][1]["amount_qubic"] == 8_000_190_000
    assert row["qearn_parts"][1]["meta"]["lock_epoch"] == 161
    pos = client.get("/api/v1/qearn/positions").json()
    assert pos[0]["status"] == "PAID"


def test_dedup_prefers_real_payout_over_reconstruction(db):
    from app.services.dedup_service import dedup_events
    _wallet(db)
    for eid, rec in (("qearn:158:F210", 1), ("realid", 0)):
        db.add(Event(id=eid, wallet_id=W, epoch=210, tick_number=5, timestamp="2026-04-29T12:00:00Z",
                     source_address=Q, destination_addr=W, amount_qubic=11_397_182_000,
                     source_type="EVENT", is_internal=0, reconstructed=rec, sc_kind=qs.KIND_PAYOUT,
                     created_at="2020-01-01T00:00:00Z" if rec else "2026-01-01T00:00:00Z"))
    db.add(EventSplit(event_id="qearn:158:F210", wallet_id=W, part="PRINCIPAL", amount_qubic=1, estimated=0))
    db.flush()
    dedup_events(db, wallet_id=W)
    left = db.query(Event).filter(Event.wallet_id == W).all()
    assert [e.id for e in left] == ["realid"]
    assert left[0].sc_kind is None  # triggers Qearn auto-processing to rebuild the split
    assert db.query(EventSplit).count() == 0


def _split_payout_setup(db):
    _wallet(db)
    _ev(db, "h" * 60, W, Q, 50_000_000_000, "2025-05-21T11:57:31Z", 161, 161 * 1000 + 10, sc_kind=qs.KIND_LOCK)
    _ev(db, "p213", Q, W, 58_000_190_000, "2026-05-20T12:00:02Z", 213, 213 * 1000 + 999, sc_kind=qs.KIND_PAYOUT)
    db.flush()
    a = qs.compute_analysis(W, [_lock(161, 50_000_000_000, h="h" * 60)],
                            [_payout("p213", 213, 58_000_190_000)], {161: 1_600_038}, _emap())
    a["txs"] = []
    _apply(db, a)


def test_exports_only_contain_qearn_interest(db, no_prices):
    from app.services.export_service import export_koinly, export_blockpit, export_cointracking
    _split_payout_setup(db)
    for fn in (export_koinly, export_blockpit, export_cointracking):
        csv_text = fn(db)
        assert "8000190000" in csv_text, fn.__name__           # interest row
        assert "58000190000" not in csv_text, fn.__name__      # never the full payout
        assert "50000000000" not in csv_text, fn.__name__      # neither lock nor principal
        assert "Qearn interest Ep. 161–213" in csv_text, fn.__name__


def test_backup_roundtrip_keeps_splits_and_positions(db, client, no_prices):
    _split_payout_setup(db)
    dump = client.get("/api/v1/backup").json()
    assert len(dump["event_splits"]) == 2 and len(dump["qearn_positions"]) == 1
    assert next(e for e in dump["events"] if e["id"] == "p213")["sc_kind"] == qs.KIND_PAYOUT
    db.query(EventSplit).delete()
    db.query(QearnPosition).delete()
    db.query(Event).delete()
    db.flush()
    from unittest.mock import patch
    with patch("app.api.v1.backup.check_all_balances"):
        stats = client.post("/api/v1/backup/restore", json=dump).json()
    assert stats["event_splits"]["created"] == 2 and stats["qearn_positions"] == "restored"
    assert db.query(Event).filter(Event.id == "p213").one().sc_kind == qs.KIND_PAYOUT
    r = calculate_tax_report(db, [W], 2026, "private", "DE", "FIFO")
    assert r["income"][0]["amount_qubic"] == 8_000_190_000
