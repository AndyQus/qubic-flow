import csv
import io
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from ..models.event import Event
from ..models.wallet import Wallet
from .label_service import get_label

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

    for e in events:
        kind = _classify(e, owned)
        amount = e.amount_qubic or 0
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

        if kind == "QUBIC_IN":
            row = ["Deposit", amount, "QUBIC", "", "", "", "", exchange, "", comment, _fmt_date(e.timestamp), e.id, value_eur, ""]
        elif kind == "QUBIC_OUT":
            row = ["Withdrawal", "", "", amount, "QUBIC", "", "", exchange, "", comment, _fmt_date(e.timestamp), e.id, "", value_eur]
        else:
            continue

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

    for e in events:
        kind = _classify(e, owned)
        amount = e.amount_qubic or 0
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
        bemerkung = " | ".join(filter(None, [e.comment or "", addr_note])) if addr_note else e.comment or ""

        writer.writerow([
            _fmt_date(e.timestamp), kind, amount, rate, value,
            label, e.source_address or "", e.destination_addr or "",
            e.id, bemerkung,
        ])

    return buf.getvalue()
