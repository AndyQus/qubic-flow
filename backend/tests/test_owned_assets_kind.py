"""
Tests for RPCClient.get_owned_assets() share/token classification.

Assets issued by the QX smart contract itself (e.g. QX, QEARN, QVAULT) are
classified as "share"; assets issued by any other identity (community
project tokens like CFB, QFT) are classified as "token".
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.qubic_client import RPCClient

QX_ISSUER = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFXIB"
OTHER_ISSUER = "CFBMEMZOIDEXQAUXYYSZIURADQLAPWPMNJXQSNVQZAHYVOPYUKKJBJUCTVJL"


def _owned_response(entries):
    return {"ownedAssets": [
        {"data": {
            "numberOfUnits": str(units),
            "issuedAsset": {"name": name, "issuerIdentity": issuer, "numberOfDecimalPlaces": 0},
            "managingContractIndex": 1,
        }} for name, issuer, units in entries
    ]}


class TestOwnedAssetsKind:
    @pytest.mark.asyncio
    async def test_qx_issued_asset_is_share(self):
        client = RPCClient()
        resp = _owned_response([("QEARN", QX_ISSUER, 100)])
        with patch.object(RPCClient, "_request", new=AsyncMock(return_value=resp)):
            assets = await client.get_owned_assets("WALLET")
        assert assets[0]["kind"] == "share"

    @pytest.mark.asyncio
    async def test_externally_issued_asset_is_token(self):
        client = RPCClient()
        resp = _owned_response([("CFB", OTHER_ISSUER, 5000)])
        with patch.object(RPCClient, "_request", new=AsyncMock(return_value=resp)):
            assets = await client.get_owned_assets("WALLET")
        assert assets[0]["kind"] == "token"

    @pytest.mark.asyncio
    async def test_mixed_holdings_classified_independently(self):
        client = RPCClient()
        resp = _owned_response([("QX", QX_ISSUER, 3), ("CFB", OTHER_ISSUER, 1000)])
        with patch.object(RPCClient, "_request", new=AsyncMock(return_value=resp)):
            assets = await client.get_owned_assets("WALLET")
        kinds = {a["name"]: a["kind"] for a in assets}
        assert kinds == {"QX": "share", "CFB": "token"}
