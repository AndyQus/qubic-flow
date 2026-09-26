import csv
import io
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from ..models.event import Event
from ..models.qearn import EventSplit
from ..models.wallet import Wallet
from .label_service import get_label
from .qearn_service import QEARN_ADDRESS

logger = logging.getLogger(__name__)

COINTRACKING_HEADER = [
    "Type", "Buy Amount", "Buy Currency", "Sell Amount", "Sell Currency",
    "Fee", "Fee Currency", "Exchange", "Trade-Group", "Comment", "Date",
    "Tx-ID", "Buy Value in Account Currency", "Sell Value in Account Currency",
]

STEUERBERATER_HEADER = [
    "Datum", "Typ", "Betrag QUBIC", "Kurs EUR", "Wert EUR",
    "Wallet-Label", "Quell-Adresse", "Ziel-Adresse", "TX-ID", "Bemerkung",
]


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return iso or ""


def _is_internal(event: Event, owned: set) -> bool:
    """Recompute dynamically against current owned wallets.

    Why: the stored `is_internal` flag reflects ownership at sync time.
    Adding a wallet after-the-fact must re-classify historical transfers
    between now-owned addresses as internal (tax-neutral).
    """
    return event.source_address in owned and event.destination_addr in owned


def _classify(event: Event, owned: set) -> str:
    if _is_internal(event, owned):
        return "INTERNAL"
    if event.destination_addr in owned:
        return "QUBIC_IN"
    if event.source_address in owned:
        return "QUBIC_OUT"
    return "UNKNOWN"


# Qearn row roles: a lock is no disposal and the principal of a payout no
# income (both are the user's own coins moving in/out of the contract) — only
# the interest is a reward.
QEARN_LOCK = "QEARN_LOCK"
QEARN_PRINCIPAL = "QEARN_PRINCIPAL"
QEARN_INTEREST = "QEARN_INTEREST"


def _expand_qearn(db: Session, events: list):
    """Yield (event, amount, qearn_role, meta) — Qearn payouts become principal + interest rows."""
    import json
    ids = [e.id for e in events if e.sc_kind == "QEARN_PAYOUT"]
    splits: dict = {}
    if ids:
        for sp in db.query(EventSplit).filter(EventSplit.event_id.in_(ids)).all():
            entry = splits.setdefault((sp.event_id, sp.wallet_id), {})
            entry[sp.part] = int(sp.amount_qubic or 0)
            entry.setdefault("meta", json.loads(sp.meta_json or "{}"))
    for e in events:
        amount = e.amount_qubic or 0
        if e.destination_addr == QEARN_ADDRESS and e.source_address == e.wallet_id:
            yield e, amount, QEARN_LOCK, {}
        elif e.source_address == QEARN_ADDRESS and e.destination_addr == e.wallet_id:
            split = splits.get((e.id, e.wallet_id))
            if e.sc_kind == "QEARN_REFUND":
                yield e, amount, QEARN_PRINCIPAL, {}
            elif split and "PRINCIPAL" in split:
                yield e, split["PRINCIPAL"], QEARN_PRINCIPAL, split["meta"]
                if split.get("INTEREST", 0) > 0:
                    yield e, split["INTEREST"], QEARN_INTEREST, split["meta"]
            else:
                yield e, amount, None, {}
        else:
            yield e, amount, None, {}


def _qearn_note(role: str | None, meta: dict, lang: str = "en") -> str:
    """Comment text; German only for the (German-language) tax advisor CSV."""
    lock_ep, pay_ep = meta.get("lock_epoch"), meta.get("payout_epoch")
    de = lang == "de"
    if role == QEARN_LOCK:
        return "Qearn Lock (kein Verkauf)" if de else "Qearn lock (not a sale)"
    if role == QEARN_PRINCIPAL:
        if lock_ep:
            return f"Qearn Rückzahlung Einsatz (Lock Ep. {lock_ep})" if de else f"Qearn principal returned (lock ep. {lock_ep})"
        return "Qearn Rückerstattung Einsatz" if de else "Qearn principal refunded"
    if role == QEARN_INTEREST:
        est = (" – geschätzt" if de else " – estimated") if meta.get("estimated") else ""
        return f"Qearn {'Zins' if de else 'interest'} Ep. {lock_ep}–{pay_ep}{est}"
    return ""


def _fmt_rate(rate) -> str:
    """Format rate with up to 10 decimal places, no scientific notation.
    e.g. 6.482e-7 -> '0.0000006482'
    """
    if not rate:
        return ""
    return f"{float(rate):.10f}".rstrip("0").rstrip(".")


def _eur_value(amount: int, rate) -> str:
    if not rate:
        return ""
    return f"{round(amount * float(rate), 2):.2f}"


def export_cointracking(db: Session, year: int | None = None) -> str:
    q = db.query(Event).join(Wallet, Wallet.id == Event.wallet_id).filter(
        Wallet.wallet_type == "PRIVATE",
        Wallet.deleted_at.is_(None),
    )
    if year:
        q = q.filter(Event.timestamp.like(f"{year}-%"))

    events = q.order_by(Event.timestamp).all()
    owned = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}
    labels = {w.id: w.label for w in db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()}

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_ALL)
    writer.writerow(COINTRACKING_HEADER)

    for e, amount, role, meta in _expand_qearn(db, events):
        kind = _classify(e, owned)
        if role in (QEARN_LOCK, QEARN_PRINCIPAL):
            continue  # own coins in/out of the contract — neither disposal nor income
        value_eur = _eur_value(amount, e.qubic_eur_rate)
        exchange = labels.get(e.wallet_id, e.wallet_id or "")

        src_name = get_label(db, e.source_address)
        dst_name = get_label(db, e.destination_addr)
        if src_name and dst_name:
            comment = f"{src_name} \u2192 {dst_name}"
        elif src_name:
            comment = f"{src_name} \u2192"
        elif dst_name:
            comment = f"\u2192 {dst_name}"
        else:
            comment = ""

        if role == QEARN_INTEREST:
            comment = " | ".join(filter(None, [_qearn_note(role, meta), comment]))
            row = ["Staking", amount, "QUBIC", "", "", "", "", exchange, "", comment, _fmt_date(e.timestamp), e.id, value_eur, ""]
        elif kind == "QUBIC_IN":
            row = ["Deposit", amount, "QUBIC", "", "", "", "", exchange, "", comment, _fmt_date(e.timestamp), e.id, value_eur, ""]
        elif kind == "QUBIC_OUT":
            row = ["Withdrawal", "", "", amount, "QUBIC", "", "", exchange, "", comment, _fmt_date(e.timestamp), e.id, "", value_eur]
        else:
            continue

        writer.writerow(row)

    return buf.getvalue()


KOINLY_HEADER = [
    "Date", "Sent Amount", "Sent Currency", "Received Amount", "Received Currency",
    "Fee Amount", "Fee Currency", "Net Worth Amount", "Net Worth Currency",
    "Label", "Description", "TxHash",
]

BLOCKPIT_HEADER = [
    "Date (UTC)", "Integration Name", "Label", "Outgoing Asset", "Outgoing Amount",
    "Incoming Asset", "Incoming Amount", "Fee Asset (optional)", "Fee Amount (optional)",
    "Comment (optional)", "Trx. ID (optional)",
]


def _private_events(db: Session, year: int | None):
    """Shared query + context for the consumer tax-tool exports (PRIVATE wallets)."""
    q = db.query(Event).join(Wallet, Wallet.id == Event.wallet_id).filter(
        Wallet.wallet_type == "PRIVATE",
        Wallet.deleted_at.is_(None),
    )
    if year:
        q = q.filter(Event.timestamp.like(f"{year}-%"))
    events = q.order_by(Event.timestamp).all()
    owned = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}
    return events, owned


def _addr_comment(db: Session, e: Event) -> str:
    src_name = get_label(db, e.source_address)
    dst_name = get_label(db, e.destination_addr)
    if src_name and dst_name:
        return f"{src_name} → {dst_name}"
    if src_name:
        return f"{src_name} →"
    if dst_name:
        return f"→ {dst_name}"
    return ""


def _fmt_date_utc(iso: str, fmt: str) -> str:
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00")).strftime(fmt)
    except Exception:
        return iso or ""


def export_koinly(db: Session, year: int | None = None) -> str:
    """Koinly universal CSV (PRIVATE wallets, internal transfers excluded)."""
    events, owned = _private_events(db, year)

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_ALL)
    writer.writerow(KOINLY_HEADER)

    for e, amount, role, meta in _expand_qearn(db, events):
        kind = _classify(e, owned)
        if kind not in ("QUBIC_IN", "QUBIC_OUT") or role in (QEARN_LOCK, QEARN_PRINCIPAL):
            continue
        date = _fmt_date_utc(e.timestamp, "%Y-%m-%d %H:%M UTC")
        net_worth = _eur_value(amount, e.qubic_eur_rate)
        label = "reward" if (kind == "QUBIC_IN" and e.source_type == "EVENT") else ""
        desc = " | ".join(filter(None, [_qearn_note(role, meta), _addr_comment(db, e)]))

        if kind == "QUBIC_IN":
            row = [date, "", "", amount, "QUBIC", "", "", net_worth, "EUR", label, desc, e.id]
        else:
            row = [date, amount, "QUBIC", "", "", "", "", net_worth, "EUR", label, desc, e.id]
        writer.writerow(row)

    return buf.getvalue()


def export_blockpit(db: Session, year: int | None = None) -> str:
    """Blockpit generic import CSV (PRIVATE wallets, internal transfers excluded)."""
    events, owned = _private_events(db, year)

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_ALL)
    writer.writerow(BLOCKPIT_HEADER)

    for e, amount, role, meta in _expand_qearn(db, events):
        kind = _classify(e, owned)
        if kind not in ("QUBIC_IN", "QUBIC_OUT") or role in (QEARN_LOCK, QEARN_PRINCIPAL):
            continue
        date = _fmt_date_utc(e.timestamp, "%Y-%m-%d %H:%M:%S")
        desc = " | ".join(filter(None, [_qearn_note(role, meta), _addr_comment(db, e)]))

        if kind == "QUBIC_IN":
            label = "Staking" if e.source_type == "EVENT" else "Deposit"
            row = [date, "QubicFlow", label, "", "", "QUBIC", amount, "", "", desc, e.id]
        else:
            row = [date, "QubicFlow", "Withdrawal", "QUBIC", amount, "", "", "", "", desc, e.id]
        writer.writerow(row)

    return buf.getvalue()


def export_steuerberater(db: Session, year: int | None = None) -> str:
    q = db.query(Event).join(Wallet, Wallet.id == Event.wallet_id).filter(
        Wallet.wallet_type == "BUSINESS",
        Wallet.deleted_at.is_(None),
    )
    if year:
        q = q.filter(Event.timestamp.like(f"{year}-%"))

    events = q.order_by(Event.timestamp).all()
    owned = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}
    labels = {w.id: w.label for w in db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()}

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    writer.writerow(STEUERBERATER_HEADER)

    for e, amount, role, meta in _expand_qearn(db, events):
        kind = _classify(e, owned)
        if role == QEARN_LOCK:
            kind = "QEARN_LOCK"
        elif role == QEARN_PRINCIPAL:
            kind = "QEARN_EINSATZ"
        elif role == QEARN_INTEREST:
            kind = "QEARN_ZINS"
        rate = _fmt_rate(e.qubic_eur_rate)
        value = _eur_value(amount, e.qubic_eur_rate)
        label = labels.get(e.wallet_id, "")

        src_name = get_label(db, e.source_address)
        dst_name = get_label(db, e.destination_addr)
        if src_name and dst_name:
            addr_note = f"{src_name} \u2192 {dst_name}"
        elif src_name:
            addr_note = f"{src_name} \u2192"
        elif dst_name:
            addr_note = f"\u2192 {dst_name}"
        else:
            addr_note = ""
        bemerkung = " | ".join(filter(None, [_qearn_note(role, meta, "de"), e.comment or "", addr_note]))

        writer.writerow([
            _fmt_date(e.timestamp), kind, amount, rate, value,
            label, e.source_address or "", e.destination_addr or "",
            e.id, bemerkung,
        ])

    return buf.getvalue()
