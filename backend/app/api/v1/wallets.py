from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ...database import get_db
from ...models.wallet import Wallet
from ...models.sync_state import SyncState
from ...schemas.wallet import WalletCreate, WalletUpdate, WalletOut
from ...utils.time import now_utc_iso
from ...services.balance_service import initialize_wallet_balance
from ...services.sync_engine import sync_wallet_tx
from ...services.qubic_client import RPCClient

router = APIRouter()


@router.get("/wallets", response_model=list[WalletOut])
def list_wallets(db: Session = Depends(get_db)):
    wallets = db.query(Wallet).filter(Wallet.deleted_at.is_(None)).all()
    states = {s.wallet_id: s for s in db.query(SyncState).all()}
    result = []
    for w in wallets:
        state = states.get(w.id)
        out = WalletOut.model_validate(w)
        out.total_events = state.total_events if state else None
        result.append(out)
    return result


@router.post("/wallets", response_model=WalletOut, status_code=201)
async def create_wallet(payload: WalletCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if db.query(Wallet).filter(Wallet.id == payload.id).first():
        raise HTTPException(status_code=409, detail="Wallet already exists")
    now = now_utc_iso()
    wallet = Wallet(
        id=payload.id,
        label=payload.label,
        note=payload.note,
        owner=payload.owner,
        function=payload.function,
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


async def _run_tx_resync(wallet_id: str):
    from ...database import SessionLocal
    db = SessionLocal()
    try:
        client = RPCClient()
        current_tick = await client.get_current_tick()
        await sync_wallet_tx(db, wallet_id, current_tick, client)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"TX resync failed for {wallet_id}: {e}", exc_info=True)
    finally:
        db.close()


@router.post("/wallets/{wallet_id}/resync-tx", status_code=204)
async def resync_tx(wallet_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Reset last_tx_tick to 0 and immediately trigger a background TX sync."""
    state = db.query(SyncState).filter(SyncState.wallet_id == wallet_id).first()
    if not state:
        raise HTTPException(status_code=404, detail="Sync state not found")
    state.last_tx_tick = 0
    db.commit()
    background_tasks.add_task(_run_tx_resync, wallet_id)


async def _run_resync_all():
    try:
        from ...services.sync_engine import sync_all_wallets
        await sync_all_wallets()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Resync-all failed: {e}", exc_info=True)


@router.post("/wallets/resync-all", status_code=202)
async def resync_all(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Reset event+TX sync progress for every active wallet and trigger a full
    re-sync in the background. Events and transactions are deduplicated by
    composite primary key, so previously imported data is not duplicated — only
    missing records get filled in.

    Also runs a one-shot re-classification: legacy rows with
    ``log_type = 0`` (QuTransfer) that were stored as ``source_type = 'EVENT'``
    are flipped to ``'TX'`` so the stats buckets are consistent with the new
    import logic."""
    from ...models.event import Event
    from ...models.address_label import AddressLabel
    # Addresses that count as smart contracts or token issuers (from the
    # Qubic assets registry). Transfers touching these stay EVENT; all other
    # logType=0 QuTransfers move to TX.
    sc_addrs = [row[0] for row in db.query(AddressLabel.address)
                .filter(
                    (AddressLabel.category == "smart_contract")
                    | (AddressLabel.source.in_(["smart_contract", "issuance", "token"]))
                ).all()]
    q = db.query(Event).filter(Event.source_type == "EVENT", Event.log_type == 0)
    if sc_addrs:
        q = q.filter(~Event.source_address.in_(sc_addrs),
                     ~Event.destination_addr.in_(sc_addrs))
    reclassified_to_tx = q.update({Event.source_type: "TX"}, synchronize_session=False)
    # Also flip any legacy TX rows that actually touch a smart contract back to EVENT
    reclassified_to_event = 0
    if sc_addrs:
        reclassified_to_event = (
            db.query(Event)
            .filter(Event.source_type == "TX", Event.log_type == 0)
            .filter(Event.source_address.in_(sc_addrs) | Event.destination_addr.in_(sc_addrs))
            .update({Event.source_type: "EVENT"}, synchronize_session=False)
        )
    reclassified = reclassified_to_tx + reclassified_to_event
    states = db.query(SyncState).all()
    for s in states:
        s.last_tick = 0
        s.last_tx_tick = 0
    db.commit()
    background_tasks.add_task(_run_resync_all)
    return {"wallets_queued": len(states), "reclassified": reclassified}


@router.delete("/wallets/{wallet_id}", status_code=204)
def delete_wallet(wallet_id: str, db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id, Wallet.deleted_at.is_(None)).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    wallet.deleted_at = now_utc_iso()
    wallet.active = 0
    db.commit()
