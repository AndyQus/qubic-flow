DONATION_ADDRESS = "CCCJKFMDTUFFWDCRBFNHMQRYOBABEKBDUZWEJMARUETQPTFZWBCJLYUGREXI"
DONATION_QU_PER_MONTH = 1_000_000
DONATION_QU_FOREVER = 100_000_000
TICKS_PER_DAY = 86_400


def parse_v2_transfers(pages: list[dict]) -> list[tuple[int, str, str, int]]:
    result = []
    for page_data in pages:
        for tick_group in (page_data.get("transactions") or []):
            tick_number = int(tick_group.get("tickNumber") or 0)
            for tx_data in (tick_group.get("transactions") or []):
                if not tx_data.get("moneyFlew", False):
                    continue
                tx = tx_data.get("transaction") or tx_data
                source = tx.get("sourceId") or tx.get("source") or ""
                dest   = tx.get("destId")   or tx.get("destination") or ""
                amount = int(tx.get("amount") or 0)
                if source and dest and amount > 0:
                    result.append((tick_number, source, dest, amount))
    return result


async def fetch_all_transfer_pages(rpc, address: str, from_tick: int, to_tick: int) -> list[dict]:
    pages = []
    page = 1
    while True:
        try:
            data = await rpc.get_transfer_transactions(address, from_tick, to_tick, page=page, page_size=100)
        except Exception:
            break
        pages.append(data)
        tick_groups = data.get("transactions") or []
        if not tick_groups:
            break
        total_pages = data.get("pagination", {}).get("totalPages", 1)
        if page >= total_pages:
            break
        page += 1
    return pages
