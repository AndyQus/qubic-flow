import time
import logging
import httpx
from ..database import SessionLocal
from ..models.node import Node
from ..utils.time import now_utc_iso
from ..websocket.manager import manager

logger = logging.getLogger(__name__)


async def check_nodes():
    db = SessionLocal()
    try:
        nodes = db.query(Node).filter(Node.is_active == 1).all()
        for node in nodes:
            await _check_node(db, node)
    finally:
        db.close()


async def _check_node(db, node: Node):
    base = node.url.rstrip('/')
    if node.node_type == "BOB_NODE":
        url = f"{base}/status"
    else:
        url = f"{base}/v1/tick-info"
    start = time.perf_counter()
    verify = node.node_type != "BOB_NODE"
    try:
        async with httpx.AsyncClient(verify=verify) as client:
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            if node.node_type == "BOB_NODE":
                tick = int(
                    data.get("currentTick") or
                    data.get("currentFetchingTick") or
                    data.get("verifiedTick") or 0
                )
            else:
                tick = int(data.get("tickInfo", {}).get("tick", 0))
            elapsed = int((time.perf_counter() - start) * 1000)
            node.tick = tick
            node.response_time_ms = elapsed
            node.health_status = "ONLINE" if elapsed < 3000 else "DEGRADED"
            node.fail_count = 0
    except Exception as e:
        node.fail_count = (node.fail_count or 0) + 1
        node.health_status = "OFFLINE" if node.fail_count >= 3 else "DEGRADED"
        logger.warning(f"Node {node.url} health check failed: {e}")

    node.last_checked = now_utc_iso()
    db.commit()

    await manager.broadcast("node.health", {
        "node_id": node.id,
        "url": node.url,
        "health_status": node.health_status,
        "tick": node.tick,
        "response_time_ms": node.response_time_ms,
    })
