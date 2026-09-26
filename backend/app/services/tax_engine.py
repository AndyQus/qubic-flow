from collections import deque, defaultdict
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.event import Event
from ..models.opening_position import OpeningPosition
from ..models.qearn import EventSplit

QEARN_ADDRESS = "JAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVKHO"


TAX_RULES = {
    "DE": {"holding_days": 365, "threshold": 1000, "threshold_type": "Freigrenze", "currency": "EUR"},
    "AT": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "EUR"},
    "CH": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "CHF"},
    "DK": {"holding_days": None, "threshold": None, "threshold_type": "Spekulationsbeskatning",
           "currency": "DKK", "forced_method": "FIFO", "separate_losses": True},
    "US": {"holding_days": 365, "threshold": None, "threshold_type": "Short/Long-Term", "currency": "USD"},
    "GB": {"holding_days": 365, "threshold": 3000, "threshold_type": "CGT Allowance", "currency": "GBP"},
    "AU": {"holding_days": 365, "threshold": None, "threshold_type": "50% CGT Discount", "currency": "AUD"},
    "CA": {"holding_days": None, "threshold": None, "threshold_type": "50% Inclusion Rate", "currency": "CAD"},
    "FR": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "EUR"},
    "NL": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "EUR"},
    "IT": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "EUR"},
    "ES": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "EUR"},
    "PT": {"holding_days": 365, "threshold": None, "threshold_type": None, "currency": "EUR"},
    "SE": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "SEK"},
    "NO": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "NOK"},
    "SG": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": "SGD"},
    "OTHER": {"holding_days": None, "threshold": None, "threshold_type": None, "currency": None},
}


def calc_currency(rules: dict) -> str:
    """Currency the report is actually calculated in.

    Only EUR and USD rates are tracked (price_cache). Countries with another
    local currency (CHF, GBP, DKK, …) get an honest EUR report instead of
    EUR numbers silently labelled with the local currency.
    """
    return "USD" if rules.get("currency") == "USD" else "EUR"


def _parse_date(iso: str) -> datetime:
    """Parse ISO date/datetime string. Returns naive datetime (UTC)."""
    if not iso:
        return datetime(1970, 1, 1)
    s = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # fall back to date-only
        try:
            dt = datetime.fromisoformat(iso[:10])
        except ValueError:
            return datetime(1970, 1, 1)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def _price(lot_or_evt: dict, currency: str) -> float:
    if currency == "USD":
        v = lot_or_evt.get("price_usd")
    else:
        v = lot_or_evt.get("price_eur")
    return float(v) if v is not None else 0.0


def _match_lots(
    q: deque,
    amount: int,
    disposal_value_per_qu: float,
    ts: datetime,
    method: str,
    holding_days_threshold,
    mode: str,
    currency: str,
) -> tuple[list, float]:
    """Match disposal against lot queue using the specified cost-basis method."""
    remaining = amount
    total_cost = 0.0
    sub_disposals = []
    m = method.upper()

    if m == "AVCO":
        total_held = sum(l["amount"] for l in q)
        if total_held > 0:
            total_cost_held = sum(l["amount"] * _price(l, currency) for l in q)
            avg_cost_per_qu = total_cost_held / total_held
        else:
            avg_cost_per_qu = 0.0
        cost = remaining * avg_cost_per_qu
        proceeds = remaining * disposal_value_per_qu
        sub_disposals.append({
            "amount_qubic": remaining,
            "acquired_date": None,
            "disposed_date": ts.isoformat(),
            "cost_basis": cost,
            "proceeds": proceeds,
            "gain": proceeds - cost,
            "holding_days": None,
            "tax_free": False,
        })
        total_cost = cost
        # Consume lots proportionally from front (order irrelevant for AVCO)
        rem = remaining
        while rem > 0 and q:
            lot = q[0]
            take = min(rem, lot["amount"])
            lot["amount"] -= take
            rem -= take
            if lot["amount"] <= 0:
                q.popleft()
        return sub_disposals, total_cost

    # FIFO / LIFO / HIFO — lot-based matching
    while remaining > 0 and q:
        if m == "LIFO":
            idx = len(q) - 1
        elif m == "HIFO":
            idx = max(range(len(q)), key=lambda i: _price(q[i], currency))
        else:  # FIFO (default)
            idx = 0

        lot = q[idx]
        take = min(remaining, lot["amount"])
        cost_per_qu = _price(lot, currency)
        cost = take * cost_per_qu
        proceeds = take * disposal_value_per_qu
        gain = proceeds - cost
        holding_days = (ts - lot["date"]).days
        tax_free = (
            holding_days_threshold is not None
            and mode == "private"
            and holding_days >= holding_days_threshold
        )

        sub_disposals.append({
            "amount_qubic": take,
            "acquired_date": lot["date"].isoformat(),
            "disposed_date": ts.isoformat(),
            "cost_basis": cost,
            "proceeds": proceeds,
            "gain": gain,
            "holding_days": holding_days,
            "tax_free": tax_free,
        })

        total_cost += cost
        lot["amount"] -= take
        remaining -= take
        if lot["amount"] <= 0:
            del q[idx]

    # Unmatched remainder (missing history) → zero cost basis
    if remaining > 0:
        proceeds = remaining * disposal_value_per_qu
        sub_disposals.append({
            "amount_qubic": remaining,
            "acquired_date": None,
            "disposed_date": ts.isoformat(),
            "cost_basis": 0.0,
            "proceeds": proceeds,
            "gain": proceeds,
            "holding_days": None,
            "tax_free": False,
        })

    return sub_disposals, total_cost


def _take_lots(q: deque, amount: int) -> list[dict]:
    """Remove `amount` QU from the front of a lot queue, keeping dates and prices."""
    taken, remaining = [], amount
    while remaining > 0 and q:
        lot = q[0]
        take = min(remaining, lot["amount"])
        taken.append({**lot, "amount": take})
        lot["amount"] -= take
        remaining -= take
        if lot["amount"] <= 0:
            q.popleft()
    return taken


def _restore_lots(q: deque, lots: list[dict]) -> None:
    """Put lots back in acquisition order so FIFO/LIFO keep working on the original dates."""
    merged = sorted(list(q) + lots, key=lambda l: l["date"])
    q.clear()
    q.extend(merged)


def _load_splits(db: Session, wallet_ids: list[str]) -> dict:
    out: dict = {}
    for s in db.query(EventSplit).filter(EventSplit.wallet_id.in_(wallet_ids)).all():
        entry = out.setdefault((s.event_id, s.wallet_id), {"meta": {}})
        entry[s.part] = int(s.amount_qubic or 0)
        if not entry["meta"] and s.meta_json:
            import json
            try:
                entry["meta"] = json.loads(s.meta_json)
            except ValueError:
                pass
    return out


def calculate_tax_report(
    db: Session,
    wallet_ids: list[str],
    year: int,
    mode: str,
    country: str,
    method: str,
) -> dict:
    rules = TAX_RULES.get(country, TAX_RULES["OTHER"])
    currency = calc_currency(rules)
    if rules.get("forced_method"):
        method = rules["forced_method"]
    separate_losses = bool(rules.get("separate_losses"))
    holding_days_threshold = rules.get("holding_days")
    threshold = rules.get("threshold")
    threshold_type = rules.get("threshold_type")

    year_start = datetime(year, 1, 1)
    year_end = datetime(year, 12, 31, 23, 59, 59)

    if not wallet_ids:
        return {
            "summary": {
                "taxable_gains_eur": 0.0,
                "tax_free_gains_eur": 0.0,
                "deductible_losses_eur": 0.0 if separate_losses else None,
                "income_eur": 0.0,
                "total_volume_eur": 0.0,
                "transactions_count": 0,
                "threshold": threshold,
                "threshold_exceeded": False,
                "threshold_type": threshold_type,
            },
            "currency": currency,
            "method": method,
            "disposals": [],
            "income": [],
            "year_end_holdings": [],
            "data_warning": "Data tracked from April 1, 2026. Calculations may be incomplete for earlier periods.",
        }

    # 1) Load opening positions sorted by date
    opening = (
        db.query(OpeningPosition)
        .filter(OpeningPosition.wallet_id.in_(wallet_ids))
        .order_by(OpeningPosition.date.asc())
        .all()
    )

    # 2) Load all events for wallets, sorted by timestamp
    events = (
        db.query(Event)
        .filter(Event.wallet_id.in_(wallet_ids))
        .filter(Event.amount_qubic > 0)
        .order_by(Event.timestamp.asc())
        .all()
    )

    wallet_set = set(wallet_ids)
    splits = _load_splits(db, wallet_ids)

    # 3) Build per-wallet FIFO lot queues
    lots: dict[str, deque] = defaultdict(deque)
    # Qearn: QU locked in the contract stay the user's coins (no disposal).
    # Their lots wait here per (wallet, lock epoch) until the principal returns.
    locked: dict[tuple, deque] = defaultdict(deque)
    qearn_unsplit = 0
    for op_ in opening:
        lots[op_.wallet_id].append({
            "date": _parse_date(op_.date),
            "amount": int(op_.amount_qubic),
            "price_eur": float(op_.price_eur) if op_.price_eur is not None else 0.0,
            "price_usd": float(op_.price_usd) if op_.price_usd is not None else 0.0,
        })

    disposals: list[dict] = []
    income: list[dict] = []

    for evt in events:
        if evt.is_internal:
            continue
        amount = int(evt.amount_qubic or 0)
        if amount <= 0:
            continue

        ts = _parse_date(evt.timestamp)
        # Stop at year end: later events must not consume lots, otherwise
        # year_end_holdings would reflect disposals from subsequent years.
        if ts > year_end:
            break
        price_eur = float(evt.qubic_eur_rate) if evt.qubic_eur_rate is not None else 0.0
        price_usd = float(evt.qubic_usd_rate) if evt.qubic_usd_rate is not None else 0.0

        dest_in = evt.destination_addr in wallet_set
        src_in = evt.source_address in wallet_set

        # Qearn lock: coins move into the contract but remain the user's —
        # not a disposal, the lots (dates + cost basis) are parked.
        if src_in and evt.destination_addr == QEARN_ADDRESS:
            locked[(evt.source_address, evt.epoch)].extend(_take_lots(lots[evt.source_address], amount))
            continue

        # Qearn payout: principal returns with its original lots, only the
        # interest is income. Unsplit payouts (check not run yet) keep the
        # previous behaviour and are counted for a warning in the report.
        if dest_in and evt.source_address == QEARN_ADDRESS:
            target_wallet = evt.destination_addr
            split = splits.get((evt.id, evt.wallet_id))
            if evt.sc_kind == "QEARN_REFUND":
                principal, interest, meta = amount, 0, {}
            elif split and "PRINCIPAL" in split:
                principal = min(split["PRINCIPAL"], amount)
                interest = amount - principal
                meta = split["meta"]
            else:
                principal, interest, meta = 0, amount, {}
                qearn_unsplit += 1
            if principal > 0:
                key = (target_wallet, meta.get("lock_epoch"))
                pool = locked[key] if locked.get(key) else next(
                    (q for (w, _e), q in locked.items() if w == target_wallet and q), deque())
                back = _take_lots(pool, principal)
                shortfall = principal - sum(l["amount"] for l in back)
                if shortfall > 0:
                    # lock happened before the tracked history: unknown cost basis
                    back.append({"date": _parse_date(meta.get("lock_ts") or evt.timestamp),
                                 "amount": shortfall, "price_eur": 0.0, "price_usd": 0.0})
                _restore_lots(lots[target_wallet], back)
            if interest > 0:
                lots[target_wallet].append({
                    "date": ts, "amount": interest, "price_eur": price_eur, "price_usd": price_usd,
                })
                if ts.year == year:
                    value = price_eur if currency == "EUR" else price_usd
                    income.append({
                        "date": evt.timestamp,
                        "wallet_id": target_wallet,
                        "amount_qubic": interest,
                        "price_eur": price_eur,
                        "price_usd": price_usd,
                        "value": interest * value,
                        "currency": currency,
                        "source_type": evt.source_type,
                        "tick_number": evt.tick_number,
                        "kind": "qearn_interest" if principal > 0 else None,
                        "lock_epoch": meta.get("lock_epoch"),
                        "principal_qubic": principal or None,
                    })
            continue

        # acquisition (incoming)
        if dest_in and not src_in:
            target_wallet = evt.destination_addr
            if evt.source_type == "TX":
                lots[target_wallet].append({
                    "date": ts,
                    "amount": amount,
                    "price_eur": price_eur,
                    "price_usd": price_usd,
                })
            elif evt.source_type == "EVENT":
                # Income / reward: taxed as income at receipt, so the lot's
                # cost basis is the market value at receipt (not zero) —
                # otherwise the same value would be taxed again on disposal.
                lots[target_wallet].append({
                    "date": ts,
                    "amount": amount,
                    "price_eur": price_eur,
                    "price_usd": price_usd,
                })
                value = price_eur if currency == "EUR" else price_usd
                if ts.year == year:
                    income.append({
                        "date": evt.timestamp,
                        "wallet_id": target_wallet,
                        "amount_qubic": amount,
                        "price_eur": price_eur,
                        "price_usd": price_usd,
                        "value": amount * value,
                        "currency": currency,
                        "source_type": evt.source_type,
                        "tick_number": evt.tick_number,
                    })

        # disposal (outgoing)
        elif src_in and not dest_in:
            source_wallet = evt.source_address
            disposal_value_per_qu = price_eur if currency == "EUR" else price_usd
            total_proceeds = amount * disposal_value_per_qu

            sub_disposals, total_cost = _match_lots(
                q=lots[source_wallet],
                amount=amount,
                disposal_value_per_qu=disposal_value_per_qu,
                ts=ts,
                method=method,
                holding_days_threshold=holding_days_threshold,
                mode=mode,
                currency=currency,
            )

            if ts.year == year:
                disposals.append({
                    "date": evt.timestamp,
                    "wallet_id": source_wallet,
                    "destination_addr": evt.destination_addr,
                    "amount_qubic": amount,
                    "price_eur": price_eur,
                    "price_usd": price_usd,
                    "proceeds": total_proceeds,
                    "cost_basis": total_cost,
                    "gain": total_proceeds - total_cost,
                    "currency": currency,
                    "tick_number": evt.tick_number,
                    "source_type": evt.source_type,
                    "lots": sub_disposals,
                })

    # 5) Summary
    taxable_gains = 0.0
    tax_free_gains = 0.0
    deductible_losses = 0.0
    total_volume = 0.0
    for d in disposals:
        total_volume += d["proceeds"]
        for l in d["lots"]:
            if l["tax_free"]:
                tax_free_gains += l["gain"]
            elif separate_losses and l["gain"] < 0:
                # e.g. Denmark: losses cannot be netted against gains —
                # they are only a (lower-valued) deduction, reported separately.
                deductible_losses += -l["gain"]
            else:
                taxable_gains += l["gain"]

    income_total = sum(i["value"] for i in income)
    threshold_exceeded = bool(threshold is not None and taxable_gains > threshold)

    # year-end holdings: collapse remaining lots per wallet (Qearn-locked QU
    # are still owned and count towards the holdings of their wallet)
    for (wid, _ep), q in locked.items():
        lots[wid].extend(q)
    year_end_holdings = []
    for wid, q in lots.items():
        # only count lots acquired <= year end
        remaining_amount = 0
        cost_basis = 0.0
        for lot in q:
            if lot["date"] > year_end:
                continue
            remaining_amount += lot["amount"]
            cost_per_qu = lot["price_eur"] if currency == "EUR" else lot["price_usd"]
            cost_basis += lot["amount"] * cost_per_qu
        if remaining_amount > 0:
            year_end_holdings.append({
                "wallet_id": wid,
                "amount_qubic": remaining_amount,
                "cost_basis_eur": cost_basis,
            })

    return {
        "summary": {
            "taxable_gains_eur": taxable_gains,
            "tax_free_gains_eur": tax_free_gains,
            "deductible_losses_eur": deductible_losses if separate_losses else None,
            "income_eur": income_total,
            "total_volume_eur": total_volume,
            "transactions_count": len(disposals) + len(income),
            "threshold": threshold,
            "threshold_exceeded": threshold_exceeded,
            "threshold_type": threshold_type,
        },
        "currency": currency,
        "method": method,
        "disposals": disposals,
        "income": income,
        "year_end_holdings": year_end_holdings,
        "qearn_unsplit": qearn_unsplit,
        "data_warning": "Data tracked from April 1, 2026. Calculations may be incomplete for earlier periods.",
    }
