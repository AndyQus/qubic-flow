"""
Tests for the webhook notification service:
  - settings round-trip with the TX/EVENT type filter
  - notify_incoming respects the type filter and only posts wanted kinds
  - message text carries the event type on the very first line
"""
import pytest

from app.services import notification_service as ns


def _ev(id_, source_type, amount=1000):
    return {
        "id": id_,
        "wallet_id": "W",
        "amount_qubic": amount,
        "source_address": "EXT_ADDR",
        "destination_addr": "W",
        "tick_number": 42,
        "epoch": 170,
        "timestamp": "2026-07-04T10:00:00Z",
        "qubic_eur_rate": 0.000001,
        "qubic_usd_rate": 0.0000011,
        "source_type": source_type,
        "is_internal": 0,
    }


class TestSettings:
    def test_defaults_include_type_filter(self, db):
        cfg = ns.get_notify_settings(db)
        assert cfg["notify_tx"] is True
        assert cfg["notify_event"] is True

    def test_save_and_reload_type_filter(self, db):
        ns.save_notify_settings(db, {"notify_tx": True, "notify_event": False})
        cfg = ns.get_notify_settings(db)
        assert cfg["notify_tx"] is True
        assert cfg["notify_event"] is False


class TestTypeFilter:
    @pytest.mark.asyncio
    async def test_only_tx_when_events_unchecked(self, db, monkeypatch):
        ns.save_notify_settings(db, {
            "enabled": True, "webhook_url": "https://example.invalid/hook",
            "notify_tx": True, "notify_event": False,
        })
        sent = []

        async def fake_post(url, fmt, ev, wallet_label):
            sent.append(ev["id"])

        monkeypatch.setattr(ns, "_post_webhook", fake_post)
        await ns.notify_incoming(db, [_ev("tx1", "TX"), _ev("ev1", "EVENT")])
        assert sent == ["tx1"]

    @pytest.mark.asyncio
    async def test_only_events_when_tx_unchecked(self, db, monkeypatch):
        ns.save_notify_settings(db, {
            "enabled": True, "webhook_url": "https://example.invalid/hook",
            "notify_tx": False, "notify_event": True,
        })
        sent = []

        async def fake_post(url, fmt, ev, wallet_label):
            sent.append(ev["id"])

        monkeypatch.setattr(ns, "_post_webhook", fake_post)
        await ns.notify_incoming(db, [_ev("tx1", "TX"), _ev("ev1", "EVENT")])
        assert sent == ["ev1"]


class TestMessageText:
    def test_type_is_on_first_line(self):
        text_tx = ns._build_text(_ev("tx1", "TX"), "My wallet")
        text_ev = ns._build_text(_ev("ev1", "EVENT"), "My wallet")
        assert text_tx.splitlines()[0].startswith("[TX]")
        assert text_ev.splitlines()[0].startswith("[SC EVENT]")

    def test_text_contains_full_record(self):
        text = ns._build_text(_ev("tx1", "TX"), "My wallet")
        for fragment in ("EXT_ADDR", "Tick: 42", "Epoch: 170", "2026-07-04", "TxID: tx1"):
            assert fragment in text
