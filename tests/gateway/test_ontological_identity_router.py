# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Tests for OntologicalIdentityRouter — W3C DID validation and FederatedBilateralSLA enforcement."""

import pytest
from fastapi import HTTPException

from coreason_ecosystem.gateway.ontological_identity_router import (
    OntologicalIdentityRouter,
)
from coreason_manifest.spec.ontology import (
    FederatedBilateralSLA,
    SemanticClassificationProfile,
)


@pytest.fixture
def broker() -> OntologicalIdentityRouter:
    return OntologicalIdentityRouter()


class TestVerifyConnectionHandshake:
    """W3C DID-based authentication via NodeCIDState TypeAdapter."""

    @pytest.mark.asyncio
    async def test_valid_did_passes(self, broker: OntologicalIdentityRouter) -> None:
        payload = {
            "receipt": {
                "issuer_did": "did:coreason:swarm-node-001",
                "authorization_claims": {"clearance": "PUBLIC"},
            }
        }
        result = await broker.authorize_coordinate(payload)
        assert result["issuer_did"] == "did:coreason:swarm-node-001"
        assert result["clearance"] == "PUBLIC"

    @pytest.mark.asyncio
    async def test_missing_receipt_raises(
        self, broker: OntologicalIdentityRouter
    ) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await broker.authorize_coordinate({})
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_did_format_raises(
        self, broker: OntologicalIdentityRouter
    ) -> None:
        payload = {
            "receipt": {
                "issuer_did": "web:hack.com",
                "authorization_claims": {"clearance": "PUBLIC"},
            }
        }
        with pytest.raises(HTTPException) as exc_info:
            await broker.authorize_coordinate(payload)
        assert exc_info.value.status_code == 401
        assert "DID geometry" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_short_did_raises(self, broker: OntologicalIdentityRouter) -> None:
        """DIDs shorter than 7 characters violate NodeCIDState min_length."""
        payload = {
            "receipt": {
                "issuer_did": "did:a",
                "authorization_claims": {"clearance": "PUBLIC"},
            }
        }
        with pytest.raises(HTTPException) as exc_info:
            await broker.authorize_coordinate(payload)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_clearance_raises(
        self, broker: OntologicalIdentityRouter
    ) -> None:
        payload = {
            "receipt": {
                "issuer_did": "did:coreason:node-001",
                "authorization_claims": {},
            }
        }
        with pytest.raises(HTTPException) as exc_info:
            await broker.authorize_coordinate(payload)
        assert exc_info.value.status_code == 401
        assert "clearance" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_empty_did_raises(self, broker: OntologicalIdentityRouter) -> None:
        payload = {
            "receipt": {
                "issuer_did": "",
                "authorization_claims": {"clearance": "PUBLIC"},
            }
        }
        with pytest.raises(HTTPException) as exc_info:
            await broker.authorize_coordinate(payload)
        assert exc_info.value.status_code == 401


class TestClearanceLattice:
    """LBAC lattice dominance verification."""

    def test_public_dominates_public(self, broker: OntologicalIdentityRouter) -> None:
        assert broker.validate_clearance_lattice("PUBLIC", "PUBLIC") is True

    def test_restricted_dominates_all(self, broker: OntologicalIdentityRouter) -> None:
        assert broker.validate_clearance_lattice("RESTRICTED", "PUBLIC") is True
        assert broker.validate_clearance_lattice("RESTRICTED", "CONFIDENTIAL") is True
        assert broker.validate_clearance_lattice("RESTRICTED", "RESTRICTED") is True

    def test_public_cannot_access_restricted(
        self, broker: OntologicalIdentityRouter
    ) -> None:
        assert broker.validate_clearance_lattice("PUBLIC", "RESTRICTED") is False

    def test_unknown_clearance_fails(self, broker: OntologicalIdentityRouter) -> None:
        assert broker.validate_clearance_lattice("UNKNOWN", "PUBLIC") is False


class TestVerifyFederationSLA:
    """FederatedBilateralSLA enforcement from coreason_manifest."""

    @pytest.fixture
    def valid_sla(self) -> FederatedBilateralSLA:
        return FederatedBilateralSLA(
            receiving_tenant_cid="tenant-001",
            max_permitted_classification=SemanticClassificationProfile.CONFIDENTIAL,
            liability_limit_magnitude=1000000,
        )

    def test_valid_sla_public_agent(
        self, broker: OntologicalIdentityRouter, valid_sla: FederatedBilateralSLA
    ) -> None:
        result = broker.verify_federation_sla(valid_sla, "public")
        assert result is True

    def test_valid_sla_confidential_agent(
        self, broker: OntologicalIdentityRouter, valid_sla: FederatedBilateralSLA
    ) -> None:
        result = broker.verify_federation_sla(valid_sla, "confidential")
        assert result is True

    def test_classification_exceeds_sla(
        self, broker: OntologicalIdentityRouter, valid_sla: FederatedBilateralSLA
    ) -> None:
        with pytest.raises(ValueError, match="Federation Severance"):
            broker.verify_federation_sla(valid_sla, "restricted")

    def test_sla_with_public_ceiling(self, broker: OntologicalIdentityRouter) -> None:
        sla = FederatedBilateralSLA(
            receiving_tenant_cid="tenant-002",
            max_permitted_classification=SemanticClassificationProfile.PUBLIC,
            liability_limit_magnitude=100,
        )
        assert broker.verify_federation_sla(sla, "public") is True
        with pytest.raises(ValueError, match="Federation Severance"):
            broker.verify_federation_sla(sla, "internal")
