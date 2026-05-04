import logging
from ..database import SessionLocal
from ..models.wallet import Wallet
from ..utils.time import now_utc_iso
from .qubic_client import RPCClient
from .sync_engine import _get_active_client

logger = logging.getLogger(__name__)


async def initialize_wallet_balance(wallet_id: str):
    """Called as a background task after wallet creation.
    Fetches the current live balance and stores it as the tracking baseline."""
    db = SessionLocal()
    try:
        client = _get_active_client(db)
        balance = await client.get_balance(wallet_id)
        if balance is None:
            logger.warning(f"Could not fetch initial balance for {wallet_id}")
            return
        current_tick = await client.get_current_tick()
        wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
        if wallet:
            wallet.balance = balance
            wallet.balance_updated_at = now_utc_iso()
            wallet.balance_since_tick = current_tick
            wallet.balance_live = balance
            wallet.balance_live_at = now_utc_iso()
            db.commit()
            logger.info(f"Initialized balance for {wallet_id}: {balance} QUBIC at tick {current_tick}")
    except Exception as e:
        logger.error(f"initialize_wallet_balance failed for {wallet_id}: {e}")
    finally:
        db.close()


async def check_all_balances():
    """Hourly scheduler job — fetch live balance for every wallet and reconcile.

    For each wallet:
    1. Fetch live balance from RPC and store in balance_live.
    2. If computed balance (balance) and live balance differ, trigger a targeted
       re-sync from balance_since_tick so missing events are re-imported without
       doing a full reset of the wallet's entire history.
    3. After re-sync the next hourly run will re-compare and confirm the fix.
    """
    from .sync_engine import _trigger_balance_resync

    db = SessionLocal()
    try:
        client = _get_active_client(db)
        current_tick = await client.get_current_tick()
        wallets = db.query(Wallet).filter(Wallet.active == 1, Wallet.deleted_at.is_(None)).all()
        updated = 0
        mismatches = 0
        for wallet in wallets:
            try:
                balance = await client.get_balance(wallet.id)
                if balance is None:
                    continue
                if wallet.balance is None:
                    wallet.balance = balance
                    wallet.balance_updated_at = now_utc_iso()
                    wallet.balance_since_tick = current_tick
                wallet.balance_live = balance
                wallet.balance_live_at = now_utc_iso()
                updated += 1

                # Reconciliation: if computed balance diverges from live balance,
                # reset the sync pointer back to balance_since_tick so the normal
                # 60-second sync loop re-imports whatever events are missing.
                if (
                    wallet.balance is not None
                    and wallet.balance_live is not None
                    and wallet.balance != wallet.balance_live
                    and wallet.balance_since_tick is not None
                ):
                    mismatches += 1
                    logger.warning(
                        f"Balance mismatch for {wallet.id}: "
                        f"computed={wallet.balance}, live={wallet.balance_live} "
                        f"— triggering re-sync from tick {wallet.balance_since_tick}"
                    )
                    await _trigger_balance_resync(db, wallet.id, wallet.balance_since_tick, current_tick)

            except Exception as e:
                logger.warning(f"Balance check failed for {wallet.id}: {e}")
        if updated:
            db.commit()
        logger.info(
            f"Balance check complete: updated {updated}/{len(wallets)} wallets"
            + (f", {mismatches} mismatch(es) — re-sync triggered" if mismatches else "")
        )
    except Exception as e:
        logger.error(f"check_all_balances failed: {e}")
    finally:
        db.close()
