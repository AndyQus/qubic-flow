"""
Tests for the batch assets summary (portfolio Token/Shares view).
"""
import pytest

from app.models.wallet import Wallet
from app.services import asset_service


def _wallet(db, id_, label):
    db.add(Wallet(id=id_, label=label, wallet_type="PRIVATE", active=1, created_at="2026-01-01T00:00:00Z"))
    db.commit()


class FakeClient:
    def __init__(self, data):
        self.data = data
        self.calls = 0

    async def get_owned_assets(self, wallet_id):
        self.calls += 1
        return [dict(a) for a in self.data.get(wallet_id, [])]


@pytest.fixture(autouse=True)
def _patch_externals(monkeypatch):
    asset_service._owned_cache.clear()

    async def fake_price(issuer, name):
        return {"QX": 5.0}.get(name)  # CFB has no trades → None

    async def fake_qu_rate(db, date_str):
        return {"eur": 0.000002, "usd": 0.0000022}

    monkeypatch.setattr(asset_service, "get_last_trade_price", fake_price)
    monkeypatch.setattr(asset_service, "get_price_for_date", fake_qu_rate)


class TestAssetsSummary:
    @pytest.mark.asyncio
    async def test_totals_per_wallet(self, db):
        _wallet(db, "W1", "Wallet 1")
        _wallet(db, "W2", "Wallet 2")
        client = FakeClient({
            "W1": [
                {"name": "QX", "issuer": "ISSUER_QX", "units": 10, "decimals": 0},
                {"name": "CFB", "issuer": "ISSUER_CFB", "units": 1000, "decimals": 0},
            ],
            "W2": [],
        })

        summary = await asset_service.build_assets_summary(db, client)

        w1 = summary["wallets"]["W1"]
        assert len(w1["assets"]) == 2
        # QX: 10 × 5 QU = 50 QU; CFB has no price → excluded from totals
        assert w1["total_value_qubic"] == 50
        assert w1["total_value_eur"] == pytest.approx(50 * 0.000002, abs=1e-6)
        qx = next(a for a in w1["assets"] if a["name"] == "QX")
        cfb = next(a for a in w1["assets"] if a["name"] == "CFB")
        assert qx["price_qu"] == 5.0
        assert cfb["price_qu"] is None
        assert cfb["value_qubic"] is None

        assert summary["wallets"]["W2"]["assets"] == []
        assert summary["wallets"]["W2"]["total_value_qubic"] == 0

    @pytest.mark.asyncio
    async def test_owned_assets_are_cached(self, db):
        _wallet(db, "W1", "Wallet 1")
        client = FakeClient({"W1": [{"name": "QX", "issuer": "I", "units": 1, "decimals": 0}]})

        await asset_service.build_assets_summary(db, client)
        await asset_service.build_assets_summary(db, client)
        assert client.calls == 1  # second run served from the owned-assets cache

    @pytest.mark.asyncio
    async def test_failed_lookup_yields_empty_assets(self, db):
        _wallet(db, "W1", "Wallet 1")

        class BrokenClient:
            async def get_owned_assets(self, wallet_id):
                raise RuntimeError("rpc down")

        summary = await asset_service.build_assets_summary(db, BrokenClient())
        assert summary["wallets"]["W1"]["assets"] == []
