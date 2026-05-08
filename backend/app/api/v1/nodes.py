from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from ...database import get_db, SessionLocal
from ...models.node import Node
from ...schemas.node import NodeCreate, NodeOut
from ...utils.time import now_utc_iso
from ...services.sync_engine import get_active_sync_node_id, elect_active_sync_node
from ...utils.log_buffer import log_buffer
from ...services.health_monitor import check_node_by_id

router = APIRouter()

_sync_running = False
_diagnose_running = False


class NodeReorder(BaseModel):
    order: List[int]


@router.get("/nodes/logs/error-check")
async def logs_error_check():
    return {"has_error": any(e["level"] == "ERROR" for e in log_buffer.get(50))}


@router.get("/nodes/logs")
async def get_logs():
    return log_buffer.get(1000)


@router.get("/nodes", response_model=list[NodeOut])
def list_nodes(db: Session = Depends(get_db)):
    active_id = get_active_sync_node_id()
    nodes = db.query(Node).order_by(Node.priority).all()
    result = []
    for n in nodes:
        out = NodeOut.model_validate(n)
        out.is_sync_active = (n.id == active_id)
        result.append(out)
    return result


@router.post("/nodes", response_model=NodeOut, status_code=201)
def create_node(payload: NodeCreate, db: Session = Depends(get_db)):
    if db.query(Node).filter(Node.url == payload.url).first():
        raise HTTPException(status_code=409, detail="Node URL already exists")
    node = Node(
        url=payload.url,
        node_type=payload.node_type,
        label=payload.label,
        priority=payload.priority,
        notes=payload.notes,
        health_status="ONLINE",
        is_active=1,
        last_checked=now_utc_iso(),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


@router.put("/nodes/reorder")
def reorder_nodes(payload: NodeReorder, db: Session = Depends(get_db)):
    for priority, node_id in enumerate(payload.order, start=1):
        node = db.query(Node).filter(Node.id == node_id).first()
        if node:
            node.priority = priority
    db.commit()
    return {"ok": True}


@router.put("/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: int, payload: NodeCreate, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    node.url = payload.url
    node.node_type = payload.node_type
    node.label = payload.label
    node.priority = payload.priority
    node.notes = payload.notes
    db.commit()
    db.refresh(node)
    return node


@router.patch("/nodes/{node_id}/toggle", response_model=NodeOut)
def toggle_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    node.is_active = 0 if node.is_active else 1
    db.commit()
    db.refresh(node)
    elect_active_sync_node(db)
    return node


@router.post("/nodes/{node_id}/check-now", status_code=202)
async def check_node_now(node_id: int):
    import asyncio
    asyncio.create_task(check_node_by_id(node_id))
    return {"queued": True}


@router.post("/nodes/sync-now", status_code=202)
async def sync_now():
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=429, detail="Sync already running")
    import asyncio
    from ...services.sync_engine import sync_all_wallets

    async def _wrapper():
        global _sync_running
        _sync_running = True
        try:
            await sync_all_wallets()
        finally:
            _sync_running = False

    asyncio.create_task(_wrapper())
    log_buffer.add("INFO", "sync", "Manual sync triggered via UI")
    return {"queued": True}


@router.post("/nodes/diagnose", status_code=202)
async def diagnose():
    global _diagnose_running
    if _diagnose_running:
        raise HTTPException(status_code=429, detail="Diagnosis already running")
    import asyncio

    async def _wrapper():
        global _diagnose_running
        _diagnose_running = True
        try:
            await _run_diagnose()
        finally:
            _diagnose_running = False

    asyncio.create_task(_wrapper())
    return {"queued": True}


async def _run_diagnose():
    from ...services.qubic_client import BOBClient, RPCClient
    from ...services.sync_engine import _get_event_client, _get_rpc_client
    from ...models.node import Node as NodeModel

    db = SessionLocal()
    try:
        log_buffer.add("INFO", "diag", "--- Diagnosis started ---")

        nodes = db.query(NodeModel).filter(NodeModel.is_active == 1).order_by(NodeModel.priority).all()
        for n in nodes:
            client = BOBClient(n.url) if n.node_type == "BOB_NODE" else RPCClient(n.url)
            try:
                tick = await client.get_current_tick()
                log_buffer.add("INFO", "diag", f"{n.node_type} reachable — tick {tick}", node=n.url)
            except Exception as e:
                log_buffer.add("ERROR", "diag", f"{n.node_type} unreachable: {e}", node=n.url)

        # Event client (BOB or RPC)
        try:
            event_client = await _get_event_client(db)
            ec_type = "BOB" if isinstance(event_client, BOBClient) else "RPC"
            ec_url = getattr(event_client, 'base_url', '?')
            tick = await event_client.get_current_tick()

            if isinstance(event_client, BOBClient):
                raw, actual_tick = await event_client._fetch_raw(
                    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', tick - 2, tick
                )
                log_buffer.add("INFO", "diag",
                    f"Event source: {ec_type} — tick {actual_tick} — {len(raw)} transfers in network",
                    node=ec_url)
            else:
                log_buffer.add("INFO", "diag",
                    f"Event source: {ec_type} — tick {tick}",
                    node=ec_url)
        except Exception as e:
            log_buffer.add("ERROR", "diag", f"Event client error: {e}")

        # RPC for history
        try:
            rpc = _get_rpc_client(db)
            tick = await rpc.get_current_tick()
            log_buffer.add("INFO", "diag", f"RPC (history) reachable — tick {tick}", node=rpc.base_url)
        except Exception as e:
            log_buffer.add("ERROR", "diag", f"RPC (history) unreachable: {e}")

        log_buffer.add("INFO", "diag", "--- Diagnosis complete ---")
    finally:
        db.close()


@router.delete("/nodes/{node_id}", status_code=204)
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    db.delete(node)
    db.commit()
