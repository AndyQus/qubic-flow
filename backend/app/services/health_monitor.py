import time
import logging
import httpx
from ..database import SessionLocal
from ..models.node import Node
from ..utils.time import now_utc_iso
from ..websocket.manager import manager
from ..utils.log_buffer import log_buffer
from . import rate_limit

logger = logging.getLogger(__name__)

# While the user's own Home Node is healthy, public nodes are only standby —
# probing them every 30 s would just spend the shared per-IP budget.
PUBLIC_STANDBY_CHECK_S = 300


def _seconds_since(iso: str | None) -> float:
    from datetime import datetime, timezone
    if not iso:
        return float("inf")
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()
    except ValueError:
        return float("inf")


async def check_nodes():
    db = SessionLocal()
    try:
        nodes = db.query(Node).filter(Node.is_active == 1).all()
        home_online = any(n.node_type == "HOME_NODE" and n.health_status == "ONLINE" for n in nodes)
        for node in nodes:
            if rate_limit.is_public_host(rate_limit._host(node.url)):
                # host is pausing us after a 429 — not the node's fault, keep its status
                if rate_limit.cooling_down(node.url):
                    continue
                if home_online and _seconds_since(node.last_checked) < PUBLIC_STANDBY_CHECK_S:
                    continue
            await _check_node(db, node)
    finally:
        db.close()


async def check_node_by_id(node_id: int):
    db = SessionLocal()
    try:
        node = db.query(Node).filter(Node.id == node_id).first()
        if node:
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
    # SSL-Verify nur für öffentliche RPCs; BOB & HOME_NODE laufen oft im LAN
    # mit http oder selbstsignierten Zertifikaten.
    verify = node.node_type == "RPC"
    try:
        await rate_limit.acquire(base)
        if node.node_type == "BOB_NODE":
            # Try JSON-RPC first (qubic_getTickNumber), fall back to REST /status
            tick = 0
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    rpc_r = await client.post(
                        f"{base}/qubic",
                        json={"jsonrpc": "2.0", "id": 1, "method": "qubic_getTickNumber"},
                        timeout=10,
                    )
                    rpc_r.raise_for_status()
                    rpc_data = rpc_r.json()
                    if not rpc_data.get("error") and rpc_data.get("result") is not None:
                        tick = int(rpc_data["result"] or 0)
            except Exception:
                pass
            if tick == 0:
                async with httpx.AsyncClient(verify=False) as client:
                    r = await client.get(url, timeout=10)
                    r.raise_for_status()
                    data = r.json()
                    tick = int(
                        data.get("currentTick") or
                        data.get("currentFetchingTick") or
                        data.get("verifiedTick") or 0
                    )
        else:
            async with httpx.AsyncClient(verify=verify) as client:
                r = await client.get(url, timeout=10)
                r.raise_for_status()
                data = r.json()
                tick = int(data.get("tickInfo", {}).get("tick", 0))
        elapsed = int((time.perf_counter() - start) * 1000)
        node.tick = tick
        node.response_time_ms = elapsed
        node.health_status = "ONLINE" if elapsed < 3000 else "DEGRADED"
        node.fail_count = 0
        node.last_error = None
        logger.info(f"Node {node.url}: {node.health_status} ({elapsed} ms, tick {tick})")
        log_buffer.add("INFO", "health", f"Node {node.url}: {node.health_status} ({elapsed} ms, tick {tick})")
    except Exception as e:
        if isinstance(e, httpx.HTTPStatusError):
            rate_limit.report(base, e.response.status_code, e.response.headers)
        node.fail_count = (node.fail_count or 0) + 1
        node.health_status = "OFFLINE" if node.fail_count >= 3 else "DEGRADED"
        node.last_error = str(e)[:500]
        logger.warning(f"Node {node.url} health check failed: {e}")
        log_buffer.add("WARNING", "health", f"Node {node.url} health check failed: {e}")

    node.last_checked = now_utc_iso()
    db.commit()

    await manager.broadcast("node.health", {
        "node_id": node.id,
        "url": node.url,
        "health_status": node.health_status,
        "tick": node.tick,
        "response_time_ms": node.response_time_ms,
        "fail_count": node.fail_count,
        "last_error": node.last_error,
    })
