from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from ...database import get_db
from ...models.event import Event
from ...models.sync_state import SyncState
from ...models.node import Node

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    events_total = db.query(func.count(Event.id)).scalar() or 0
    failed_syncs = db.query(func.count(SyncState.wallet_id)).filter(SyncState.status == "FAILED").scalar() or 0
    nodes_online = db.query(func.count(Node.id)).filter(Node.health_status == "ONLINE").scalar() or 0
    nodes_total = db.query(func.count(Node.id)).scalar() or 0
    return {
        "events_total": events_total,
        "failed_syncs": failed_syncs,
        "nodes_online": nodes_online,
        "nodes_total": nodes_total,
    }
