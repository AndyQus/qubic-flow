import re
import logging
import httpx
from sqlalchemy.orm import Session
from ..models.address_label import AddressLabel
from ..utils.time import now_utc_iso

logger = logging.getLogger(__name__)

_ADDRESS_LABELS_URL    = "https://static.qubic.org/v1/general/data/address_labels.json"
_TOKENS_URL            = "https://static.qubic.org/v1/general/data/tokens.json"
_SMART_CONTRACTS_URL   = "https://static.qubic.org/v1/general/data/smart_contracts.json"
_EXCHANGES_URL         = "https://static.qubic.org/v1/general/data/exchanges.json"
_ISSUANCES_URL         = "https://rpc.qubic.org/live/v1/assets/issuances"
_TOKEN_CATEGORIES_URL  = "https://static.qubic.org/v1/explorer/token_categories.json"


def _resolve_category(name: str | None, categories: list, default_id: str) -> str:
    if not name:
        return default_id
    for cat in categories:
        regex = cat.get("rules", {}).get("nameRegex")
        if regex and re.match(regex, name):
            return cat["id"]
    return default_id


async def sync_labels(db: Session):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r_cats = await client.get(_TOKEN_CATEGORIES_URL)
            r_cats.raise_for_status()
            cats_data = r_cats.json()

            r_labels = await client.get(_ADDRESS_LABELS_URL)
            r_labels.raise_for_status()
            labels_data = r_labels.json()

            r_tokens = await client.get(_TOKENS_URL)
            r_tokens.raise_for_status()
            tokens_data = r_tokens.json()

            r_sc = await client.get(_SMART_CONTRACTS_URL)
            r_sc.raise_for_status()
            sc_data = r_sc.json()

            r_ex = await client.get(_EXCHANGES_URL)
            r_ex.raise_for_status()
            ex_data = r_ex.json()

            r_issuances = await client.get(_ISSUANCES_URL)
            r_issuances.raise_for_status()
            issuances_data = r_issuances.json()
    except Exception as e:
        logger.warning(f"label_service fetch failed: {e}")
        return

    categories = cats_data.get("categories", [])
    default_category_id = cats_data.get("defaultCategoryId", "standard")

    records: dict[str, AddressLabel] = {}
    now = now_utc_iso()

    for entry in issuances_data.get("assets", []):
        data = entry.get("data", {})
        addr = data.get("issuerIdentity")
        if not addr:
            continue
        name = data.get("name")
        cat = _resolve_category(name, categories, default_category_id)
        records[addr] = AddressLabel(
            address=addr,
            name=name,
            label=None,
            website=None,
            category=cat,
            asset_type=data.get("type"),
            decimal_places=data.get("numberOfDecimalPlaces"),
            universe_index=entry.get("universeIndex"),
            source="issuance",
            updated_at=now,
        )

    for sc in sc_data.get("smart_contracts", []):
        addr = sc.get("address")
        if not addr:
            continue
        records[addr] = AddressLabel(
            address=addr,
            name=sc.get("name"),
            label=sc.get("label"),
            website=sc.get("website") or sc.get("githubUrl"),
            category="smart_contract",
            asset_type=None,
            decimal_places=None,
            universe_index=sc.get("contractIndex"),
            source="smart_contract",
            updated_at=now,
        )

    for ex in ex_data.get("exchanges", []):
        addr = ex.get("address")
        if not addr:
            continue
        name = ex.get("name")
        records[addr] = AddressLabel(
            address=addr,
            name=name,
            label=name,
            website=None,
            category="exchange",
            asset_type=None,
            decimal_places=None,
            universe_index=None,
            source="exchange",
            updated_at=now,
        )

    for token in tokens_data.get("tokens", []):
        addr = token.get("issuer")
        if not addr:
            continue
        name = token.get("name")
        cat = _resolve_category(name, categories, default_category_id)
        existing = records.get(addr)
        records[addr] = AddressLabel(
            address=addr,
            name=name,
            label=existing.label if existing else None,
            website=token.get("website"),
            category=cat,
            asset_type=existing.asset_type if existing else None,
            decimal_places=existing.decimal_places if existing else None,
            universe_index=existing.universe_index if existing else None,
            source="token",
            updated_at=now,
        )

    for entry in labels_data.get("address_labels", []):
        addr = entry.get("address")
        if not addr:
            continue
        label_text = entry.get("label")
        existing = records.get(addr)
        records[addr] = AddressLabel(
            address=addr,
            name=existing.name if existing else None,
            label=label_text,
            website=existing.website if existing else None,
            category=existing.category if existing else default_category_id,
            asset_type=existing.asset_type if existing else None,
            decimal_places=existing.decimal_places if existing else None,
            universe_index=existing.universe_index if existing else None,
            source="address_label",
            updated_at=now,
        )

    for record in records.values():
        db.merge(record)

    db.commit()
    logger.info(f"label_service: synced {len(records)} address labels")


def get_label(db: Session, address: str) -> str | None:
    if not address:
        return None
    rec = db.query(AddressLabel).filter(AddressLabel.address == address).first()
    if not rec:
        return None
    return rec.label or rec.name or None
