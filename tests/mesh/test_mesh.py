from coreason_ecosystem.mesh import KademliaDHTMock, MeshGateway, ZeroCopyStreamingMock
from coreason_manifest.spec.ontology import (
    FederatedDiscoveryIntent,
)


def test_kademlia_dht_mock() -> None:
    dht = KademliaDHTMock()
    valid_urn = "urn:coreason:actionspace:solver:test_capability"
    dht.store_capability(valid_urn, "192.168.1.1")
    dht.store_capability(valid_urn, "192.168.1.2")

    peers = dht.resolve_capability(valid_urn)
    assert len(peers) == 2
    assert "192.168.1.1" in peers
    assert "192.168.1.2" in peers


def test_mesh_gateway() -> None:
    valid_urn = "urn:coreason:actionspace:solver:test_capability"
    dht = KademliaDHTMock()
    dht.store_capability(valid_urn, "10.0.0.1")
    gateway = MeshGateway(dht)

    intent = FederatedDiscoveryIntent(
        domain_filter=["solver"],
        minimum_epistemic_status="DRAFT",
    )

    peers = gateway.handle_discovery_intent(intent)
    assert peers == ["10.0.0.1"]

    # Test intent with non-matching domain
    intent_mismatch = FederatedDiscoveryIntent(
        domain_filter=["oracle"],
        minimum_epistemic_status="DRAFT",
    )
    peers_mismatch = gateway.handle_discovery_intent(intent_mismatch)
    assert peers_mismatch == []


def test_zero_copy_streaming_mock() -> None:
    valid_cid = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    stream = ZeroCopyStreamingMock()
    stream.store_blob(valid_cid, b"mocked_binary_content")

    data = stream.handle_fetch_intent(valid_cid)
    assert data == b"mocked_binary_content"
