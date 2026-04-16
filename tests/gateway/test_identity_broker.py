import pytest
import typing
from fastapi import HTTPException
from coreason_ecosystem.gateway.identity_broker import IdentityBroker
from coreason_ecosystem.gateway.capability_registry import CapabilityRegistry


@pytest.mark.asyncio
async def test_sybil_rejection() -> None:
    """A fraudulent payload bearing did:web:hack.com must mathematically fail."""
    broker = IdentityBroker()
    payload: dict[str, typing.Any] = {
        "domain_filter": [],
        "receipt": {
            "issuer_did": "did:web:hack.com",
            "authorization_claims": {"clearance": "PUBLIC"},
        },
    }
    with pytest.raises(HTTPException) as exc:
        await broker.verify_connection_handshake(payload)
    assert exc.value.status_code == 401
    assert "Invalid issuer_did" in exc.value.detail


@pytest.mark.asyncio
async def test_missing_receipt() -> None:
    """Test payload lacking cryptographic receipt fails."""
    broker = IdentityBroker()
    payload: dict[str, typing.Any] = {"domain_filter": []}
    with pytest.raises(HTTPException) as exc:
        await broker.verify_connection_handshake(payload)
    assert exc.value.status_code == 401
    assert "Missing cryptographic receipt" in exc.value.detail


@pytest.mark.asyncio
async def test_missing_clearance() -> None:
    """Test payload lacking semantic clearance fails."""
    broker = IdentityBroker()
    payload: dict[str, typing.Any] = {
        "domain_filter": [],
        "receipt": {"issuer_did": "did:coreason:oracle:empty"},
    }
    with pytest.raises(HTTPException) as exc:
        await broker.verify_connection_handshake(payload)
    assert exc.value.status_code == 401
    assert "Missing semantic clearance" in exc.value.detail


@pytest.mark.asyncio
async def test_successful_handshake() -> None:
    """Test payload passing successfully."""
    broker = IdentityBroker()
    payload: dict[str, typing.Any] = {
        "domain_filter": [],
        "receipt": {
            "issuer_did": "did:coreason:oracle:test",
            "authorization_claims": {"clearance": "PUBLIC"},
        },
    }
    result = await broker.verify_connection_handshake(payload)
    assert result["issuer_did"] == "did:coreason:oracle:test"
    assert result["clearance"] == "PUBLIC"


@pytest.mark.asyncio
async def test_registry_resolve() -> None:
    """Test registry direct resolution."""
    registry = CapabilityRegistry()
    assert (
        registry.resolve_urn("urn:coreason:oracle:clinical_extractor")
        == "http://svc-pubmed-mcp.internal:8000"
    )
    with pytest.raises(KeyError):
        registry.resolve_urn("urn:coreason:oracle:fake")


@pytest.mark.asyncio
async def test_lbac_masking() -> None:
    """An agent possessing PUBLIC clearance only discovers PUBLIC endpoints."""
    registry = CapabilityRegistry()
    # Mock finding endpoints based on PUBLIC clearance
    masked_endpoints = await registry.discover_active_substrates(
        agent_clearance="PUBLIC"
    )

    assert "urn:coreason:oracle:clinical_extractor" in masked_endpoints
    assert "urn:coreason:oracle:mathematics" not in masked_endpoints
    assert "urn:coreason:oracle:weapon_systems" not in masked_endpoints
