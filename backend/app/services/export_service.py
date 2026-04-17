import csv
import io
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from ..models.event import Event
from ..models.wallet import Wallet

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


def _classify(event: Event, owned: set) -> str:
    if event.is_internal:
        return "INTERNAL"
    if event.destination_addr in owned:
        return "QUBIC_IN"
    if event.source_address in owned:
        return "QUBIC_OUT"
    return "UNKNOWN"


def export_cointracking(db: Session, year: int | None = None) -> str:
    q = db.query(Event).join(Wallet, Wallet.id == Event.wallet_id).filter(
        Wallet.wallet_type == "PRIVATE",
        Wallet.deleted_at.is_(None),
        Event.is_internal == 0,
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
        value_eur = (amount * e.qubic_eur_rate) if e.qubic_eur_rate else ""
        exchange = labels.get(e.wallet_id, e.wallet_id or "")

        if kind == "QUBIC_IN":
            row = ["Deposit", amount, "QUBIC", "", "", "", "", exchange, "", "", _fmt_date(e.timestamp), e.id, value_eur, ""]
        elif kind == "QUBIC_OUT":
            row = ["Withdrawal", "", "", amount, "QUBIC", "", "", exchange, "", "", _fmt_date(e.timestamp), e.id, "", value_eur]
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
        rate = e.qubic_eur_rate or 0
        value = amount * rate if rate else ""
        label = labels.get(e.wallet_id, "")

        writer.writerow([
            _fmt_date(e.timestamp), kind, amount, rate, value,
            label, e.source_address or "", e.destination_addr or "",
            e.id, e.comment or "",
        ])

    return buf.getvalue()
