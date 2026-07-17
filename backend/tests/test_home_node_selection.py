"""
Tests for HOME_NODE preference in the sync source selection chain.

Chain: HOME_NODE → BOB → RPC. A healthy Home Node (the user's own archive
node, RPC interface) is preferred over public infrastructure; when it is
unavailable the existing BOB→RPC behaviour stays untouched.
"""
from app.models.node import Node
from app.utils.time import now_utc_iso
from app.services.qubic_client import RPCClient, BOBClient
from app.services.sync_engine import (
    _select_home_node,
    _get_rpc_client,
    _get_ordered_clients,
)


def _node(db, url, node_type, tick=1000, priority=1, status="ONLINE", is_active=1):
    n = Node(
        url=url,
        node_type=node_type,
        label=None,
        priority=priority,
        is_active=is_active,
        health_status=status,
        tick=tick,
        fail_count=0,
        last_checked=now_utc_iso(),
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


class TestSelectHomeNode:
    def test_none_without_home_nodes(self, db):
        _node(db, "https://rpc.qubic.org", "RPC")
        assert _select_home_node(db) is None

    def test_online_preferred_over_degraded(self, db):
        _node(db, "http://192.168.1.10:8080", "HOME_NODE", status="DEGRADED", priority=1)
        online = _node(db, "http://192.168.1.11:8080", "HOME_NODE", status="ONLINE", priority=9)
        assert _select_home_node(db).id == online.id

    def test_offline_and_inactive_ignored(self, db):
        _node(db, "http://192.168.1.10:8080", "HOME_NODE", status="OFFLINE")
        _node(db, "http://192.168.1.11:8080", "HOME_NODE", is_active=0)
        assert _select_home_node(db) is None

    def test_priority_breaks_tie(self, db):
        _node(db, "http://192.168.1.10:8080", "HOME_NODE", priority=5)
        best = _node(db, "http://192.168.1.11:8080", "HOME_NODE", priority=1)
        assert _select_home_node(db).id == best.id


class TestRpcClientPrefersHomeNode:
    def test_home_node_wins_over_rpc(self, db):
        _node(db, "https://rpc.qubic.org", "RPC", priority=1)
        _node(db, "http://192.168.1.10:8080", "HOME_NODE", priority=99)

        client = _get_rpc_client(db)
        assert client.base_url == "http://192.168.1.10:8080"

    def test_falls_back_to_rpc_when_home_offline(self, db):
        _node(db, "https://rpc.qubic.org", "RPC", priority=10)
        _node(db, "http://192.168.1.10:8080", "HOME_NODE", status="OFFLINE")

        client = _get_rpc_client(db)
        assert client.base_url == "https://rpc.qubic.org"


class TestOrderedClients:
    def test_home_node_first_and_correct_client_types(self, db):
        _node(db, "https://rpc.qubic.org", "RPC", priority=1)
        _node(db, "https://bobnet.qubic.li", "BOB_NODE", priority=1)
        _node(db, "http://192.168.1.10:8080", "HOME_NODE", priority=99)

        ordered = _get_ordered_clients(db)
        nodes = [n for n, _ in ordered]
        clients = [c for _, c in ordered]

        assert nodes[0].node_type == "HOME_NODE"
        assert isinstance(clients[0], RPCClient)          # Home Node spricht RPC
        assert any(isinstance(c, BOBClient) for c in clients[1:])