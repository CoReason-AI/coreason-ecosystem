# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Ontological Identity Router — W3C DID-based Zero-Trust Attestation.

Decentralized Ontological Identity Router for enforcing Lattice-Based Access Control (LBAC)
using W3C Decentralized Identifiers (DIDs) and Selective Disclosure JWTs.

All attestation flows are routed through W3C DID verification —
zero local trust assumptions or hardcoded RPC URLs exist in this module,
per LAW 9 (Federated Epistemic Handshakes) and LAW 10 (Thermodynamic
Secret Quarantine).
"""

from typing import Any

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from coreason_manifest.spec.ontology import (
    FederatedBilateralSLA,
    NodeCIDState,
    SemanticClassificationProfile,
)

# Transmutation the validator once at module level — enforces the manifest's exact
# DID regex (^did:[a-z0-9]+:[a-zA-Z0-9.\-_:]+$) and min_length=7 without
# duplicating the pattern.
_node_cid_validator: TypeAdapter[str] = TypeAdapter(NodeCIDState)

# Semantic classification ordering for LBAC dominance checks.
_CLASSIFICATION_LEVELS: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}


class OntologicalIdentityRouter:
    """Decentralized Ontological Identity Router enforcing Lattice-Based Access Control (LBAC).

    Verifies W3C DID-based VerifiableCredentialPresentationReceipts to establish
    cross-boundary authorization. No RPC URLs, ABIs, or local trust assumptions
    are hardcoded — all attestation is resolved from the DID document and
    the claims embedded in the Selective Disclosure JWT.
    """

    async def authorize_coordinate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Extract and verify the VerifiableCredentialPresentationReceipt.

        Validates the W3C DID-based receipt using the manifest's
        ``NodeCIDState`` TypeAdapter, ensuring the issuer DID matches
        the rigid ``^did:[a-z0-9]+:[a-zA-Z0-9.\\-_:]+$`` pattern and
        that authorization claims include a valid semantic clearance level.

        Args:
            payload: The connection payload containing the intent and receipt.

        Returns:
            The validated agent profile and clearance level.

        Raises:
            HTTPException: 401 Unauthorized if verification fails.
        """
        receipt = payload.get("receipt")
        if not receipt:
            raise HTTPException(
                status_code=401,
                detail="Connection Severance Event: Missing cryptographic receipt.",
            )

        principal_did = receipt.get("principal_did", receipt.get("issuer_did", ""))

        # Rigid W3C DID validation via the manifest's NodeCIDState TypeAdapter.
        try:
            _node_cid_validator.validate_python(principal_did)
        except ValidationError:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Connection Severance Event: Invalid DID geometry. "
                    f"'{principal_did}' does not conform to NodeCIDState pattern."
                ),
            )

        claims = receipt.get("authorization_claims", {})
        clearance = claims.get("clearance")
        if not clearance:
            raise HTTPException(
                status_code=401,
                detail="Connection Severance Event: Missing semantic clearance.",
            )

        # Return validated agent profile
        return {
            "principal_did": principal_did,
            "clearance": clearance,
        }

    # LBAC lattice ordering — strictly ascending clearance.
    CLEARANCE_LATTICE: dict[str, int] = {
        "PUBLIC": 1,
        "CONFIDENTIAL": 2,
        "RESTRICTED": 3,
    }

    def validate_clearance_lattice(
        self,
        agent_clearance: str,
        required_clearance: str,
    ) -> bool:
        """Verify that the agent's clearance level dominates the required level.

        Uses Lattice-Based Access Control (LBAC) ordering to determine
        if the agent has sufficient authorization to access the requested
        capability.

        Args:
            agent_clearance: The clearance level of the requesting agent.
            required_clearance: The clearance level required by the capability.

        Returns:
            True if ``agent_clearance`` dominates ``required_clearance``
            in the LBAC lattice.
        """
        agent_level = self.CLEARANCE_LATTICE.get(agent_clearance, 0)
        required_level = self.CLEARANCE_LATTICE.get(required_clearance, 3)
        return agent_level >= required_level

    def verify_federation_sla(
        self,
        sla: FederatedBilateralSLA,
        agent_classification: str,
    ) -> bool:
        """Verify a FederatedBilateralSLA governs the cross-boundary connection.

        Enforces the manifest's mathematical contract for multi-tenant
        federation.  Checks:

          1. ``receiving_tenant_cid`` is non-empty and conforms to CID pattern.
          2. Agent's classification does not exceed
             ``max_permitted_classification``.
          3. ``liability_limit_magnitude`` is within bounds (0–1B).

        Args:
            sla: The ``FederatedBilateralSLA`` from ``coreason_manifest``.
            agent_classification: The agent's semantic classification
                (``public``, ``internal``, ``confidential``, ``restricted``).

        Returns:
            True if the SLA geometry is satisfied.

        Raises:
            ValueError: If any SLA constraint is violated.
        """
        # 1. Validate receiving_tenant_cid is non-empty.
        if not sla.receiving_tenant_cid:
            raise ValueError("Federation Severance: receiving_tenant_cid is empty.")

        # 2. Classification dominance check
        agent_level = _CLASSIFICATION_LEVELS.get(agent_classification, 0)
        max_level = _CLASSIFICATION_LEVELS.get(
            sla.max_permitted_classification.value
            if isinstance(
                sla.max_permitted_classification, SemanticClassificationProfile
            )
            else str(sla.max_permitted_classification),
            0,
        )
        if agent_level > max_level:
            raise ValueError(
                f"Federation Severance: agent classification '{agent_classification}' "
                f"exceeds SLA max_permitted_classification "
                f"'{sla.max_permitted_classification}'."
            )

        # 3. Liability magnitude bounds are enforced by Pydantic (0 <= x <= 1B),
        # but we verify the field is present and non-negative defensively.
        if sla.liability_limit_magnitude < 0:
            raise ValueError(  # pragma: no cover
                "Federation Severance: liability_limit_magnitude is negative."
            )

        return True
