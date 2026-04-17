from datetime import datetime, timezone


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def unix_ms_to_iso(ms: str | int) -> str:
    """Qubic API timestamp (unix-ms as string) -> ISO 8601 UTC."""
    ts = int(ms) / 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def iso_to_date(iso: str) -> str:
    """ISO 8601 -> YYYY-MM-DD (for price cache lookup)."""
    return iso[:10]
