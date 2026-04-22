from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ...database import get_db
from ...models.wallet import Wallet
from ...schemas.wallet import WalletCreate, WalletUpdate, WalletOut
from ...utils.time import now_utc_iso
from ...services.balance_service import initialize_wallet_balance

router = APIRouter()


@router.get("/wallets", response_model=list[WalletOut])
def list_wallets(db: Session = Depends(get_db)):
    return db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()


@router.post("/wallets", response_model=WalletOut, status_code=201)
async def create_wallet(payload: WalletCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if db.query(Wallet).filter(Wallet.id == payload.id).first():
        raise HTTPException(status_code=409, detail="Wallet already exists")
    now = now_utc_iso()
    wallet = Wallet(
        id=payload.id,
        label=payload.label,
        note=payload.note,
        wallet_type=payload.wallet_type,
        active=1,
        created_at=now,
        updated_at=now,
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    background_tasks.add_task(initialize_wallet_balance, wallet.id)
    return wallet


@router.put("/wallets/{wallet_id}", response_model=WalletOut)
def update_wallet(wallet_id: str, payload: WalletUpdate, db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id, Wallet.deleted_at.is_(None)).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(wallet, k, v)
    wallet.updated_at = now_utc_iso()
    db.commit()
    db.refresh(wallet)
    return wallet


@router.delete("/wallets/{wallet_id}", status_code=204)
def delete_wallet(wallet_id: str, db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id, Wallet.deleted_at.is_(None)).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    wallet.deleted_at = now_utc_iso()
    wallet.active = 0
    db.commit()
