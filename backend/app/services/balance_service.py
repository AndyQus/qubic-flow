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
            db.commit()
            logger.info(f"Initialized balance for {wallet_id}: {balance} QUBIC at tick {current_tick}")
    except Exception as e:
        logger.error(f"initialize_wallet_balance failed for {wallet_id}: {e}")
    finally:
        db.close()


async def check_all_balances():
    """Daily scheduler job — fetch live balance for every wallet.
    Also initializes balance for wallets that have never been fetched."""
    db = SessionLocal()
    try:
        client = _get_active_client(db)
        current_tick = await client.get_current_tick()
        wallets = db.query(Wallet).filter(Wallet.active == 1, Wallet.deleted_at.is_(None)).all()
        updated = 0
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
            except Exception as e:
                logger.warning(f"Balance check failed for {wallet.id}: {e}")
        if updated:
            db.commit()
        logger.info(f"Balance check complete: updated {updated}/{len(wallets)} wallets")
    except Exception as e:
        logger.error(f"check_all_balances failed: {e}")
    finally:
        db.close()
