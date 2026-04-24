"""
Diagnose-Skript: BOB-Node Live-Test
Fuehrt echte HTTP-Anfragen gegen die konfigurierten BOB-Nodes durch.

Aufruf:
    python -m tests.diagnose_bob
    python -m tests.diagnose_bob <wallet_adresse>
"""
import asyncio
import sys
import json
import httpx
from datetime import datetime

BOB_NODES = [
    "https://bobnet.qubic.li",
]

SEP = "-" * 60


async def check_status(session: httpx.AsyncClient, base: str) -> dict:
    url = f"{base}/status"
    try:
        r = await session.get(url, timeout=10)
        r.raise_for_status()
        return {"ok": True, "status": r.status_code, "data": r.json()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def check_transfers(session: httpx.AsyncClient, base: str, wallet_id: str, current_tick: int) -> dict:
    url = f"{base}/getQuTransfersForIdentity"
    from_tick = max(1, current_tick - 999)  # BOB-Limit: toTick - fromTick < 1000
    payload = {"fromTick": from_tick, "toTick": current_tick, "identity": wallet_id}
    try:
        r = await session.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        api_error = data.get("error")
        if api_error and not data.get("transfers"):
            return {"ok": False, "error": f"API-Fehler: {api_error}"}
        transfers = data.get("transfers") or []
        return {"ok": True, "count": len(transfers), "sample": transfers[:2], "raw_keys": list(data.keys())}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def check_balance(session: httpx.AsyncClient, base: str, wallet_id: str) -> dict:
    url = f"{base}/balance/{wallet_id}"
    try:
        r = await session.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def check_epoch_info(session: httpx.AsyncClient, base: str, epoch: int) -> dict:
    url = f"{base}/epochinfo/{epoch}"
    try:
        r = await session.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def check_jsonrpc(session: httpx.AsyncClient, base: str) -> dict:
    url = f"{base}/qubic"
    payload = {"jsonrpc": "2.0", "method": "qubic_getTickNumber", "params": [], "id": 1}
    try:
        r = await session.post(url, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def check_jsonrpc_transfers(session: httpx.AsyncClient, base: str, wallet_id: str, current_tick: int) -> dict:
    url = f"{base}/qubic"
    from_tick = max(1, current_tick - 999)  # BOB-Limit: toTick - fromTick < 1000
    payload = {
        "jsonrpc": "2.0",
        "method": "qubic_getQuTransfers",
        "params": [{"identity": wallet_id, "fromTick": from_tick, "toTick": current_tick}],
        "id": 2,
    }
    try:
        r = await session.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def get_wallet_from_db() -> str | None:
    """Liest die erste aktive Wallet aus der DB."""
    try:
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from app.database import SessionLocal
        from app.models.wallet import Wallet
        db = SessionLocal()
        w = db.query(Wallet).filter(Wallet.active == 1, Wallet.deleted_at.is_(None)).first()
        db.close()
        return w.id if w else None
    except Exception as e:
        print(f"  DB-Zugriff fehlgeschlagen: {e}")
        return None


async def main():
    wallet_id = sys.argv[1] if len(sys.argv) > 1 else None

    if not wallet_id:
        print("Lese Wallet-Adresse aus Datenbank...")
        wallet_id = await get_wallet_from_db()

    if not wallet_id:
        print("Keine Wallet-Adresse -- Uebergabe als Argument: python -m tests.diagnose_bob <ADRESSE>")
        wallet_id = "BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        print(f"  Verwende Dummy-Adresse: {wallet_id[:20]}...")

    print(f"\n{'='*60}")
    print(f"  QubicFlow BOB-Node Diagnose  --  {datetime.now().strftime('%H:%M:%S')}")
    print(f"  Wallet: {wallet_id[:20]}...{wallet_id[-5:]}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(verify=False) as session:
        for base in BOB_NODES:
            print(f"  Node: {base}")
            print(SEP)

            # 1. GET /status
            print("  [1] GET /status ...", end=" ", flush=True)
            status = await check_status(session, base)
            if status["ok"]:
                data = status["data"]
                tick = (data.get("currentTick") or data.get("currentFetchingTick")
                        or data.get("verifiedTick") or "?")
                epoch = data.get("currentEpoch") or data.get("epoch") or "?"
                print(f"OK  Tick={tick}  Epoch={epoch}")
                print(f"      Antwort-Keys: {list(data.keys())}")
                current_tick = int(tick) if str(tick).isdigit() else 50000000
            else:
                print(f"FEHLER  {status['error']}")
                print()
                continue

            # 2. POST /getQuTransfersForIdentity (korrigierter Endpunkt)
            print(f"  [2] POST /getQuTransfersForIdentity (letzte 5000 Ticks) ...", end=" ", flush=True)
            tx = await check_transfers(session, base, wallet_id, current_tick)
            if tx["ok"]:
                print(f"OK  {tx['count']} Transfers")
                print(f"      Antwort-Keys: {tx['raw_keys']}")
                if tx["sample"]:
                    print(f"      Erstes Transfer:")
                    sample = tx["sample"][0]
                    print(f"        Keys: {list(sample.keys())}")
                    msg = sample.get("message") or {}
                    print(f"        message-Keys: {list(msg.keys())}")
                    print(f"        tick={sample.get('tick')}, logType={sample.get('logType')}")
                    print(f"        amount={msg.get('amount')}")
                    print(f"        source={msg.get('sourceId') or msg.get('source') or msg.get('from')}")
                    print(f"        dest={msg.get('destId') or msg.get('destination') or msg.get('to')}")
                else:
                    print("      Keine Transfers in diesem Tick-Fenster.")
            else:
                print(f"FEHLER  {tx['error']}")

            # 3. GET /tick/<tick>
            test_tick = current_tick - 100
            print(f"  [3] GET /tick/{test_tick} (Timestamp-Test) ...", end=" ", flush=True)
            try:
                r = await session.get(f"{base}/tick/{test_tick}", timeout=10)
                r.raise_for_status()
                d = r.json()
                tick_val = d.get("tick")
                ts = (d.get("timestamp") or
                      (tick_val.get("timestamp") if isinstance(tick_val, dict) else None) or
                      d.get("time") or d.get("tickTimestamp"))
                td = d.get("tickdata")
                print(f"OK  timestamp={ts}  tickdata={td}  Keys={list(d.keys())}")
            except Exception as e:
                print(f"FEHLER  {e}")

            # 4. GET /balance/<identity>
            print(f"  [4] GET /balance/<identity> ...", end=" ", flush=True)
            bal = await check_balance(session, base, wallet_id)
            if bal["ok"]:
                print(f"OK  Keys={list(bal['data'].keys())}")
            else:
                print(f"FEHLER  {bal['error']}")

            # 5. JSON-RPC: qubic_getTickNumber
            print(f"  [5] JSON-RPC POST /qubic (qubic_getTickNumber) ...", end=" ", flush=True)
            rpc = await check_jsonrpc(session, base)
            if rpc["ok"]:
                result = rpc["data"].get("result")
                print(f"OK  result={result}")
            else:
                print(f"FEHLER  {rpc['error']}")

            # 6. JSON-RPC: qubic_getQuTransfers
            print(f"  [6] JSON-RPC qubic_getQuTransfers (letzte 5000 Ticks) ...", end=" ", flush=True)
            rpc_tx = await check_jsonrpc_transfers(session, base, wallet_id, current_tick)
            if rpc_tx["ok"]:
                d = rpc_tx["data"]
                result = d.get("result")
                err = d.get("error")
                if err:
                    print(f"RPC-Fehler  code={err.get('code')}  msg={err.get('message')}")
                else:
                    count = len(result) if isinstance(result, list) else "?"
                    print(f"OK  {count} Transfers")
            else:
                print(f"FEHLER  {rpc_tx['error']}")

            print()

    print("Diagnose abgeschlossen.")


if __name__ == "__main__":
    asyncio.run(main())
