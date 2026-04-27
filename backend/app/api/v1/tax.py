import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ...database import get_db
from ...models.settings import AppSetting
from ...models.opening_position import OpeningPosition
from ...services import tax_engine
from ...utils.time import now_utc_iso

router = APIRouter()

TAX_PREFIX = "tax."


def _parse_json_value(raw: Optional[str]) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _encode_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    return json.dumps(value)


@router.get("/tax/settings")
def get_tax_settings(db: Session = Depends(get_db)):
    rows = db.query(AppSetting).filter(AppSetting.key.like(f"{TAX_PREFIX}%")).all()
    result: dict[str, Any] = {}
    for row in rows:
        short = row.key[len(TAX_PREFIX):]
        result[short] = _parse_json_value(row.value)
    return result


class TaxSettingsUpdate(BaseModel):
    class Config:
        extra = "allow"


@router.put("/tax/settings")
def update_tax_settings(payload: dict[str, Any], db: Session = Depends(get_db)):
    for k, v in payload.items():
        full_key = f"{TAX_PREFIX}{k}"
        row = db.query(AppSetting).filter(AppSetting.key == full_key).first()
        encoded = _encode_value(v)
        if row:
            row.value = encoded
        else:
            db.add(AppSetting(key=full_key, value=encoded))
    db.commit()
    return get_tax_settings(db)


# --- Opening Positions ---

class OpeningPositionCreate(BaseModel):
    wallet_id: str
    date: str
    amount_qubic: int
    price_eur: Optional[float] = None
    price_usd: Optional[float] = None
    note: Optional[str] = None


class OpeningPositionOut(BaseModel):
    id: int
    wallet_id: str
    date: str
    amount_qubic: int
    price_eur: Optional[float] = None
    price_usd: Optional[float] = None
    note: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


@router.get("/tax/opening-positions", response_model=list[OpeningPositionOut])
def list_opening_positions(
    wallet_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(OpeningPosition)
    if wallet_id:
        q = q.filter(OpeningPosition.wallet_id == wallet_id)
    q = q.order_by(OpeningPosition.date.asc())
    return q.all()


@router.post("/tax/opening-positions", response_model=OpeningPositionOut, status_code=201)
def create_opening_position(payload: OpeningPositionCreate, db: Session = Depends(get_db)):
    row = OpeningPosition(
        wallet_id=payload.wallet_id,
        date=payload.date,
        amount_qubic=payload.amount_qubic,
        price_eur=payload.price_eur,
        price_usd=payload.price_usd,
        note=payload.note,
        created_at=now_utc_iso(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/tax/opening-positions/{position_id}", status_code=204)
def delete_opening_position(position_id: int, db: Session = Depends(get_db)):
    row = db.query(OpeningPosition).filter(OpeningPosition.id == position_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Opening position not found")
    db.delete(row)
    db.commit()


# --- Report ---

@router.get("/tax/report")
async def get_tax_report(
    year: int = Query(default=None),
    wallet_ids: list[str] = Query(default=[]),
    mode: str = Query(default="private"),
    db: Session = Depends(get_db),
):
    if year is None:
        year = datetime.utcnow().year

    # read tax settings
    settings_rows = db.query(AppSetting).filter(AppSetting.key.like(f"{TAX_PREFIX}%")).all()
    settings_map: dict[str, Any] = {}
    for row in settings_rows:
        short = row.key[len(TAX_PREFIX):]
        settings_map[short] = _parse_json_value(row.value)

    country = settings_map.get("country") or "DE"
    method = settings_map.get("method") or "FIFO"

    try:
        report = tax_engine.calculate_tax_report(
            db=db,
            wallet_ids=wallet_ids,
            year=year,
            mode=mode,
            country=country,
            method=method,
        )
    except Exception:
        logger.exception("Tax report calculation failed")
        raise

    report["meta"] = {
        "year": year,
        "mode": mode,
        "country": country,
        "method": method,
        "wallet_ids": wallet_ids,
    }
    return report


@router.get("/tax/countries")
def get_countries():
    return tax_engine.TAX_RULES


@router.get("/tax/price")
async def get_price_for_date(date: str = Query(...), db: Session = Depends(get_db)):
    from ...services.coingecko import get_price_for_date as _get_price
    return await _get_price(db, date)
