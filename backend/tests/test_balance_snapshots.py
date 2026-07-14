"""Tests for the Bestandsverlauf feature: bucket slots, edit audit trail and
Excel workbook generation from the template layout."""
import json
import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.balance_snapshot import BalanceSnapshot, SnapshotAnnotation
from app.models.event import Event
from app.models.wallet import Wallet
from app.services.balance_snapshot_service import bucket_for, apply_edit, reset_series
from app.services.excel_workbook_service import build_workbook, build_owner_rows, build_flat_rows


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed(db):
    db.add(Wallet(id="WALLETA" * 8 + "AAAA", label="Qx Anna", owner="Anna",
                  wallet_type="PRIVATE", active=1, created_at="2026-01-01T00:00:00+00:00"))
    db.add(Wallet(id="WALLETB" * 8 + "BBBB", label="Qearn Ben", owner="Ben",
                  wallet_type="PRIVATE", active=1, created_at="2026-01-01T00:00:00+00:00"))
    wid_a = "WALLETA" * 8 + "AAAA"
    wid_b = "WALLETB" * 8 + "BBBB"
    for i, (bucket, captured) in enumerate([
        ("e220", "2026-07-08T12:00:05+00:00"),
        ("e221", "2026-07-15T12:00:05+00:00"),
    ]):
        for wid, base in ((wid_a, 100), (wid_b, 500)):
            balance = base + i * 50
            db.add(BalanceSnapshot(
                kind="weekly", bucket=bucket, trigger="auto",
                captured_at=captured,
                range_from=None if i == 0 else "2026-07-08T12:00:05+00:00",
                range_to=captured,
                wallet_id=wid, label="Qx Anna" if wid == wid_a else "Qearn Ben",
                owner="Anna" if wid == wid_a else "Ben",
                balance=balance, delta=None if i == 0 else 50,
                epoch=220 + i, eur_rate=0.0000006, usd_rate=0.0000007,
                value_eur=balance * 0.0000006, value_usd=balance * 0.0000007,
                tick=66_000_000 + i, source="rpc", edited=0,
                created_at=captured,
            ))
    db.add(SnapshotAnnotation(kind="weekly", bucket="e221", why="Dividenden",
                              info="Test-Info", note="Notiz", updated_at="2026-07-15T12:01:00+00:00"))
    db.commit()
    return wid_a, wid_b


def test_bucket_for_slots():
    now = datetime(2026, 7, 15, 13, 45, tzinfo=timezone.utc)
    assert bucket_for("hourly", now, 221) == "2026-07-15T13"
    assert bucket_for("daily", now, 221) == "2026-07-15"
    assert bucket_for("weekly", now, 221) == "e221"
    assert bucket_for("weekly", now, None) == "w2026-07-15"


def test_apply_edit_preserves_original(db):
    _seed(db)
    snap = db.query(BalanceSnapshot).filter(BalanceSnapshot.bucket == "e221").first()
    original_delta = snap.delta
    apply_edit(db, snap, {"delta": 999})
    assert snap.edited == 1
    assert snap.delta == 999
    saved = json.loads(snap.original_json)
    assert saved["delta"] == original_delta
    # second edit must not overwrite the original audit values
    apply_edit(db, snap, {"delta": 1234})
    assert json.loads(snap.original_json)["delta"] == original_delta


def test_workbook_structure(db):
    wid_a, wid_b = _seed(db)
    wb = build_workbook(db, "weekly", "de")

    # overview sheet is named plain "Ledger" (not LedgerPrivat like the user's template)
    assert wb.sheetnames[0] == "Ledger"
    assert wb.sheetnames[1] == "Bestand"
    assert "LedgerAnna" in wb.sheetnames
    assert "LedgerBen" in wb.sheetnames
    assert "Transfer" in wb.sheetnames
    assert "MyLedgerCSV" in wb.sheetnames

    ws = wb["Ledger"]
    # header row 7: fixed columns then wallet labels grouped by owner
    assert ws.cell(row=7, column=1).value == "Datum"
    assert ws.cell(row=7, column=2).value == "Epoch"
    assert ws.cell(row=7, column=7).value == "why"
    assert ws.cell(row=7, column=8).value == "Qx Anna"
    assert ws.cell(row=7, column=9).value == "Qearn Ben"

    # first data row (row 8) is the baseline without delta, second has 50
    assert ws.cell(row=8, column=8).value is None
    assert ws.cell(row=9, column=8).value == 50
    assert ws.cell(row=9, column=2).value == 221
    assert ws.cell(row=9, column=7).value == "Dividenden"

    # price per 1 billion QUBIC
    assert ws.cell(row=9, column=5).value == pytest.approx(600.0)

    # per-owner EUR formula references the EUR price cell
    owner_cell = ws.cell(row=9, column=11)  # info at 10, owners at 11..12
    assert str(owner_cell.value).startswith("=(SUM(")
    assert "/1000000000)*E9" in str(owner_cell.value)

    # balance sheet: absolute balances per wallet + total/value formulas
    bs = wb["Bestand"]
    assert bs.cell(row=3, column=1).value == "Datum"
    assert bs.cell(row=2, column=5).value == "Anna"     # owner row above labels
    assert bs.cell(row=3, column=5).value == "Qx Anna"
    assert bs.cell(row=4, column=5).value == 100        # first capture balances
    assert bs.cell(row=4, column=6).value == 500
    assert bs.cell(row=5, column=5).value == 150        # second capture balances
    assert bs.cell(row=5, column=6).value == 550
    assert str(bs.cell(row=5, column=7).value) == "=SUM(E5:F5)"   # total
    assert "/1000000000)*C5" in str(bs.cell(row=5, column=8).value)  # value €


def _seed_tx(db, wid, ts, amount, incoming=True, eid="tx1"):
    ext = "E" * 60
    db.add(Event(
        id=eid, wallet_id=wid, timestamp=ts, epoch=221,
        source_address=ext if incoming else wid,
        destination_addr=wid if incoming else ext,
        amount_qubic=amount, source_type="TX", is_internal=0,
        qubic_eur_rate=4e-7, qubic_usd_rate=5e-7,
    ))
    db.commit()


def test_owner_rows_residual_from_balance_delta(db):
    """User's rule: previous balance 100, new balance 150 with one incoming
    TX of 30 in the interval → the events row of that slot carries 20.
    Locally synced SC events are not consulted at all."""
    wid_a, wid_b = _seed(db)   # weekly snapshots: baseline e220, delta 50 each at e221
    _seed_tx(db, wid_a, "2026-07-10T09:00:00+00:00", 30, incoming=True)
    # an SC event in the DB must be ignored by the ledger
    db.add(Event(
        id="ev-ignored", wallet_id=wid_a, timestamp="2026-07-11T09:00:00+00:00", epoch=221,
        source_address="E" * 60, destination_addr=wid_a,
        amount_qubic=999999, source_type="EVENT", is_internal=0,
        qubic_eur_rate=4e-7, qubic_usd_rate=5e-7,
    ))
    db.commit()
    wallets = [{"id": wid_a, "label": "Qx Anna"}, {"id": wid_b, "label": "Qearn Ben"}]

    rows = build_owner_rows(db, wallets, "weekly")
    assert len(rows) == 2
    tx, agg = rows[0], rows[1]
    # TX keeps its own timestamp and stays individual
    assert tx["type"] == "tx" and tx["ts"] == datetime(2026, 7, 10, 9, 0)
    assert tx["cells"] == {wid_a: 30}
    # events row = balance delta minus TX of the interval, per wallet
    assert agg["type"] == "aggregate" and agg["ts"] == datetime(2026, 7, 15, 12, 0, 5)
    assert agg["cells"] == {wid_a: 20, wid_b: 50}
    assert agg["eur_rate"] == pytest.approx(0.0000006)

    # a series without captures has no ledger rows at all
    assert build_owner_rows(db, wallets, "daily") == []

    # flat MyLedgerCSV rows: one TX row + one residual row per wallet
    flat = build_flat_rows(db, wallets, "weekly")
    assert [(r["wallet_id"], r["amount"], r["is_sc"]) for r in flat] == [
        (wid_a, 30, False), (wid_a, 20, True), (wid_b, 50, True),
    ]


def test_owner_rows_ignore_tx_before_baseline(db):
    wid_a, wid_b = _seed(db)
    _seed_tx(db, wid_a, "2026-07-01T09:00:00+00:00", 40, incoming=True)  # before baseline
    wallets = [{"id": wid_a, "label": "Qx Anna"}]
    rows = build_owner_rows(db, wallets, "weekly")
    # no TX row shown, and the full delta stays attributed to events
    assert [r["type"] for r in rows] == ["aggregate"]
    assert rows[0]["cells"] == {wid_a: 50}


def test_owner_sheet_has_full_public_ids(db):
    wid_a, _ = _seed(db)
    wb = build_workbook(db, "hourly", "de")
    ws = wb["LedgerAnna"]
    assert ws.cell(row=2, column=6).value == "Qx Anna"   # label row
    assert ws.cell(row=3, column=6).value == wid_a       # full publicId row


def test_reset_series_only_touches_one_kind(db):
    _seed(db)
    # a second series must survive the weekly reset
    db.add(BalanceSnapshot(
        kind="daily", bucket="2026-07-14", trigger="auto",
        captured_at="2026-07-14T12:00:05+00:00", wallet_id="WALLETA" * 8 + "AAAA",
        label="Qx Anna", owner="Anna", balance=100, epoch=221,
        source="rpc", edited=0, created_at="2026-07-14T12:00:05+00:00",
    ))
    db.commit()

    deleted = reset_series(db, "weekly")
    assert deleted == 4  # 2 buckets x 2 wallets
    assert db.query(BalanceSnapshot).filter(BalanceSnapshot.kind == "weekly").count() == 0
    assert db.query(SnapshotAnnotation).filter(SnapshotAnnotation.kind == "weekly").count() == 0
    assert db.query(BalanceSnapshot).filter(BalanceSnapshot.kind == "daily").count() == 1

    with pytest.raises(ValueError):
        reset_series(db, "monthly")


def test_workbook_bytes_roundtrip(db):
    _seed(db)
    from app.services.excel_workbook_service import build_workbook_bytes
    data = build_workbook_bytes(db, "weekly", "en")
    assert data[:2] == b"PK"  # xlsx = zip container
    assert len(data) > 1000
