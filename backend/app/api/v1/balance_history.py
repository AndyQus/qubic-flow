import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.balance_snapshot import BalanceSnapshot, SnapshotAnnotation
from ...models.event import Event
from ...models.wallet import Wallet
from ...utils.time import now_utc_iso
from ...services import balance_snapshot_service as bhs
from ...services.excel_workbook_service import (
    build_workbook_bytes, write_workbooks, export_file_path, FILE_NAMES,
    _wallet_columns, _owner_groups,
)
from ...services.coingecko import get_price_for_date

logger = logging.getLogger(__name__)
router = APIRouter()


def _refresh_exports_after_change(background_tasks: BackgroundTasks, db: Session, kind: str):
    """Edits are part of the exported files — regenerate the affected series'
    file in the background so UI and Excel stay identical (only when auto
    export is enabled)."""
    if bhs.get_bh_settings(db).get("bh_excel_autoexport", "true") == "true":
        background_tasks.add_task(write_workbooks, [kind])


# ---------------------------------------------------------------- settings

class BHSettings(BaseModel):
    bh_hourly_enabled: Optional[bool] = None
    bh_daily_enabled: Optional[bool] = None
    bh_weekly_enabled: Optional[bool] = None
    bh_excel_autoexport: Optional[bool] = None
    bh_hourly_retention_days: Optional[int] = None
    bh_export_lang: Optional[str] = None


def _settings_out(raw: dict) -> dict:
    return {
        "hourly_enabled": raw["bh_hourly_enabled"] == "true",
        "daily_enabled": raw["bh_daily_enabled"] == "true",
        "weekly_enabled": raw["bh_weekly_enabled"] == "true",
        "excel_autoexport": raw["bh_excel_autoexport"] == "true",
        "hourly_retention_days": int(raw["bh_hourly_retention_days"] or 0),
        "export_lang": raw["bh_export_lang"],
    }


@router.get("/balance-history/settings")
def get_settings(db: Session = Depends(get_db)):
    return _settings_out(bhs.get_bh_settings(db))


@router.put("/balance-history/settings")
def put_settings(body: BHSettings, db: Session = Depends(get_db)):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    return _settings_out(bhs.save_bh_settings(db, values))


# ---------------------------------------------------------------- overview

def _snap_out(s: BalanceSnapshot) -> dict:
    return {
        "id": s.id, "delta": s.delta, "balance": s.balance,
        "in_amount": s.in_amount, "out_amount": s.out_amount,
        "tick": s.tick, "edited": bool(s.edited), "source": s.source,
        "value_eur": s.value_eur, "value_usd": s.value_usd,
    }


@router.get("/balance-history/overview")
def overview(kind: str = Query(...), db: Session = Depends(get_db)):
    if kind not in bhs.KINDS:
        raise HTTPException(400, "invalid kind")
    columns = _wallet_columns(db, kind)
    groups = _owner_groups(columns)

    snaps = (
        db.query(BalanceSnapshot)
        .filter(BalanceSnapshot.kind == kind)
        .order_by(BalanceSnapshot.captured_at.desc(), BalanceSnapshot.id.desc())
        .all()
    )
    annotations = {
        a.bucket: a
        for a in db.query(SnapshotAnnotation).filter(SnapshotAnnotation.kind == kind).all()
    }
    buckets: dict[str, dict] = {}
    order: list[str] = []
    for s in snaps:
        if s.bucket not in buckets:
            ann = annotations.get(s.bucket)
            buckets[s.bucket] = {
                "bucket": s.bucket, "captured_at": s.captured_at,
                "range_from": s.range_from, "range_to": s.range_to,
                "epoch": s.epoch, "eur_rate": s.eur_rate, "usd_rate": s.usd_rate,
                "trigger": s.trigger,
                "why": ann.why if ann else None,
                "info": ann.info if ann else None,
                "note": ann.note if ann else None,
                "cells": {},
            }
            order.append(s.bucket)
        b = buckets[s.bucket]
        b["cells"][s.wallet_id] = _snap_out(s)
        if b["eur_rate"] is None and s.eur_rate is not None:
            b["eur_rate"] = s.eur_rate
        if b["usd_rate"] is None and s.usd_rate is not None:
            b["usd_rate"] = s.usd_rate

    totals: dict[str, int] = {}
    for s in snaps:
        if s.delta is not None:
            totals[s.wallet_id] = totals.get(s.wallet_id, 0) + s.delta

    return {
        "kind": kind,
        "columns": columns,
        "owners": [
            {"owner": g["owner"], "wallet_ids": [c["id"] for c in columns[g["start"]:g["end"] + 1]]}
            for g in groups
        ],
        "rows": [buckets[b] for b in order],
        "totals": totals,
    }


# ---------------------------------------------------------------- capture

class CaptureBody(BaseModel):
    kind: str = "hourly"


@router.post("/balance-history/capture")
async def capture_now(background_tasks: BackgroundTasks, body: CaptureBody | None = None,
                      db: Session = Depends(get_db)):
    kind = (body.kind if body else "hourly") or "hourly"
    if kind not in bhs.KINDS:
        raise HTTPException(400, "invalid kind")
    # Excel regeneration runs as background task — writing the workbook of a
    # large database inline made the capture button hang for minutes.
    result = await bhs.capture_snapshots(kind, trigger="manual", export=False)
    if result.get("captured") and bhs.get_bh_settings(db).get("bh_excel_autoexport", "true") == "true":
        background_tasks.add_task(write_workbooks, [kind])
    return result


# ---------------------------------------------------------------- editing

class SnapshotEdit(BaseModel):
    balance: Optional[int] = None
    delta: Optional[int] = None
    in_amount: Optional[int] = None
    out_amount: Optional[int] = None
    eur_rate: Optional[float] = None
    usd_rate: Optional[float] = None


@router.patch("/balance-history/snapshots/{snapshot_id}")
def edit_snapshot(snapshot_id: int, body: SnapshotEdit, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    snap = db.query(BalanceSnapshot).filter(BalanceSnapshot.id == snapshot_id).first()
    if not snap:
        raise HTTPException(404, "snapshot not found")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    snap = bhs.apply_edit(db, snap, changes)
    _refresh_exports_after_change(background_tasks, db, snap.kind)
    return _snap_out(snap)


class AnnotationBody(BaseModel):
    kind: str
    bucket: str
    why: Optional[str] = None
    info: Optional[str] = None
    note: Optional[str] = None


@router.patch("/balance-history/annotations")
def upsert_annotation(body: AnnotationBody, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if body.kind not in bhs.KINDS:
        raise HTTPException(400, "invalid kind")
    row = (
        db.query(SnapshotAnnotation)
        .filter(SnapshotAnnotation.kind == body.kind, SnapshotAnnotation.bucket == body.bucket)
        .first()
    )
    if not row:
        row = SnapshotAnnotation(kind=body.kind, bucket=body.bucket)
        db.add(row)
    row.why = body.why
    row.info = body.info
    row.note = body.note
    row.updated_at = now_utc_iso()
    db.commit()
    _refresh_exports_after_change(background_tasks, db, body.kind)
    return {"kind": row.kind, "bucket": row.bucket, "why": row.why, "info": row.info, "note": row.note}


# ---------------------------------------------------------------- manual rows

class ManualRowBody(BaseModel):
    kind: str
    date: str                       # YYYY-MM-DD or full ISO
    epoch: Optional[int] = None
    why: Optional[str] = None
    info: Optional[str] = None
    note: Optional[str] = None
    eur_rate: Optional[float] = None
    usd_rate: Optional[float] = None
    cells: dict[str, int] = {}      # wallet_id -> delta


@router.post("/balance-history/rows")
async def create_manual_row(body: ManualRowBody, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if body.kind not in bhs.KINDS:
        raise HTTPException(400, "invalid kind")
    if not body.cells:
        raise HTTPException(400, "at least one wallet amount required")

    captured_at = body.date if len(body.date) > 10 else f"{body.date}T12:00:00+00:00"
    try:
        datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "invalid date")

    eur_rate, usd_rate = body.eur_rate, body.usd_rate
    if eur_rate is None or usd_rate is None:
        prices = await get_price_for_date(db, captured_at[:10])
        eur_rate = eur_rate if eur_rate is not None else prices.get("eur")
        usd_rate = usd_rate if usd_rate is not None else prices.get("usd")

    wallets = {
        w.id: w for w in db.query(Wallet).filter(Wallet.id.in_(list(body.cells.keys()))).all()
    }
    bucket = f"u{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    now_iso = now_utc_iso()
    for wallet_id, delta in body.cells.items():
        w = wallets.get(wallet_id)
        db.add(BalanceSnapshot(
            kind=body.kind, bucket=bucket, trigger="user",
            captured_at=captured_at, range_from=None, range_to=captured_at,
            wallet_id=wallet_id,
            label=w.label if w else wallet_id[:8],
            owner=w.owner if w else None,
            balance=None, delta=int(delta),
            epoch=body.epoch, eur_rate=eur_rate, usd_rate=usd_rate,
            source="user", edited=0, created_at=now_iso,
        ))
    if body.why or body.info or body.note:
        db.add(SnapshotAnnotation(
            kind=body.kind, bucket=bucket,
            why=body.why, info=body.info, note=body.note, updated_at=now_iso,
        ))
    db.commit()
    _refresh_exports_after_change(background_tasks, db, body.kind)
    return {"bucket": bucket, "kind": body.kind, "rows": len(body.cells)}


@router.delete("/balance-history/rows")
def delete_row(background_tasks: BackgroundTasks, kind: str = Query(...), bucket: str = Query(...), db: Session = Depends(get_db)):
    rows = (
        db.query(BalanceSnapshot)
        .filter(BalanceSnapshot.kind == kind, BalanceSnapshot.bucket == bucket)
        .all()
    )
    if not rows:
        raise HTTPException(404, "row not found")
    if any(r.trigger != "user" for r in rows):
        raise HTTPException(400, "only manually created rows can be deleted")
    for r in rows:
        db.delete(r)
    ann = (
        db.query(SnapshotAnnotation)
        .filter(SnapshotAnnotation.kind == kind, SnapshotAnnotation.bucket == bucket)
        .first()
    )
    if ann:
        db.delete(ann)
    db.commit()
    _refresh_exports_after_change(background_tasks, db, kind)
    return {"deleted": len(rows)}


@router.delete("/balance-history/series/{kind}")
def reset_series(kind: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Full reset of one series: deletes every capture (incl. manual records
    and annotations) and regenerates that series' Excel file empty."""
    if kind not in bhs.KINDS:
        raise HTTPException(400, "invalid kind")
    deleted = bhs.reset_series(db, kind)
    background_tasks.add_task(write_workbooks, [kind])
    return {"kind": kind, "deleted": deleted}


# ---------------------------------------------------------------- sheet views

@router.get("/balance-history/owner-ledger")
def owner_ledger(
    owner: str = Query(default=""),
    kind: str = Query(default="hourly"),
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Per-owner ledger rows: SC events aggregated per capture slot of the
    series (like the user's manual ledger), TX rows individual with their
    own timestamp — same logic as the Excel sheets (build_owner_rows)."""
    if kind not in bhs.KINDS:
        raise HTTPException(400, "invalid kind")
    q = db.query(Wallet).filter(Wallet.deleted_at.is_(None))
    if owner:
        q = q.filter(Wallet.owner == owner)
    else:
        q = q.filter((Wallet.owner.is_(None)) | (Wallet.owner == ""))
    wallets = q.order_by(Wallet.label).all()
    wallet_dicts = [{"id": w.id, "label": w.label} for w in wallets]

    from ...services.excel_workbook_service import build_owner_rows
    rows = build_owner_rows(db, wallet_dicts, kind)
    rows.reverse()  # newest first for the UI
    page = rows[offset:offset + limit]
    return {
        "owner": owner,
        "kind": kind,
        "wallets": wallet_dicts,
        "total": len(rows),
        "rows": [{
            "type": r["type"],
            "timestamp": r["ts"].isoformat() if r["ts"] else None,
            "epoch": r["epoch"],
            "count": r["count"],
            "cells": r["cells"],
            "eur_rate": r["eur_rate"],
            "usd_rate": r["usd_rate"],
            "is_internal": r["is_internal"],
            "incoming": r["incoming"],
            "comment": r["comment"],
            "note": r["note"],
            "tx_id": r["tx_id"],
        } for r in page],
    }


@router.get("/balance-history/transfers")
def internal_transfers(
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    labels = {w.id: w.label for w in db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()}
    base = db.query(Event).filter(Event.is_internal == 1)
    rows = base.order_by(Event.timestamp.desc(), Event.tick_number.desc()).all()
    seen: set[str] = set()
    unique = []
    for e in rows:
        if e.id in seen:
            continue
        seen.add(e.id)
        unique.append(e)
    page = unique[offset:offset + limit]
    return {
        "total": len(unique),
        "rows": [{
            "id": e.id, "timestamp": e.timestamp, "epoch": e.epoch,
            "amount": e.amount_qubic or 0,
            "source": e.source_address, "destination": e.destination_addr,
            "source_label": labels.get(e.source_address),
            "destination_label": labels.get(e.destination_addr),
            "eur_rate": e.qubic_eur_rate, "usd_rate": e.qubic_usd_rate,
        } for e in page],
    }


@router.get("/balance-history/transactions")
def transactions(
    kind: str = Query(default="hourly"),
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Flat MyLedgerCSV rows: TX individually plus the per-slot events
    residual (balance delta minus TX) — same source as the Excel sheet."""
    if kind not in bhs.KINDS:
        raise HTTPException(400, "invalid kind")
    from ...services.excel_workbook_service import _wallet_columns, build_flat_rows

    columns = _wallet_columns(db, kind)
    owner_of = {c["id"]: c["owner"] for c in columns}
    labels = {c["id"]: c["label"] for c in columns}
    rows = build_flat_rows(db, columns, kind)
    rows.reverse()  # newest first for the UI
    page = rows[offset:offset + limit]
    return {
        "kind": kind,
        "total": len(rows),
        "rows": [{
            "timestamp": r["ts"].isoformat() if r["ts"] else None,
            "epoch": r["epoch"],
            "wallet_id": r["wallet_id"],
            "wallet_label": labels.get(r["wallet_id"]),
            "owner": owner_of.get(r["wallet_id"]),
            "amount": r["amount"],
            "eur_rate": r["eur_rate"], "usd_rate": r["usd_rate"],
            "source_type": "EVENT" if r["is_sc"] else "TX",
            "is_internal": r["is_internal"],
            "comment": r["comment"], "note": r["note"], "id": r["tx_id"] or "",
        } for r in page],
    }


# ---------------------------------------------------------------- export

@router.get("/balance-history/export/{kind}")
def download_export(kind: str, lang: str = Query(default="de"), db: Session = Depends(get_db)):
    if kind not in bhs.KINDS:
        raise HTTPException(400, "invalid kind")
    lang = lang if lang in FILE_NAMES else "de"
    xlsx_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # The auto-exported file on disk is kept current after every capture/edit
    # (atomic writes) — serving it directly avoids rebuilding a large workbook
    # per download. Fall back to an on-the-fly build (auto export off, other
    # language, or file not written yet).
    settings_map = bhs.get_bh_settings(db)
    path = export_file_path(kind, lang)
    if (
        settings_map.get("bh_excel_autoexport", "true") == "true"
        and lang == settings_map.get("bh_export_lang", "de")
        and path.exists()
    ):
        return FileResponse(path, media_type=xlsx_type, filename=path.name)

    data = build_workbook_bytes(db, kind, lang)
    return Response(
        content=data,
        media_type=xlsx_type,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.post("/balance-history/export/rebuild")
async def rebuild_exports():
    import asyncio
    written = await asyncio.to_thread(write_workbooks)
    return {"written": written}
