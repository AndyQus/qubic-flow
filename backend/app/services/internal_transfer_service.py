import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.event import Event
from ..models.wallet import Wallet

logger = logging.getLogger(__name__)


def recompute_internal_flags(db: Session) -> dict:
    """Re-derive ``events.is_internal`` from the wallets that are owned *now*.

    The flag is stored at sync time against the wallets known back then. A
    wallet added later (e.g. the new address after moving funds away from a
    compromised one) would leave the sender's outgoing rows marked external —
    the tax report would count the move as a sale. Deleting a wallet has the
    opposite effect. Exports already recompute this on the fly; this keeps the
    stored flag (tax report, balance history) consistent with them.
    """
    owned = [row[0] for row in db.query(Wallet.id).filter(Wallet.deleted_at.is_(None)).all()]
    to_internal = (
        db.query(Event)
        .filter(Event.is_internal == 0,
                Event.source_address.in_(owned),
                Event.destination_addr.in_(owned))
        .update({Event.is_internal: 1}, synchronize_session=False)
    )
    to_external = (
        db.query(Event)
        .filter(Event.is_internal == 1,
                or_(Event.source_address.is_(None), ~Event.source_address.in_(owned),
                    Event.destination_addr.is_(None), ~Event.destination_addr.in_(owned)))
        .update({Event.is_internal: 0}, synchronize_session=False)
    )
    db.commit()
    if to_internal or to_external:
        logger.info(f"Internal-transfer flags recomputed: {to_internal} → internal, {to_external} → external")
    return {"to_internal": to_internal, "to_external": to_external}
