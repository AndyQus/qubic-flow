import json
import logging

import httpx
from sqlalchemy.orm import Session

from ..models.settings import AppSetting
from ..models.wallet import Wallet

logger = logging.getLogger(__name__)

NOTIFY_PREFIX = "notify."

# Supported webhook formats:
#   generic — JSON payload with all event fields
#   discord — {"content": "<text>"} (Discord webhook URL)
#   ntfy    — plain-text body (ntfy.sh topic URL)
DEFAULT_SETTINGS = {
    "enabled": False,
    "webhook_url": "",
    "format": "generic",
    "min_amount": 0,
    "notify_tx": True,     # notify on regular transfers (source_type TX)
    "notify_event": True,  # notify on smart-contract events (source_type EVENT)
}


def get_notify_settings(db: Session) -> dict:
    rows = db.query(AppSetting).filter(AppSetting.key.like(f"{NOTIFY_PREFIX}%")).all()
    result = dict(DEFAULT_SETTINGS)
    for row in rows:
        short = row.key[len(NOTIFY_PREFIX):]
        try:
            result[short] = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            result[short] = row.value
    return result


def save_notify_settings(db: Session, payload: dict) -> dict:
    for k in DEFAULT_SETTINGS:
        if k not in payload:
            continue
        full_key = f"{NOTIFY_PREFIX}{k}"
        row = db.query(AppSetting).filter(AppSetting.key == full_key).first()
        encoded = json.dumps(payload[k])
        if row:
            row.value = encoded
        else:
            db.add(AppSetting(key=full_key, value=encoded))
    db.commit()
    return get_notify_settings(db)


def _short(addr: str | None) -> str:
    return f"{addr[:5]}…{addr[-5:]}" if addr and len(addr) > 12 else (addr or "?")


def _event_kind(ev: dict) -> str:
    return "TX" if ev.get("source_type") == "TX" else "SC EVENT"


def _build_text(ev: dict, wallet_label: str) -> str:
    """Full multi-line message with the event type on the very first line."""
    amount = ev.get("amount_qubic") or 0
    lines = [f"[{_event_kind(ev)}] QubicFlow: +{amount:,} QU → {wallet_label}"]
    rate = ev.get("qubic_eur_rate")
    if rate:
        usd = ev.get("qubic_usd_rate")
        value = f"Value: ≈ {amount * rate:.2f} EUR"
        if usd:
            value += f" / {amount * usd:.2f} USD"
        lines.append(value)
    lines.append(f"From: {ev.get('source_address') or '?'}")
    lines.append(f"To: {ev.get('destination_addr') or '?'}")
    lines.append(f"Wallet: {wallet_label}")
    if ev.get("tick_number") is not None:
        lines.append(f"Tick: {ev['tick_number']}")
    if ev.get("epoch") is not None:
        lines.append(f"Epoch: {ev['epoch']}")
    if ev.get("timestamp"):
        lines.append(f"Time: {ev['timestamp']}")
    if ev.get("id"):
        lines.append(f"TxID: {ev['id']}")
    return "\n".join(lines)


async def _post_webhook(url: str, fmt: str, ev: dict, wallet_label: str):
    try:
        async with httpx.AsyncClient() as client:
            if fmt == "discord":
                await client.post(url, json={"content": _build_text(ev, wallet_label)}, timeout=5)
            elif fmt == "ntfy":
                await client.post(
                    url,
                    content=_build_text(ev, wallet_label).encode("utf-8"),
                    headers={"Title": f"QubicFlow [{_event_kind(ev)}]", "Tags": "moneybag"},
                    timeout=5,
                )
            else:  # generic JSON — event type first, then the full record
                await client.post(url, json={
                    "event_type": _event_kind(ev).replace(" ", "_"),  # TX | SC_EVENT
                    "type": "qubicflow.incoming",
                    "wallet_label": wallet_label,
                    **ev,
                }, timeout=5)
    except Exception as e:
        # Notifications are best-effort — never break the sync because of them.
        logger.warning(f"Webhook notification failed: {e}")


async def notify_incoming(db: Session, events: list[dict]):
    """Send a webhook notification for each new incoming (non-internal) transfer."""
    cfg = get_notify_settings(db)
    if not cfg.get("enabled") or not cfg.get("webhook_url"):
        return
    try:
        min_amount = int(cfg.get("min_amount") or 0)
    except (TypeError, ValueError):
        min_amount = 0

    labels = {w.id: w.label for w in db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()}
    for ev in events:
        if ev.get("is_internal"):
            continue
        if ev.get("destination_addr") != ev.get("wallet_id"):
            continue  # only incoming transfers
        # Type filter: user chooses whether TX and/or SC events trigger a push
        src_type = ev.get("source_type")
        if src_type == "TX" and not cfg.get("notify_tx", True):
            continue
        if src_type == "EVENT" and not cfg.get("notify_event", True):
            continue
        if (ev.get("amount_qubic") or 0) < min_amount:
            continue
        wallet_label = labels.get(ev.get("wallet_id"), _short(ev.get("wallet_id")))
        await _post_webhook(cfg["webhook_url"], cfg.get("format") or "generic", ev, wallet_label)


async def send_test_notification(db: Session) -> bool:
    """Send a test message to the configured webhook. Returns True on success."""
    cfg = get_notify_settings(db)
    url = cfg.get("webhook_url")
    if not url:
        return False
    ev = {
        "id": "test-notification",
        "wallet_id": "TEST",
        "amount_qubic": 1_000_000,
        "source_address": "QUBICFLOWTESTNOTIFICATION",
        "destination_addr": "TEST",
        "tick_number": 0,
        "epoch": None,
        "timestamp": None,
        "qubic_eur_rate": None,
        "qubic_usd_rate": None,
        "source_type": "TX",
        "is_internal": 0,
    }
    try:
        await _post_webhook(url, cfg.get("format") or "generic", ev, "Test wallet")
        return True
    except Exception:
        return False
