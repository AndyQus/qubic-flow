from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from ...database import get_db
from ...models.node import Node
from ...schemas.node import NodeCreate, NodeOut
from ...utils.time import now_utc_iso
from ...services.sync_engine import get_active_sync_node_id, elect_active_sync_node
from ...utils.log_buffer import log_buffer
from ...services.health_monitor import check_node_by_id

router = APIRouter()


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


@router.delete("/nodes/{node_id}", status_code=204)
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    db.delete(node)
    db.commit()
