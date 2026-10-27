"""Outbound throttle for public Qubic APIs (shared per-IP budget)."""
import asyncio
import time

import pytest

from app.services import rate_limit


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    rate_limit.reset_for_tests()
    monkeypatch.setattr(rate_limit.settings, "public_rpc_rate_limit_per_min", 600)  # 10/s keeps tests fast
    monkeypatch.setattr(rate_limit.settings, "public_rpc_burst", 3)
    yield
    rate_limit.reset_for_tests()


def test_private_and_lan_hosts_are_not_throttled():
    for url in ("http://192.168.178.172:8090", "http://localhost:8000", "http://umbrel.local",
                "http://qubic-home-node_edge:8090", "http://10.0.0.5", "http://abc.onion"):
        assert not rate_limit.is_public_host(rate_limit._host(url)), url
    assert rate_limit.is_public_host("rpc.qubic.org")


def test_burst_then_steady_rate():
    async def run():
        start = time.monotonic()
        for _ in range(5):  # burst 3, then 2 more at 10/s
            await rate_limit.acquire("https://rpc.qubic.org/v1/tick-info")
        return time.monotonic() - start
    elapsed = asyncio.run(run())
    assert 0.15 <= elapsed < 1.0


def test_429_pauses_all_requests_to_that_host():
    async def run():
        url = "https://rpc.qubic.org/v1/tick-info"
        rate_limit.report(url, 429, {"retry-after": "1"})
        assert rate_limit.cooling_down(url)
        assert not rate_limit.cooling_down("https://bobnet.qubic.li/status")
        start = time.monotonic()
        await asyncio.gather(*(rate_limit.acquire(url) for _ in range(2)))
        return time.monotonic() - start
    assert asyncio.run(run()) >= 0.9


def test_429_from_private_host_is_ignored():
    rate_limit.report("http://192.168.1.10:8090/v1/tick-info", 429, {})
    assert not rate_limit.cooling_down("http://192.168.1.10:8090/v1/tick-info")


def test_503_without_retry_after_is_no_cooldown():
    rate_limit.report("https://rpc.qubic.org/x", 503, {})
    assert not rate_limit.cooling_down("https://rpc.qubic.org/x")


def test_status_reports_hosts():
    asyncio.run(rate_limit.acquire("https://rpc.qubic.org/v1/tick-info"))
    st = rate_limit.status()
    assert st["hosts"]["rpc.qubic.org"]["requests_last_min"] == 1
