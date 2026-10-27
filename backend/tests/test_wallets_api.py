"""
Integration tests for the wallets REST API.

Uses FastAPI TestClient (synchronous) against the in-memory SQLite DB via the
`client` fixture from conftest.py.  Each test gets a fresh rolled-back session,
so wallet IDs can be reused across tests without conflict.
"""
import pytest


def _addr(seed: str) -> str:
    """Produce a valid 60-char uppercase Qubic-style address for tests."""
    import hashlib
    h = hashlib.sha256(seed.encode()).hexdigest().upper()
    alpha = "".join(c for c in h if c.isalpha())
    while len(alpha) < 60:
        alpha += alpha
    return alpha[:60]


WALLET_PAYLOAD = {
    "id": _addr("primary"),
    "label": "Test Wallet",
    "note": "Created in tests",
    "wallet_type": "PRIVATE",
}

WALLET_ID = WALLET_PAYLOAD["id"]
WALLET_ID_A = _addr("list-a")
WALLET_ID_B = _addr("list-b")


# ------------------------------------------------------------------ POST /wallets --

class TestCreateWallet:
    def test_create_returns_201(self, client):
        resp = client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        assert resp.status_code == 201, resp.text

    def test_create_returns_wallet_id(self, client):
        resp = client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        assert resp.json()["id"] == WALLET_ID

    def test_create_returns_correct_label(self, client):
        resp = client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        assert resp.json()["label"] == "Test Wallet"

    def test_create_returns_wallet_type(self, client):
        resp = client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        assert resp.json()["wallet_type"] == "PRIVATE"

    def test_create_duplicate_returns_409(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        resp = client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        assert resp.status_code == 409

    def test_create_wallet_is_active_by_default(self, client):
        resp = client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        assert resp.json()["active"] == 1

    def test_create_sets_created_at(self, client):
        resp = client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        data = resp.json()
        assert "created_at" in data
        assert data["created_at"] != "" and data["created_at"] is not None

    def test_create_without_note_succeeds(self, client):
        payload = {**WALLET_PAYLOAD, "note": None}
        resp = client.post("/api/v1/wallets", json=payload)
        assert resp.status_code == 201

    def test_create_missing_required_field_returns_422(self, client):
        """Omitting 'label' should fail validation."""
        payload = {"id": WALLET_ID, "wallet_type": "PRIVATE"}
        resp = client.post("/api/v1/wallets", json=payload)
        assert resp.status_code == 422


# ------------------------------------------------------------------ GET /wallets --

class TestListWallets:
    def test_empty_list_before_creation(self, client):
        resp = client.get("/api/v1/wallets")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_created_wallet_appears_in_list(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        resp = client.get("/api/v1/wallets")
        assert resp.status_code == 200
        ids = [w["id"] for w in resp.json()]
        assert WALLET_ID in ids

    def test_list_returns_all_active_wallets(self, client):
        payload_a = {**WALLET_PAYLOAD, "id": WALLET_ID_A}
        payload_b = {**WALLET_PAYLOAD, "id": WALLET_ID_B}
        client.post("/api/v1/wallets", json=payload_a)
        client.post("/api/v1/wallets", json=payload_b)
        resp = client.get("/api/v1/wallets")
        ids = [w["id"] for w in resp.json()]
        assert WALLET_ID_A in ids
        assert WALLET_ID_B in ids

    def test_list_returns_200(self, client):
        resp = client.get("/api/v1/wallets")
        assert resp.status_code == 200


# ------------------------------------------------------------------ DELETE /wallets/{id} --

class TestDeleteWallet:
    def test_delete_returns_204(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        resp = client.delete(f"/api/v1/wallets/{WALLET_ID}")
        assert resp.status_code == 204

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/api/v1/wallets/NONEXISTENT_ID")
        assert resp.status_code == 404

    def test_soft_deleted_wallet_excluded_from_list(self, client):
        """After DELETE the wallet must not appear in GET /wallets."""
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.delete(f"/api/v1/wallets/{WALLET_ID}")
        resp = client.get("/api/v1/wallets")
        ids = [w["id"] for w in resp.json()]
        assert WALLET_ID not in ids, (
            "Soft-deleted wallet should be excluded from the active wallet list"
        )

    def test_delete_twice_returns_404(self, client):
        """Deleting an already soft-deleted wallet should return 404."""
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.delete(f"/api/v1/wallets/{WALLET_ID}")
        resp = client.delete(f"/api/v1/wallets/{WALLET_ID}")
        assert resp.status_code == 404

    def test_soft_delete_sets_deleted_at_in_db(self, client, db):
        """Verify deleted_at is actually set in the database row."""
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.delete(f"/api/v1/wallets/{WALLET_ID}")

        from app.models.wallet import Wallet
        wallet = db.query(Wallet).filter(Wallet.id == WALLET_ID).first()
        assert wallet is not None, "Wallet row should still exist after soft delete"
        assert wallet.deleted_at is not None, (
            "deleted_at should be set after soft delete"
        )

    def test_soft_delete_sets_active_to_0(self, client, db):
        """Verify active flag is set to 0 in the database row."""
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.delete(f"/api/v1/wallets/{WALLET_ID}")

        from app.models.wallet import Wallet
        wallet = db.query(Wallet).filter(Wallet.id == WALLET_ID).first()
        assert wallet is not None
        assert wallet.active == 0, (
            f"Expected active=0 after soft delete, got active={wallet.active}"
        )


# ------------------------------------------------------------------ PUT /wallets/{id} --

class TestUpdateWallet:
    def test_update_label_returns_200(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        resp = client.put(f"/api/v1/wallets/{WALLET_ID}", json={"label": "Renamed"})
        assert resp.status_code == 200

    def test_update_label_persisted(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.put(f"/api/v1/wallets/{WALLET_ID}", json={"label": "Renamed"})
        resp = client.get("/api/v1/wallets")
        wallet = next(w for w in resp.json() if w["id"] == WALLET_ID)
        assert wallet["label"] == "Renamed"

    def test_update_nonexistent_returns_404(self, client):
        resp = client.put("/api/v1/wallets/NONEXISTENT_ID", json={"label": "X"})
        assert resp.status_code == 404

    def test_update_soft_deleted_wallet_returns_404(self, client):
        """PUT on a soft-deleted wallet must return 404."""
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.delete(f"/api/v1/wallets/{WALLET_ID}")
        resp = client.put(f"/api/v1/wallets/{WALLET_ID}", json={"label": "Ghost"})
        assert resp.status_code == 404


# ------------------------------------------------------------------ archive --

class TestArchiveWallet:
    def test_new_wallet_is_not_archived(self, client):
        resp = client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        assert resp.json()["archived"] is False

    def test_archive_without_reason_returns_422(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        resp = client.put(f"/api/v1/wallets/{WALLET_ID}", json={"archived": True})
        assert resp.status_code == 422

    def test_archive_with_blank_reason_returns_422(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        resp = client.put(f"/api/v1/wallets/{WALLET_ID}", json={"archived": True, "archived_reason": "   "})
        assert resp.status_code == 422

    def test_archive_with_reason_persisted(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        resp = client.put(f"/api/v1/wallets/{WALLET_ID}", json={
            "archived": True, "archived_reason": " Hack ", "archived_successor": "NEWID"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["archived"] is True
        assert body["archived_reason"] == "Hack"
        assert body["archived_successor"] == "NEWID"
        assert body["archived_at"]

    def test_successor_is_optional(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        resp = client.put(f"/api/v1/wallets/{WALLET_ID}", json={"archived": True, "archived_reason": "Hack"})
        assert resp.status_code == 200
        assert resp.json()["archived_successor"] is None

    def test_unarchive_clears_archived_at(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.put(f"/api/v1/wallets/{WALLET_ID}", json={"archived": True, "archived_reason": "Hack"})
        resp = client.put(f"/api/v1/wallets/{WALLET_ID}", json={"archived": False})
        assert resp.json()["archived"] is False
        assert resp.json()["archived_at"] is None

    def test_clearing_reason_of_archived_wallet_returns_422(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.put(f"/api/v1/wallets/{WALLET_ID}", json={"archived": True, "archived_reason": "Hack"})
        resp = client.put(f"/api/v1/wallets/{WALLET_ID}", json={"archived_reason": ""})
        assert resp.status_code == 422

    def test_list_reports_qearn_locked_default_zero(self, client):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        wallet = next(w for w in client.get("/api/v1/wallets").json() if w["id"] == WALLET_ID)
        assert wallet["qearn_locked"] == 0


# ------------------------------------------------------------------ internal flags --

class TestInternalFlagRecompute:
    def _event(self, db, wallet_id, source, dest, is_internal=0):
        from app.models.event import Event
        db.add(Event(
            id="mv1", wallet_id=wallet_id, tick_number=1, timestamp="2026-10-20T00:00:00Z",
            source_address=source, destination_addr=dest, is_internal=is_internal,
            amount_qubic=1000, source_type="TX", verified=0, created_at="2026-10-20T00:00:00Z",
        ))
        db.commit()

    def _flag(self, db):
        from app.models.event import Event
        db.expire_all()
        return db.query(Event).filter(Event.id == "mv1").one().is_internal

    def test_adding_counterpart_wallet_marks_transfer_internal(self, client, db):
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        new_id = _addr("successor")
        self._event(db, WALLET_ID, WALLET_ID, new_id)
        assert self._flag(db) == 0
        client.post("/api/v1/wallets", json={**WALLET_PAYLOAD, "id": new_id, "label": "New"})
        assert self._flag(db) == 1

    def test_deleting_counterpart_wallet_marks_transfer_external(self, client, db):
        new_id = _addr("successor")
        client.post("/api/v1/wallets", json=WALLET_PAYLOAD)
        client.post("/api/v1/wallets", json={**WALLET_PAYLOAD, "id": new_id, "label": "New"})
        self._event(db, WALLET_ID, WALLET_ID, new_id, is_internal=1)
        client.delete(f"/api/v1/wallets/{new_id}")
        assert self._flag(db) == 0
