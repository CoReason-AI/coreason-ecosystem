# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import typing

import pytest
from fastapi import HTTPException

from coreason_ecosystem.gateway.capability_registry import CapabilityRegistry
from coreason_ecosystem.gateway.identity_broker import IdentityBroker


def _seed_test_registry() -> CapabilityRegistry:
    """Create a CapabilityRegistry seeded with test capabilities."""
    registry = CapabilityRegistry()
    registry._cache = {
        "urn:coreason:oracle:clinical_extractor": {
            "endpoint": "http://svc-pubmed-mcp.internal:8000",
            "clearance": "PUBLIC",
        },
        "urn:coreason:oracle:mathematics": {
            "endpoint": "http://svc-math-mcp.internal:8000",
            "clearance": "CONFIDENTIAL",
        },
    }
    return registry


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
    """Test registry direct resolution with seeded capabilities."""
    registry = _seed_test_registry()
    assert (
        registry.resolve_urn("urn:coreason:oracle:clinical_extractor")
        == "http://svc-pubmed-mcp.internal:8000"
    )
    with pytest.raises(KeyError):
        registry.resolve_urn("urn:coreason:oracle:fake")


@pytest.mark.asyncio
async def test_lbac_masking() -> None:
    """An agent possessing PUBLIC clearance only discovers PUBLIC endpoints."""
    registry = _seed_test_registry()
    masked_endpoints = await registry.discover_active_substrates(
        agent_clearance="PUBLIC"
    )

    assert "urn:coreason:oracle:clinical_extractor" in masked_endpoints
    assert "urn:coreason:oracle:mathematics" not in masked_endpoints
    assert "urn:coreason:oracle:weapon_systems" not in masked_endpoints


def test_lbac_validate_clearance_dominates() -> None:
    """RESTRICTED agent dominates PUBLIC capability."""
    broker = IdentityBroker()
    assert broker.validate_clearance_lattice("RESTRICTED", "PUBLIC") is True
    assert broker.validate_clearance_lattice("CONFIDENTIAL", "PUBLIC") is True
    assert broker.validate_clearance_lattice("PUBLIC", "PUBLIC") is True


def test_lbac_validate_clearance_insufficient() -> None:
    """PUBLIC agent cannot access RESTRICTED capability."""
    broker = IdentityBroker()
    assert broker.validate_clearance_lattice("PUBLIC", "RESTRICTED") is False
    assert broker.validate_clearance_lattice("PUBLIC", "CONFIDENTIAL") is False


def test_lbac_validate_clearance_unknown() -> None:
    """Unknown clearance level defaults to most restrictive."""
    broker = IdentityBroker()
    # Unknown agent gets level 0, unknown required gets level 3.
    assert broker.validate_clearance_lattice("UNKNOWN", "PUBLIC") is False
    assert broker.validate_clearance_lattice("RESTRICTED", "UNKNOWN") is True
