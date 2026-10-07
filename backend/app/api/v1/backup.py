import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...services.balance_service import check_all_balances
from ...models.event import Event
from ...models.qearn import EventSplit, QearnPosition
from ...models.node import Node
from ...models.opening_position import OpeningPosition
from ...models.settings import AppSetting
from ...models.wallet import Wallet
from ...utils.time import now_utc_iso

router = APIRouter()

TAX_PREFIX = "tax."

_bearer = HTTPBearer(auto_error=False)


def _require_backup_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    if not settings.app_password:
        return  # No password set → open access (dev mode; Umbrel proxy handles auth)
    if credentials is None or credentials.credentials != settings.app_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def _row(obj) -> dict:
    return {c.key: getattr(obj, c.key) for c in sa_inspect(obj).mapper.column_attrs}


@router.get("/backup")
def export_backup(
    db: Session = Depends(get_db),
):
    wallets = [_row(w) for w in db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()]
    nodes = [_row(n) for n in db.query(Node).all()]
    opening_positions = [_row(p) for p in db.query(OpeningPosition).all()]
    events = [_row(e) for e in db.query(Event).all()]
    event_splits = [_row(s) for s in db.query(EventSplit).all()]
    qearn_positions = [_row(p) for p in db.query(QearnPosition).all()]

    settings_rows = db.query(AppSetting).filter(AppSetting.key.like(f"{TAX_PREFIX}%")).all()
    tax_settings: dict[str, Any] = {}
    for row in settings_rows:
        short = row.key[len(TAX_PREFIX):]
        try:
            tax_settings[short] = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            tax_settings[short] = row.value

    return {
        "version": 1,
        "exported_at": now_utc_iso(),
        "wallets": wallets,
        "nodes": nodes,
        "opening_positions": opening_positions,
        "tax_settings": tax_settings,
        "events": events,
        "event_splits": event_splits,
        "qearn_positions": qearn_positions,
    }


@router.post("/backup/restore")
def restore_backup(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    stats: dict[str, Any] = {}

    # --- Wallets ---
    existing_wallet_ids = {w.id for w in db.query(Wallet.id).all()}
    wc = {"created": 0, "skipped": 0, "failed": 0}
    for w in payload.get("wallets", []):
        if w.get("id") in existing_wallet_ids:
            wc["skipped"] += 1
            continue
        try:
            db.add(Wallet(
                id=w["id"],
                label=w.get("label", ""),
                note=w.get("note"),
                wallet_type=w.get("wallet_type", "PRIVATE"),
                active=w.get("active", 1),
                created_at=w.get("created_at") or now_utc_iso(),
                updated_at=w.get("updated_at"),
                owner=w.get("owner"),
                function=w.get("function"),
            ))
            db.flush()
            existing_wallet_ids.add(w["id"])
            wc["created"] += 1
        except Exception:
            db.rollback()
            wc["failed"] += 1
    db.commit()
    stats["wallets"] = wc

    # --- Nodes (unique by url) ---
    existing_urls = {n.url for n in db.query(Node.url).all()}
    nc = {"created": 0, "skipped": 0, "failed": 0}
    for n in payload.get("nodes", []):
        if n.get("url") in existing_urls:
            nc["skipped"] += 1
            continue
        try:
            db.add(Node(
                url=n["url"],
                node_type=n.get("node_type", "BOB"),
                label=n.get("label"),
                priority=n.get("priority", 1),
                is_active=n.get("is_active", 1),
            ))
            db.flush()
            existing_urls.add(n["url"])
            nc["created"] += 1
        except Exception:
            db.rollback()
            nc["failed"] += 1
    db.commit()
    stats["nodes"] = nc

    # --- Opening positions ---
    existing_positions = {
        (p.wallet_id, p.date, p.amount_qubic)
        for p in db.query(OpeningPosition.wallet_id, OpeningPosition.date, OpeningPosition.amount_qubic).all()
    }
    pc = {"created": 0, "skipped": 0, "failed": 0}
    for p in payload.get("opening_positions", []):
        key = (p.get("wallet_id"), p.get("date"), p.get("amount_qubic"))
        if key in existing_positions:
            pc["skipped"] += 1
            continue
        try:
            db.add(OpeningPosition(
                wallet_id=p["wallet_id"],
                date=p["date"],
                amount_qubic=p["amount_qubic"],
                price_eur=p.get("price_eur"),
                price_usd=p.get("price_usd"),
                note=p.get("note"),
                created_at=p.get("created_at") or now_utc_iso(),
            ))
            db.flush()
            existing_positions.add(key)
            pc["created"] += 1
        except Exception:
            db.rollback()
            pc["failed"] += 1
    db.commit()
    stats["opening_positions"] = pc

    # --- Events (INSERT OR IGNORE on composite PK: id + wallet_id) ---
    events_data = payload.get("events", [])
    ec = {"created": 0, "skipped": 0, "failed": 0}
    if events_data:
        before = db.query(Event).count()
        try:
            stmt = text("""
                INSERT OR IGNORE INTO events
                (id, wallet_id, epoch, tick_number, timestamp_raw, timestamp, log_type,
                 log_digest, categories, source_address, destination_addr, is_internal,
                 amount_qubic, qubic_eur_rate, qubic_usd_rate, qubic_eur_rate_hourly, qubic_usd_rate_hourly, buy_value_eur, buy_value_usd,
                 sell_value_eur, sell_value_usd, source_type, buy_currency, sell_currency,
                 item_id, item_name, comment, trade_group, verified, created_at,
                 note, sc_kind, reconstructed)
                VALUES
                (:id, :wallet_id, :epoch, :tick_number, :timestamp_raw, :timestamp, :log_type,
                 :log_digest, :categories, :source_address, :destination_addr, :is_internal,
                 :amount_qubic, :qubic_eur_rate, :qubic_usd_rate, :qubic_eur_rate_hourly, :qubic_usd_rate_hourly, :buy_value_eur, :buy_value_usd,
                 :sell_value_eur, :sell_value_usd, :source_type, :buy_currency, :sell_currency,
                 :item_id, :item_name, :comment, :trade_group, :verified, :created_at,
                 :note, :sc_kind, :reconstructed)
            """)
            batch_size = 500
            for i in range(0, len(events_data), batch_size):
                batch = events_data[i:i + batch_size]
                params = [{
                    "id": e.get("id"), "wallet_id": e.get("wallet_id"),
                    "epoch": e.get("epoch"), "tick_number": e.get("tick_number"),
                    "timestamp_raw": e.get("timestamp_raw"), "timestamp": e.get("timestamp"),
                    "log_type": e.get("log_type"), "log_digest": e.get("log_digest"),
                    "categories": e.get("categories"), "source_address": e.get("source_address"),
                    "destination_addr": e.get("destination_addr"), "is_internal": e.get("is_internal", 0),
                    "amount_qubic": e.get("amount_qubic"), "qubic_eur_rate": e.get("qubic_eur_rate"),
                    "qubic_usd_rate": e.get("qubic_usd_rate"),
                    "qubic_eur_rate_hourly": e.get("qubic_eur_rate_hourly"),
                    "qubic_usd_rate_hourly": e.get("qubic_usd_rate_hourly"), "buy_value_eur": e.get("buy_value_eur"),
                    "buy_value_usd": e.get("buy_value_usd"), "sell_value_eur": e.get("sell_value_eur"),
                    "sell_value_usd": e.get("sell_value_usd"), "source_type": e.get("source_type"),
                    "buy_currency": e.get("buy_currency"), "sell_currency": e.get("sell_currency"),
                    "item_id": e.get("item_id"), "item_name": e.get("item_name"),
                    "comment": e.get("comment"), "trade_group": e.get("trade_group"),
                    "verified": e.get("verified", 0), "created_at": e.get("created_at"),
                    "note": e.get("note"), "sc_kind": e.get("sc_kind"),
                    "reconstructed": e.get("reconstructed") or 0,
                } for e in batch]
                db.execute(stmt, params)
                db.commit()
            after = db.query(Event).count()
            ec["created"] = after - before
            ec["skipped"] = len(events_data) - ec["created"]
        except Exception as ex:
            db.rollback()
            ec["failed"] = len(events_data)
    stats["events"] = ec

    # --- Qearn principal/interest splits (INSERT OR IGNORE on event+wallet+part) ---
    splits_data = payload.get("event_splits", [])
    sc = {"created": 0, "skipped": 0, "failed": 0}
    if splits_data:
        try:
            before = db.query(EventSplit).count()
            db.execute(text("""
                INSERT OR IGNORE INTO event_splits
                (event_id, wallet_id, part, amount_qubic, estimated, meta_json, updated_at)
                VALUES (:event_id, :wallet_id, :part, :amount_qubic, :estimated, :meta_json, :updated_at)
            """), [{
                "event_id": sp.get("event_id"), "wallet_id": sp.get("wallet_id"), "part": sp.get("part"),
                "amount_qubic": sp.get("amount_qubic") or 0, "estimated": sp.get("estimated") or 0,
                "meta_json": sp.get("meta_json"), "updated_at": sp.get("updated_at"),
            } for sp in splits_data])
            db.commit()
            sc["created"] = db.query(EventSplit).count() - before
            sc["skipped"] = len(splits_data) - sc["created"]
        except Exception:
            db.rollback()
            sc["failed"] = len(splits_data)
    stats["event_splits"] = sc

    # --- Qearn positions (overview only; recomputed by every Qearn check) ---
    positions_data = payload.get("qearn_positions", [])
    if positions_data:
        try:
            db.execute(text("""
                INSERT OR IGNORE INTO qearn_positions
                (wallet_id, lock_epoch, principal_qu, early_unlocked_qu, end_epoch, yield_e7,
                 expected_payout_qu, payout_qu, interest_qu, status, detail_json, checked_at)
                VALUES (:wallet_id, :lock_epoch, :principal_qu, :early_unlocked_qu, :end_epoch, :yield_e7,
                 :expected_payout_qu, :payout_qu, :interest_qu, :status, :detail_json, :checked_at)
            """), [{k: p.get(k) for k in (
                "wallet_id", "lock_epoch", "principal_qu", "early_unlocked_qu", "end_epoch", "yield_e7",
                "expected_payout_qu", "payout_qu", "interest_qu", "status", "detail_json", "checked_at",
            )} for p in positions_data])
            db.commit()
            stats["qearn_positions"] = "restored"
        except Exception:
            db.rollback()
            stats["qearn_positions"] = "failed"

    # --- Tax settings (overwrite) ---
    if "tax_settings" in payload:
        for k, v in payload["tax_settings"].items():
            full_key = f"{TAX_PREFIX}{k}"
            row = db.query(AppSetting).filter(AppSetting.key == full_key).first()
            encoded = json.dumps(v)
            if row:
                row.value = encoded
            else:
                db.add(AppSetting(key=full_key, value=encoded))
        db.commit()
        stats["tax_settings"] = "restored"

    background_tasks.add_task(check_all_balances)
    return stats
