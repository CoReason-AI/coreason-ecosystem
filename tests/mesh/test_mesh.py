from coreason_ecosystem.mesh import KademliaDHTMock, MeshGateway, ZeroCopyStreamingMock
from coreason_manifest.spec.ontology import (
    FederatedDiscoveryIntent,
    FederatedCIDFetchIntent,
)


def test_kademlia_dht_mock() -> None:
    dht = KademliaDHTMock()
    valid_cid = (
        "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )
    missing_cid = (
        "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    )
    dht.store_capability(valid_cid, "192.168.1.1")
    dht.store_capability(valid_cid, "192.168.1.2")

    peers = dht.resolve_capability(valid_cid)
    assert len(peers) == 2
    assert "192.168.1.1" in peers
    assert "192.168.1.2" in peers

    empty_peers = dht.resolve_capability(missing_cid)
    assert len(empty_peers) == 0


def test_mesh_gateway() -> None:
    valid_cid = (
        "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )
    dht = KademliaDHTMock()
    dht.store_capability(valid_cid, "10.0.0.1")
    gateway = MeshGateway(dht)

    intent = FederatedDiscoveryIntent(
        target_capability_cid=valid_cid,
        required_security_clearance="PUBLIC",
        domain_filter=[],
    )

    peers = gateway.handle_discovery_intent(intent)
    assert peers == ["10.0.0.1"]

    # Test intent without specific CID
    intent_empty = FederatedDiscoveryIntent(
        required_security_clearance="PUBLIC", domain_filter=[]
    )
    peers_empty = gateway.handle_discovery_intent(intent_empty)
    assert peers_empty == []


def test_zero_copy_streaming_mock() -> None:
    valid_cid = (
        "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )
    missing_cid = (
        "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    )
    stream = ZeroCopyStreamingMock()
    stream.store_blob(valid_cid, b"mocked_binary_content")

    intent = FederatedCIDFetchIntent(target_cid=valid_cid)

    data = stream.handle_fetch_intent(intent)
    assert data == b"mocked_binary_content"

    intent_missing = FederatedCIDFetchIntent(target_cid=missing_cid)
    assert stream.handle_fetch_intent(intent_missing) == b""
