"""Qearn: principal/interest split of payouts and the manual "Qearn check".

How Qearn works (verified against qubic/core src/contracts/Qearn.h):
  * lock   — TX wallet → Qearn, inputType 1, amount = principal. All locks of
             one wallet within one epoch are merged into one position.
  * payout — END_EPOCH of epoch E pays every position locked in E-52 with ONE
             transfer Qearn → wallet: principal + floor(principal*yield/1e7).
  * unlock — TX wallet → Qearn, inputType 2, amount 0, input = amount(u64) +
             lockedEpoch(u32). In the same tick the contract transfers
             amount + reduced reward (0–55 % of the reward) back.
  * getLockInfoPerEpoch (function 1) still returns the yield of long-ended
             rounds, so every regular payout can be split exactly.

The public event archive misses the END_EPOCH payout batches of several
epochs (e.g. 208–210, 212) and has no data before ~epoch 207. Such payouts are
computed ("reconstructed") and only written after the user confirmed them.

Layering: the pure `compute_analysis()` does all matching; `analyze_wallet()`
gathers the inputs (DB, archiver, contract) and `apply_analysis()` persists.
"""
import asyncio
import base64
import json
import logging
import struct
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.event import Event
from ..models.qearn import EventSplit, QearnEpoch, QearnPosition
from ..models.wallet import Wallet
from ..utils.log_buffer import log_buffer
from ..utils.time import iso_to_date, now_utc_iso, unix_ms_to_iso
from .qubic_client import RPCClient

logger = logging.getLogger(__name__)

QEARN_ADDRESS = "JAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVKHO"
QEARN_CONTRACT_INDEX = 9
LOCK_EPOCHS = 52
MIN_LOCK_AMOUNT = 10_000_000
YIELD_SCALE = 10_000_000

# (min locked weeks, max locked weeks, reward percent) — QEARN_EARLY_UNLOCKING_PERCENT_*
_EARLY_UNLOCK_PERCENT = (
    (4, 7, 5), (8, 11, 5), (12, 15, 10), (16, 19, 15), (20, 23, 20), (24, 27, 25),
    (28, 31, 30), (32, 35, 35), (36, 39, 40), (40, 43, 45), (44, 47, 50), (48, 51, 55),
)

# Epoch transitions happen Wednesdays 12:00 UTC; epoch 213 ended 2026-05-20.
# Only used as fallback timestamp when the archiver cannot resolve a tick.
_EPOCH_END_ANCHOR = (213, datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc))

KIND_LOCK = "QEARN_LOCK"
KIND_PAYOUT = "QEARN_PAYOUT"
KIND_REFUND = "QEARN_REFUND"

PART_PRINCIPAL = "PRINCIPAL"
PART_INTEREST = "INTEREST"


# ─────────────────────────────── pure helpers ───────────────────────────────

def decode_unlock_input(input_b64: str | None) -> tuple[int, int] | None:
    """unlock_input = {uint64 amount; uint32 lockedEpoch} (little endian)."""
    if not input_b64:
        return None
    try:
        raw = base64.b64decode(input_b64)
    except Exception:
        return None
    if len(raw) < 12:
        return None
    amount, locked_epoch = struct.unpack_from("<QI", raw)
    return amount, locked_epoch


def early_unlock_percent(unlock_epoch: int, lock_epoch: int) -> int:
    """Reward share of an early unlock. countOfLockedEpochs = epoch - lockedEpoch - 1
    (uint32 in the contract: an unlock in the lock epoch wraps around → 0 %)."""
    weeks = unlock_epoch - lock_epoch - 1
    for lo, hi, pct in _EARLY_UNLOCK_PERCENT:
        if lo <= weeks <= hi:
            return pct
    return 0


def full_reward(principal: int, yield_e7: int) -> int:
    return principal * yield_e7 // YIELD_SCALE


def early_reward(amount: int, reward_percent_e7: int, pct: int) -> int:
    div_calcu = reward_percent_e7 * amount // 100
    return div_calcu * pct // YIELD_SCALE


def derive_principal(payout: int, yield_e7: int) -> int | None:
    """Invert payout = P + floor(P*y/1e7) (strictly increasing in P, so the
    preimage is unique). None when no integer P reproduces the payout."""
    if payout <= 0 or yield_e7 is None or yield_e7 < 0:
        return None
    p0 = payout * YIELD_SCALE // (YIELD_SCALE + yield_e7)
    for p in range(max(1, p0 - 3), p0 + 4):
        if p + full_reward(p, yield_e7) == payout:
            return p
    return None


def epoch_end_fallback_iso(epoch: int) -> str:
    anchor_epoch, anchor_dt = _EPOCH_END_ANCHOR
    dt = anchor_dt + timedelta(days=7 * (epoch - anchor_epoch)) - timedelta(seconds=1)
    return dt.isoformat().replace("+00:00", "Z")


class EpochMap:
    """Tick ↔ epoch mapping built from the archiver's /v1/status."""

    def __init__(self, intervals: dict[int, tuple[int, int]], current_epoch: int):
        self._intervals = intervals            # epoch -> (first tick, last tick)
        self._starts = sorted((first, ep) for ep, (first, _last) in intervals.items())
        self.current_epoch = current_epoch

    @classmethod
    def from_status(cls, status: dict) -> "EpochMap":
        intervals: dict[int, tuple[int, int]] = {}
        for item in status.get("processedTickIntervalsPerEpoch") or []:
            ep = int(item["epoch"])
            ticks = [(int(i["initialProcessedTick"]), int(i["lastProcessedTick"])) for i in item.get("intervals") or []]
            if ticks:
                intervals[ep] = (min(t[0] for t in ticks), max(t[1] for t in ticks))
        last = status.get("lastProcessedTick") or {}
        current = int(last.get("epoch") or (max(intervals) if intervals else 0))
        return cls(intervals, current)

    def epoch_of_tick(self, tick: int | None) -> int | None:
        if tick is None or not self._starts:
            return None
        found = None
        for first, ep in self._starts:
            if first <= tick:
                found = ep
            else:
                break
        return found

    def last_tick(self, epoch: int) -> int | None:
        iv = self._intervals.get(epoch)
        return iv[1] if iv else None


def _new_position(lock_epoch: int) -> dict:
    return {
        "lock_epoch": lock_epoch,
        "end_epoch": lock_epoch + LOCK_EPOCHS,
        "principal": 0,
        "early_unlocked": 0,
        "lock_txs": [],
        "lock_ts": None,
        "early": [],
        "status": None,
        "expected_payout": None,
        "payout": None,
        "interest": None,
        "yield_e7": None,
        "payout_event_id": None,
        "derived": False,
    }


def compute_analysis(
    wallet_id: str,
    txs: list[dict],
    payouts: list[dict],
    yields: dict[int, int | None],
    emap: EpochMap,
) -> dict:
    """Match locks, unlocks and payouts of one wallet.

    txs:     wallet → Qearn transactions {hash, tick, ts, amount, input_type, input_b64}
    payouts: Qearn → wallet transfers {event_id, tick, epoch, amount, timestamp,
             reconstructed, origin ('db'|'archive'), override}
    yields:  lock epoch → yield (×1e7) from getLockInfoPerEpoch, None if unknown

    Returns positions, splits (per payout event id), classification, candidates
    for reconstruction, stale reconstructed events and issues. No I/O.
    """
    current_epoch = emap.current_epoch
    real = sorted([p for p in payouts if not p.get("reconstructed")], key=lambda p: (p["tick"] or 0))
    recon = {p["event_id"]: p for p in payouts if p.get("reconstructed")}
    used: set[str] = set()
    splits: dict[str, dict] = {}
    classification: dict[str, str] = {}
    candidates: list[dict] = []
    issues: list[dict] = []
    positions: dict[int, dict] = {}

    locks = sorted([t for t in txs if t["input_type"] == 1 and t["amount"] > 0], key=lambda t: t["tick"])
    unlocks = sorted([t for t in txs if t["input_type"] == 2], key=lambda t: t["tick"])

    def take_real(pred):
        for p in real:
            if p["event_id"] not in used and pred(p):
                used.add(p["event_id"])
                return p
        return None

    def payout_epoch(p):
        return p.get("epoch") if p.get("epoch") is not None else emap.epoch_of_tick(p.get("tick"))

    # Locks. A lock the contract rejected is refunded in the same tick.
    for lock in locks:
        refund = take_real(lambda p, l=lock: p["tick"] == l["tick"] and p["amount"] == l["amount"])
        if refund:
            classification[refund["event_id"]] = KIND_REFUND
            continue
        ep = emap.epoch_of_tick(lock["tick"])
        if ep is None:
            issues.append({"code": "unknown_epoch", "tick": lock["tick"]})
            continue
        pos = positions.setdefault(ep, _new_position(ep))
        pos["principal"] += lock["amount"]
        pos["lock_txs"].append(lock["hash"])
        if lock.get("ts") and (pos["lock_ts"] is None or lock["ts"] < pos["lock_ts"]):
            pos["lock_ts"] = lock["ts"]

    # Early unlocks (in tick order, each reduces its position).
    for un in unlocks:
        dec = decode_unlock_input(un.get("input_b64"))
        if dec is None:
            continue
        req, lock_ep = dec
        unlock_ep = emap.epoch_of_tick(un["tick"])
        pos = positions.get(lock_ep)
        if pos is not None:
            remaining = pos["principal"] - pos["early_unlocked"]
            if req < MIN_LOCK_AMOUNT or req > remaining or remaining <= 0:
                continue  # contract rejects it → no transfer
            amount = remaining if remaining - req < MIN_LOCK_AMOUNT else req
        else:
            if req < MIN_LOCK_AMOUNT:
                continue
            amount = req
        pct = early_unlock_percent(unlock_ep, lock_ep) if unlock_ep is not None else 0
        weeks = (unlock_ep - lock_ep) if unlock_ep is not None else None
        base_meta = {
            "kind": "EARLY", "lock_epoch": lock_ep, "payout_epoch": unlock_ep, "weeks": weeks,
            "lock_ts": pos["lock_ts"] if pos else None, "lock_txs": list(pos["lock_txs"]) if pos else [],
            "unlock_tx": un["hash"], "early_pct": pct, "yield_e7": yields.get(lock_ep),
        }
        payout = take_real(lambda p, u=un: p["tick"] == u["tick"])
        entry = {"tick": un["tick"], "amount": amount, "pct": pct, "unlock_tx": un["hash"]}
        if payout:
            principal = min(amount, payout["amount"])
            interest = payout["amount"] - principal
            splits[payout["event_id"]] = _split(principal, interest, False, base_meta, payout)
            classification[payout["event_id"]] = KIND_PAYOUT
            entry.update(payout_event_id=payout["event_id"], interest=interest, status="PAID", estimated=False)
        else:
            recon_id = f"qearn:{lock_ep}:E{un['tick']}"
            y = yields.get(lock_ep)
            exact = pct == 0
            reward = 0 if exact else (early_reward(amount, y, pct) if y is not None else None)
            if recon_id in recon:
                rp = recon.pop(recon_id)
                est = not exact and not rp.get("override")
                splits[recon_id] = _split(amount, rp["amount"] - amount, est, base_meta, rp)
                classification[recon_id] = KIND_PAYOUT
                entry.update(payout_event_id=recon_id, interest=rp["amount"] - amount, status="RECONSTRUCTED",
                             estimated=est, override=bool(rp.get("override")))
            elif reward is not None:
                candidates.append({
                    "event_id": recon_id, "kind": "EARLY", "lock_epoch": lock_ep, "payout_epoch": unlock_ep,
                    "tick": un["tick"], "timestamp": un.get("ts"), "principal": amount, "interest": reward,
                    "amount": amount + reward, "estimated": not exact, "meta": {**base_meta, "estimated": not exact},
                })
                entry.update(status="MISSING", interest=reward, estimated=not exact)
            else:
                issues.append({"code": "no_yield", "lock_epoch": lock_ep})
                entry.update(status="MISSING")
        if pos is not None:
            pos["early_unlocked"] += amount
            pos["early"].append(entry)

    # Regular payouts at the end of epoch lock_epoch + 52.
    for lock_ep in sorted(positions):
        pos = positions[lock_ep]
        remaining = pos["principal"] - pos["early_unlocked"]
        y = yields.get(lock_ep)
        pos["yield_e7"] = y
        if remaining <= 0:
            pos["status"] = "EARLY_UNLOCKED"
            continue
        end = pos["end_epoch"]
        expected = remaining + full_reward(remaining, y) if y is not None else None
        pos["expected_payout"] = expected
        if current_epoch <= end:
            pos["status"] = "LOCKED"
            continue
        meta = {
            "kind": "FULL", "lock_epoch": lock_ep, "payout_epoch": end, "weeks": LOCK_EPOCHS,
            "lock_ts": pos["lock_ts"], "lock_txs": list(pos["lock_txs"]), "yield_e7": y,
            "partial": pos["early_unlocked"] > 0,
        }
        payout = None
        if expected is not None:
            payout = take_real(lambda p, e=end, x=expected: payout_epoch(p) == e and p["amount"] == x)
        if payout is None:
            payout = take_real(lambda p, e=end, r=remaining: payout_epoch(p) == e and p["amount"] >= r)
        if payout:
            interest = payout["amount"] - remaining
            meta["yield_mismatch"] = expected is not None and payout["amount"] != expected
            splits[payout["event_id"]] = _split(remaining, interest, False, meta, payout)
            classification[payout["event_id"]] = KIND_PAYOUT
            pos.update(status="PAID", payout=payout["amount"], interest=interest, payout_event_id=payout["event_id"])
            continue
        recon_id = f"qearn:{lock_ep}:F{end}"
        if recon_id in recon:
            rp = recon.pop(recon_id)
            splits[recon_id] = _split(remaining, rp["amount"] - remaining, False, meta, rp)
            classification[recon_id] = KIND_PAYOUT
            pos.update(status="RECONSTRUCTED", payout=rp["amount"], interest=rp["amount"] - remaining,
                       payout_event_id=recon_id)
        elif expected is not None:
            candidates.append({
                "event_id": recon_id, "kind": "FULL", "lock_epoch": lock_ep, "payout_epoch": end,
                "tick": emap.last_tick(end), "timestamp": None, "principal": remaining,
                "interest": expected - remaining, "amount": expected, "estimated": False,
                "meta": {**meta, "estimated": False},
            })
            pos.update(status="MISSING", interest=expected - remaining)
        else:
            issues.append({"code": "no_yield", "lock_epoch": lock_ep})
            pos["status"] = "MISSING"

    # Payouts without a known lock (lock missing from the TX history): an
    # END_EPOCH payout can be inverted with the yield of its round. Only
    # transfers at the very end of an epoch qualify — anything mid-epoch is
    # an early unlock whose reward cannot be derived this way.
    for p in real:
        if p["event_id"] in used:
            continue
        classification[p["event_id"]] = KIND_PAYOUT
        pe = payout_epoch(p)
        lock_ep = pe - LOCK_EPOCHS if pe is not None else None
        y = yields.get(lock_ep) if lock_ep is not None else None
        last = emap.last_tick(pe) if pe is not None else None
        at_epoch_end = last is not None and (p.get("tick") or 0) >= last - 2
        principal = derive_principal(p["amount"], y) if (y is not None and at_epoch_end) else None
        if principal is None:
            issues.append({"code": "unmatched_payout", "event_id": p["event_id"], "amount": p["amount"]})
            continue
        used.add(p["event_id"])
        meta = {"kind": "FULL", "lock_epoch": lock_ep, "payout_epoch": pe, "weeks": LOCK_EPOCHS,
                "lock_ts": None, "lock_txs": [], "yield_e7": y, "derived": True}
        splits[p["event_id"]] = _split(principal, p["amount"] - principal, False, meta, p)
        if lock_ep not in positions:
            pos = _new_position(lock_ep)
            pos.update(principal=principal, yield_e7=y, expected_payout=p["amount"], status="PAID",
                       payout=p["amount"], interest=p["amount"] - principal,
                       payout_event_id=p["event_id"], derived=True)
            positions[lock_ep] = pos

    return {
        "wallet_id": wallet_id,
        "positions": [positions[k] for k in sorted(positions)],
        "splits": splits,
        "classification": classification,
        "candidates": candidates,
        "stale_reconstructed": sorted(recon),   # computed payouts now superseded / no longer valid
        "issues": issues,
        "archive_imports": [p for p in real if p.get("origin") == "archive"],
    }


def _split(principal: int, interest: int, estimated: bool, meta: dict, payout: dict) -> dict:
    m = dict(meta)
    m.update(principal=principal, interest=interest, payout_ts=payout.get("timestamp"),
             estimated=estimated, override=bool(payout.get("override")))
    return {"principal": principal, "interest": interest, "estimated": estimated, "meta": m}


# ─────────────────────────────── I/O layer ───────────────────────────────

_run_lock = asyncio.Lock()
_status_cache: dict = {"at": 0.0, "emap": None}
_STATUS_TTL = 600
_YIELD_TTL_OPEN = 6 * 3600


def _clients(db: Session) -> list[RPCClient]:
    """User's RPC/home node first, public RPC as fallback (the /query API may be missing on custom nodes)."""
    from .sync_engine import _get_rpc_client
    primary = _get_rpc_client(db)
    default = RPCClient()
    return [primary] if primary.base_url == default.base_url else [primary, default]


async def _with_fallback(clients: list[RPCClient], fn):
    last: Exception | None = None
    for c in clients:
        try:
            return await fn(c)
        except Exception as e:  # try the next client
            last = e
    raise last if last else RuntimeError("no RPC client")


async def get_epoch_map(clients: list[RPCClient], force: bool = False) -> EpochMap:
    now = time.monotonic()
    if not force and _status_cache["emap"] is not None and now - _status_cache["at"] < _STATUS_TTL:
        return _status_cache["emap"]
    status = await _with_fallback(clients, lambda c: c.get_status())
    emap = EpochMap.from_status(status)
    if not emap.current_epoch:
        raise RuntimeError("archiver status without epoch data")
    _status_cache.update(at=now, emap=emap)
    return emap


async def get_yields(db: Session, clients: list[RPCClient], epochs: set[int], current_epoch: int) -> dict[int, int | None]:
    out: dict[int, int | None] = {}
    for ep in sorted(e for e in epochs if e is not None and e > 0):
        row = db.query(QearnEpoch).filter(QearnEpoch.epoch == ep).first()
        ended = current_epoch > ep + LOCK_EPOCHS
        fresh = row is not None and (row.final or (
            row.fetched_at and (datetime.now(timezone.utc) - datetime.fromisoformat(row.fetched_at.replace("Z", "+00:00"))).total_seconds() < _YIELD_TTL_OPEN
        ))
        if fresh and (row.final or not ended):
            out[ep] = row.yield_e7
            continue
        try:
            raw = await _with_fallback(
                clients, lambda c, e=ep: c.query_smart_contract(QEARN_CONTRACT_INDEX, 1, struct.pack("<I", e)))
            if len(raw) < 40:
                raise ValueError(f"short response ({len(raw)} bytes)")
            locked, bonus, cur_locked, cur_bonus, yld = struct.unpack_from("<5Q", raw)
            if row is None:
                row = QearnEpoch(epoch=ep)
                db.add(row)
            row.yield_e7 = int(yld) if cur_locked else None
            row.locked_amount = int(cur_locked)
            row.bonus_amount = int(cur_bonus)
            row.final = 1 if ended else 0
            row.fetched_at = now_utc_iso()
            db.flush()
            out[ep] = row.yield_e7
        except Exception as e:
            logger.warning(f"Qearn yield for epoch {ep} unavailable: {e}")
            out[ep] = row.yield_e7 if row is not None else None
    return out


async def _fetch_qearn_txs(clients: list[RPCClient], wallet_id: str) -> list[dict]:
    """All transactions wallet → Qearn (locks + unlock requests), full history."""
    async def run(c: RPCClient):
        out, offset = [], 0
        while True:
            resp = await c.get_transactions_for_identity(
                wallet_id, {"source": wallet_id, "destination": QEARN_ADDRESS}, offset=offset, size=100)
            items = resp.get("transactions") or []
            out.extend(items)
            offset += len(items)
            total = int((resp.get("hits") or {}).get("total") or 0)
            if not items or offset >= total:
                return out
    raw = await _with_fallback(clients, run)
    txs = []
    for t in raw:
        if t.get("source") != wallet_id or t.get("destination") != QEARN_ADDRESS:
            continue
        if not t.get("moneyFlew", True) and int(t.get("inputType") or 0) == 1:
            continue  # lock whose QU never moved
        txs.append({
            "hash": t.get("hash"),
            "tick": int(t.get("tickNumber") or 0),
            "ts": unix_ms_to_iso(t.get("timestamp")) if t.get("timestamp") else None,
            "amount": int(t.get("amount") or 0),
            "input_type": int(t.get("inputType") or 0),
            "input_b64": t.get("inputData") or "",
        })
    return txs


async def _fetch_archive_payouts(clients: list[RPCClient], wallet_id: str, from_tick: int, to_tick: int) -> list[dict]:
    async def run(c: RPCClient):
        out, offset = [], 0
        while True:
            resp = await c.get_event_logs_filtered(
                {"source": QEARN_ADDRESS, "destination": wallet_id}, from_tick, to_tick, offset=offset, size=1000)
            logs = resp.get("eventLogs") or []
            out.extend(logs)
            offset += len(logs)
            total = int((resp.get("hits") or {}).get("total") or 0)
            if not logs or offset >= total:
                return out
    return await _with_fallback(clients, run)


def _log_effective_id(log: dict) -> str:
    for c in (log.get("transactionHash"), log.get("transactionId"), log.get("txId"), log.get("digest")):
        if isinstance(c, str) and len(c) == 60 and c.isalpha() and c.islower():
            return c
    return str(log.get("logId"))


def _event_exists(db: Session, wallet_id: str, keys: set[str]) -> bool:
    keys = {k for k in keys if k}
    if not keys:
        return False
    return db.query(Event.id).filter(
        Event.wallet_id == wallet_id,
        or_(Event.id.in_(keys), Event.log_digest.in_(keys)),
    ).first() is not None


async def analyze_wallet(db: Session, wallet_id: str, clients: list[RPCClient], emap: EpochMap) -> dict:
    """Gather all inputs of one wallet and run compute_analysis (read-only apart from the yield cache)."""
    txs = await _fetch_qearn_txs(clients, wallet_id)

    # Lock rows already in the DB but not returned by the archiver (defensive merge).
    known = {(t["tick"], t["amount"]) for t in txs if t["input_type"] == 1}
    known_ids = {t["hash"] for t in txs}
    for ev in db.query(Event).filter(
        Event.wallet_id == wallet_id, Event.source_address == wallet_id,
        Event.destination_addr == QEARN_ADDRESS, Event.amount_qubic > 0,
    ).all():
        if ev.id in known_ids or ev.log_digest in known_ids or (ev.tick_number, ev.amount_qubic) in known:
            continue
        txs.append({"hash": ev.id, "tick": ev.tick_number or 0, "ts": ev.timestamp,
                    "amount": ev.amount_qubic, "input_type": 1, "input_b64": ""})

    split_rows = db.query(EventSplit).filter(EventSplit.wallet_id == wallet_id).all()
    overrides = set()
    for s in split_rows:
        try:
            if json.loads(s.meta_json or "{}").get("override"):
                overrides.add(s.event_id)
        except ValueError:
            pass

    payouts = []
    db_ids: set[str] = set()
    for ev in db.query(Event).filter(
        Event.wallet_id == wallet_id, Event.source_address == QEARN_ADDRESS,
        Event.destination_addr == wallet_id, Event.amount_qubic > 0,
    ).all():
        db_ids.update(filter(None, (ev.id, ev.log_digest)))
        payouts.append({
            "event_id": ev.id, "tick": ev.tick_number, "epoch": ev.epoch, "amount": ev.amount_qubic,
            "timestamp": ev.timestamp, "reconstructed": bool(ev.reconstructed), "origin": "db",
            "override": ev.id in overrides,
        })

    # Qearn only pays the wallet that locked: without any lock or payout there
    # is nothing to find, and payouts can never precede the first lock.
    if not txs and not payouts:
        return {"wallet_id": wallet_id, "txs": [], "has_activity": False}
    to_tick = max(emap.last_tick(emap.current_epoch) or 0, 1)
    from_tick = min((t["tick"] for t in txs if t["tick"]), default=1)
    for log in await _fetch_archive_payouts(clients, wallet_id, from_tick, to_tick):
        qu = log.get("quTransfer") or {}
        amount = int(qu.get("amount") or 0)
        if qu.get("source") != QEARN_ADDRESS or qu.get("destination") != wallet_id or amount <= 0:
            continue
        eid = _log_effective_id(log)
        if {eid, str(log.get("logId")), log.get("logDigest")} & db_ids:
            continue
        db_ids.add(eid)
        payouts.append({
            "event_id": eid, "tick": int(log.get("tickNumber") or 0), "epoch": log.get("epoch"),
            "amount": amount, "timestamp": unix_ms_to_iso(log.get("timestamp") or "0"),
            "reconstructed": False, "origin": "archive", "log": log,
        })

    needed: set[int] = set()
    for t in txs:
        if t["input_type"] == 1:
            needed.add(emap.epoch_of_tick(t["tick"]))
        elif t["input_type"] == 2:
            dec = decode_unlock_input(t["input_b64"])
            if dec:
                needed.add(dec[1])
    for p in payouts:
        pe = p["epoch"] if p["epoch"] is not None else emap.epoch_of_tick(p["tick"])
        if pe is not None:
            needed.add(pe - LOCK_EPOCHS)
    yields = await get_yields(db, clients, {e for e in needed if e}, emap.current_epoch)

    result = compute_analysis(wallet_id, txs, payouts, yields, emap)
    result["txs"] = txs
    result["has_activity"] = bool(txs or payouts)
    return result


async def _price(db: Session, iso: str | None, cache: dict) -> dict:
    from .coingecko import get_price_for_date
    if not iso:
        return {}
    d = iso_to_date(iso)
    if d not in cache:
        cache[d] = await get_price_for_date(db, d)
    return cache[d] or {}


async def apply_analysis(db: Session, analysis: dict, clients: list[RPCClient], emap: EpochMap,
                         confirmed: set[str]) -> dict:
    """Persist one wallet's analysis. Reconstructed payouts are only created for
    event ids in `confirmed` (the user's explicit choice in the preview)."""
    wallet_id = analysis["wallet_id"]
    prices: dict = {}
    stats = {"locks_imported": 0, "payouts_imported": 0, "reconstructed": 0, "removed": 0, "splits": 0}

    # 1) lock / unlock history missing in the DB
    for t in analysis["txs"]:
        if t["input_type"] != 1 or t["amount"] <= 0 or not t["hash"]:
            continue
        if _event_exists(db, wallet_id, {t["hash"]}) or db.query(Event.id).filter(
            Event.wallet_id == wallet_id, Event.tick_number == t["tick"], Event.source_address == wallet_id,
            Event.destination_addr == QEARN_ADDRESS, Event.amount_qubic == t["amount"],
        ).first():
            continue
        price = await _price(db, t["ts"], prices)
        db.add(Event(
            id=t["hash"], wallet_id=wallet_id, epoch=emap.epoch_of_tick(t["tick"]), tick_number=t["tick"],
            timestamp_raw=None, timestamp=t["ts"], log_type=1, log_digest=t["hash"],
            source_address=wallet_id, destination_addr=QEARN_ADDRESS,
            is_internal=0, amount_qubic=t["amount"],  # the contract is never a user wallet
            qubic_eur_rate=price.get("eur"), qubic_usd_rate=price.get("usd"),
            source_type="EVENT", sc_kind=KIND_LOCK, verified=0, reconstructed=0, created_at=now_utc_iso(),
        ))
        stats["locks_imported"] += 1

    # 2) payouts that exist in the archive but not in the DB
    for p in analysis["archive_imports"]:
        if _event_exists(db, wallet_id, {p["event_id"], str(p["log"].get("logId"))}):
            continue
        log = p["log"]
        price = await _price(db, p["timestamp"], prices)
        eid = p["event_id"]
        db.add(Event(
            id=eid, wallet_id=wallet_id, epoch=p["epoch"], tick_number=p["tick"],
            timestamp_raw=log.get("timestamp"), timestamp=p["timestamp"], log_type=log.get("logType"),
            log_digest=eid if len(eid) == 60 else log.get("logDigest"),
            categories=json.dumps(log.get("categories") or []),
            source_address=QEARN_ADDRESS, destination_addr=wallet_id, is_internal=0,
            amount_qubic=p["amount"], qubic_eur_rate=price.get("eur"), qubic_usd_rate=price.get("usd"),
            source_type="EVENT", sc_kind=analysis["classification"].get(eid, KIND_PAYOUT),
            verified=0, reconstructed=0, created_at=now_utc_iso(),
        ))
        stats["payouts_imported"] += 1

    # 3) confirmed reconstructions
    new_splits = dict(analysis["splits"])
    for c in analysis["candidates"]:
        if c["event_id"] not in confirmed or _event_exists(db, wallet_id, {c["event_id"]}):
            continue
        ts = c.get("timestamp")
        if not ts and c.get("tick") and clients:
            try:
                ms = await _with_fallback(clients, lambda cl, tk=c["tick"]: cl.get_tick_timestamp_ms(tk))
                ts = unix_ms_to_iso(ms) if ms else None
            except Exception:
                ts = None
        ts = ts or epoch_end_fallback_iso(c["payout_epoch"])
        price = await _price(db, ts, prices)
        db.add(Event(
            id=c["event_id"], wallet_id=wallet_id, epoch=c["payout_epoch"], tick_number=c.get("tick"),
            timestamp_raw=None, timestamp=ts, log_type=0, log_digest=None,
            categories=json.dumps([5] if c["kind"] == "FULL" else []),
            source_address=QEARN_ADDRESS, destination_addr=wallet_id, is_internal=0,
            amount_qubic=c["amount"], qubic_eur_rate=price.get("eur"), qubic_usd_rate=price.get("usd"),
            source_type="EVENT", sc_kind=KIND_PAYOUT, verified=0, reconstructed=1, created_at=now_utc_iso(),
        ))
        meta = dict(c["meta"])
        meta.update(principal=c["principal"], interest=c["interest"], payout_ts=ts, override=False)
        new_splits[c["event_id"]] = {"principal": c["principal"], "interest": c["interest"],
                                     "estimated": c["estimated"], "meta": meta}
        stats["reconstructed"] += 1
    db.flush()

    # 4) reconstructed payouts superseded by real data
    for eid in analysis["stale_reconstructed"]:
        db.query(EventSplit).filter(EventSplit.wallet_id == wallet_id, EventSplit.event_id == eid).delete()
        stats["removed"] += db.query(Event).filter(
            Event.wallet_id == wallet_id, Event.id == eid, Event.reconstructed == 1).delete()

    # 5) classification of every Qearn row of this wallet
    for ev in db.query(Event).filter(
        Event.wallet_id == wallet_id,
        or_(Event.source_address == QEARN_ADDRESS, Event.destination_addr == QEARN_ADDRESS),
    ).all():
        if ev.destination_addr == QEARN_ADDRESS and ev.source_address == wallet_id:
            ev.sc_kind = KIND_LOCK
            ev.source_type = "EVENT"
        elif ev.source_address == QEARN_ADDRESS:
            ev.sc_kind = analysis["classification"].get(ev.id, KIND_PAYOUT)

    # 6) splits (rewritten completely for this wallet; orphans vanish with it)
    db.query(EventSplit).filter(EventSplit.wallet_id == wallet_id).delete()
    now = now_utc_iso()
    existing_ids = {r[0] for r in db.query(Event.id).filter(Event.wallet_id == wallet_id,
                                                             Event.id.in_(list(new_splits) or [""])).all()}
    for eid, s in new_splits.items():
        if eid not in existing_ids:
            continue
        meta_json = json.dumps(s["meta"])
        db.add(EventSplit(event_id=eid, wallet_id=wallet_id, part=PART_PRINCIPAL, amount_qubic=s["principal"],
                          estimated=0, meta_json=meta_json, updated_at=now))
        db.add(EventSplit(event_id=eid, wallet_id=wallet_id, part=PART_INTEREST, amount_qubic=s["interest"],
                          estimated=1 if s["estimated"] else 0, meta_json=meta_json, updated_at=now))
        stats["splits"] += 1

    # 7) positions
    db.query(QearnPosition).filter(QearnPosition.wallet_id == wallet_id).delete()
    created = {c["event_id"] for c in analysis["candidates"] if c["event_id"] in existing_ids}
    for pos in analysis["positions"]:
        status = pos["status"] or "LOCKED"
        detail = {k: pos[k] for k in ("lock_txs", "lock_ts", "early", "payout_event_id", "derived")}
        rec_id = f"qearn:{pos['lock_epoch']}:F{pos['end_epoch']}"
        if status == "MISSING" and rec_id in created:
            status = "RECONSTRUCTED"
            detail["payout_event_id"] = rec_id
            pos["payout"] = pos["expected_payout"]
        for e in detail["early"]:
            eid = f"qearn:{pos['lock_epoch']}:E{e['tick']}"
            if e.get("status") == "MISSING" and eid in created:
                e.update(status="RECONSTRUCTED", payout_event_id=eid)
        db.add(QearnPosition(
            wallet_id=wallet_id, lock_epoch=pos["lock_epoch"], principal_qu=pos["principal"],
            early_unlocked_qu=pos["early_unlocked"], end_epoch=pos["end_epoch"], yield_e7=pos["yield_e7"],
            expected_payout_qu=pos["expected_payout"], payout_qu=pos["payout"], interest_qu=pos["interest"],
            status=status, detail_json=json.dumps(detail), checked_at=now,
        ))
    db.commit()
    return stats


def candidate_key(wallet_id: str, event_id: str) -> str:
    return f"{wallet_id}|{event_id}"


def _public_analysis(a: dict) -> dict:
    """JSON-safe preview of one wallet's analysis for the UI."""
    return {
        "wallet_id": a["wallet_id"],
        "positions": [{k: v for k, v in p.items()} for p in a["positions"]],
        "candidates": [{**{k: v for k, v in c.items() if k != "meta"},
                        "key": candidate_key(a["wallet_id"], c["event_id"])} for c in a["candidates"]],
        "missing_locks": sum(1 for t in a["txs"] if t["input_type"] == 1 and t["amount"] > 0 and t.get("_missing")),
        "archive_imports": len(a["archive_imports"]),
        "splits": len(a["splits"]),
        "stale_reconstructed": a["stale_reconstructed"],
        "issues": a["issues"],
    }


def _mark_missing_locks(db: Session, a: dict) -> None:
    wid = a["wallet_id"]
    for t in a["txs"]:
        if t["input_type"] == 1 and t["amount"] > 0:
            t["_missing"] = not (_event_exists(db, wid, {t["hash"]}) or db.query(Event.id).filter(
                Event.wallet_id == wid, Event.tick_number == t["tick"], Event.source_address == wid,
                Event.destination_addr == QEARN_ADDRESS, Event.amount_qubic == t["amount"],
            ).first() is not None)


def _target_wallets(db: Session, wallet_ids: list[str] | None) -> list[str]:
    q = db.query(Wallet.id).filter(Wallet.deleted_at.is_(None))
    if wallet_ids:
        q = q.filter(Wallet.id.in_(wallet_ids))
    return [r[0] for r in q.all()]


async def run_check(db: Session, wallet_ids: list[str] | None = None, apply: bool = False,
                    confirmed_keys: set[str] | None = None, progress: dict | None = None) -> dict:
    """Manual Qearn check. apply=False → preview only (dry run)."""
    async with _run_lock:
        clients = _clients(db)
        emap = await get_epoch_map(clients, force=True)
        results, errors = [], []
        targets = _target_wallets(db, wallet_ids)
        if progress is not None:
            progress.update(done=0, total=len(targets))
        for wid in targets:
            if progress is not None:
                progress["done"] += 1
            try:
                a = await analyze_wallet(db, wid, clients, emap)
                if not a["has_activity"]:
                    db.commit()
                    continue
                if apply:
                    confirmed = {k.split("|", 1)[1] for k in (confirmed_keys or set()) if k.startswith(wid + "|")}
                    stats = await apply_analysis(db, a, clients, emap, confirmed)
                    results.append({"wallet_id": wid, "applied": stats, "issues": a["issues"]})
                else:
                    _mark_missing_locks(db, a)
                    db.commit()  # yield cache only
                    results.append(_public_analysis(a))
            except Exception as e:
                db.rollback()
                logger.error(f"Qearn check failed for {wid}: {e}", exc_info=True)
                errors.append({"wallet_id": wid, "error": str(e)[:300]})
        if apply:
            msg = f"Qearn check applied for {len(results)} wallet(s)"
            logger.info(msg)
            log_buffer.add("INFO", "qearn", msg)
        return {"current_epoch": emap.current_epoch, "wallets": results, "errors": errors}


# ─────────────────────── background job for the UI ───────────────────────
# A check over many wallets can take longer than a reverse proxy waits for a
# response (nginx: 60 s), so the UI starts a job and polls its state.

_job: dict = {"id": 0, "state": "idle", "kind": None, "result": None, "error": None,
              "progress": {"done": 0, "total": 0}, "started_at": None, "finished_at": None}
_job_task: asyncio.Task | None = None


def job_status() -> dict:
    return {k: v for k, v in _job.items()}


async def _run_job(job_id: int, apply: bool, wallet_ids, confirmed: set[str]) -> None:
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        result = await run_check(db, wallet_ids, apply=apply, confirmed_keys=confirmed, progress=_job["progress"])
        if _job["id"] == job_id:
            _job.update(state="done", result=result, finished_at=now_utc_iso())
    except Exception as e:
        logger.error(f"Qearn job failed: {e}", exc_info=True)
        if _job["id"] == job_id:
            _job.update(state="error", error=str(e)[:300], finished_at=now_utc_iso())
    finally:
        db.close()


def start_job(apply: bool, wallet_ids: list[str] | None, confirmed: set[str]) -> dict:
    global _job_task
    if _job["state"] == "running":
        raise RuntimeError("a Qearn check is already running")
    _job.update(id=_job["id"] + 1, state="running", kind="apply" if apply else "check", result=None,
                error=None, progress={"done": 0, "total": 0}, started_at=now_utc_iso(), finished_at=None)
    _job_task = asyncio.get_running_loop().create_task(_run_job(_job["id"], apply, wallet_ids, confirmed))
    return job_status()


# ─────────────────────── automatic processing after sync ───────────────────────

_auto_backoff: dict[str, float] = {}
_AUTO_RETRY_SECONDS = 900


def wallet_needs_processing(db: Session, wallet_id: str) -> bool:
    """New Qearn rows that were never classified (cheap indexed query)."""
    return db.query(Event.id).filter(
        Event.wallet_id == wallet_id,
        Event.sc_kind.is_(None),
        or_(Event.source_address == QEARN_ADDRESS, Event.destination_addr == QEARN_ADDRESS),
    ).first() is not None


async def auto_process_wallet(db: Session, wallet_id: str) -> None:
    """Classify, import exact history and split — never creates reconstructions."""
    now = time.monotonic()
    if now - _auto_backoff.get(wallet_id, -1e9) < _AUTO_RETRY_SECONDS or _run_lock.locked():
        return
    _auto_backoff[wallet_id] = now
    async with _run_lock:
        try:
            clients = _clients(db)
            emap = await get_epoch_map(clients)
            a = await analyze_wallet(db, wallet_id, clients, emap)
            stats = await apply_analysis(db, a, clients, emap, confirmed=set())
            _auto_backoff.pop(wallet_id, None)
            logger.info(f"Qearn auto-processing {wallet_id}: {stats}")
        except Exception as e:
            db.rollback()
            logger.warning(f"Qearn auto-processing failed for {wallet_id}: {e}")


async def refresh_positions_job() -> None:
    """Weekly after the epoch switch: re-evaluate wallets with Qearn positions
    so LOCKED rounds turn into PAID/MISSING without user action."""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        wallet_ids = [r[0] for r in db.query(QearnPosition.wallet_id).distinct().all()]
    finally:
        db.close()
    for wid in wallet_ids:
        _auto_backoff.pop(wid, None)
        wdb = SessionLocal()  # fresh session per wallet: a failure never leaks into the next one
        try:
            await auto_process_wallet(wdb, wid)
        finally:
            wdb.close()


async def override_interest(db: Session, event_id: str, wallet_id: str, interest: int) -> dict:
    """Replace the estimated interest of a reconstructed early-unlock payout (e.g. with the explorer value)."""
    ev = db.query(Event).filter(Event.id == event_id, Event.wallet_id == wallet_id).first()
    if ev is None:
        raise LookupError("event not found")
    parts = {s.part: s for s in db.query(EventSplit).filter(
        EventSplit.event_id == event_id, EventSplit.wallet_id == wallet_id).all()}
    principal, interest_row = parts.get(PART_PRINCIPAL), parts.get(PART_INTEREST)
    if not ev.reconstructed or principal is None or interest_row is None:
        raise PermissionError("only reconstructed payouts can be corrected")
    meta = json.loads(interest_row.meta_json or "{}")
    if not (interest_row.estimated or meta.get("override")):
        raise PermissionError("exact values cannot be overridden")
    if interest < 0:
        raise ValueError("interest must not be negative")
    ev.amount_qubic = principal.amount_qubic + interest
    meta.update(interest=interest, override=True, estimated=False)
    interest_row.amount_qubic = interest
    interest_row.estimated = 0
    now = now_utc_iso()
    for row in (principal, interest_row):
        row.meta_json = json.dumps(meta)
        row.updated_at = now
    lock_epoch = meta.get("lock_epoch")
    pos = db.query(QearnPosition).filter(QearnPosition.wallet_id == wallet_id,
                                          QearnPosition.lock_epoch == lock_epoch).first()
    if pos is not None and pos.detail_json:
        detail = json.loads(pos.detail_json)
        for e in detail.get("early") or []:
            if e.get("payout_event_id") == event_id:
                e.update(interest=interest, estimated=False, override=True)
        pos.detail_json = json.dumps(detail)
    db.commit()
    return {"event_id": event_id, "amount_qubic": ev.amount_qubic, "interest": interest}
