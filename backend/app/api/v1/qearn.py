import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.qearn import QearnPosition
from ...models.wallet import Wallet
from ...services import qearn_service

router = APIRouter()


class QearnCheckRequest(BaseModel):
    wallet_ids: Optional[List[str]] = None


class QearnApplyRequest(BaseModel):
    wallet_ids: Optional[List[str]] = None
    # candidate keys ("<wallet>|<event id>") the user confirmed for reconstruction
    reconstruct: List[str] = []


class InterestOverride(BaseModel):
    wallet_id: str
    interest_qubic: int


@router.get("/qearn/positions")
def list_positions(wallet_ids: List[str] = Query(default=[]), db: Session = Depends(get_db)):
    active = {w.id for w in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()}
    q = db.query(QearnPosition)
    if wallet_ids:
        q = q.filter(QearnPosition.wallet_id.in_(wallet_ids))
    rows = q.order_by(QearnPosition.wallet_id, QearnPosition.lock_epoch).all()
    out = []
    for r in rows:
        if r.wallet_id not in active:
            continue
        out.append({
            "wallet_id": r.wallet_id, "lock_epoch": r.lock_epoch, "end_epoch": r.end_epoch,
            "principal": r.principal_qu, "early_unlocked": r.early_unlocked_qu, "yield_e7": r.yield_e7,
            "expected_payout": r.expected_payout_qu, "payout": r.payout_qu, "interest": r.interest_qu,
            "status": r.status, "detail": json.loads(r.detail_json or "{}"), "checked_at": r.checked_at,
        })
    return out


@router.post("/qearn/check", status_code=202)
async def check(body: QearnCheckRequest):
    """Start a dry run: shows what the check would import, split and reconstruct."""
    try:
        return qearn_service.start_job(False, body.wallet_ids, set())
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.post("/qearn/apply", status_code=202)
async def apply(body: QearnApplyRequest):
    """Start the real run; reconstructions only for the confirmed candidate keys."""
    try:
        return qearn_service.start_job(True, body.wallet_ids, set(body.reconstruct))
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.get("/qearn/job")
def job():
    return qearn_service.job_status()


@router.put("/qearn/splits/{event_id}/interest")
async def set_interest(event_id: str, body: InterestOverride, db: Session = Depends(get_db)):
    try:
        return await qearn_service.override_interest(db, event_id, body.wallet_id, body.interest_qubic)
    except LookupError:
        raise HTTPException(404, "Event not found")
    except (PermissionError, ValueError) as e:
        raise HTTPException(400, str(e))
