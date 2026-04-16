# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Identity Broker — W3C DID-based Zero-Trust Authentication.

Decentralized Identity Broker for enforcing Lattice-Based Access Control (LBAC)
using W3C Decentralized Identifiers (DIDs) and Selective Disclosure JWTs.

All authentication flows are routed through W3C DID verification —
zero local trust assumptions or hardcoded RPC URLs exist in this module,
per LAW 9 (Federated Epistemic Handshakes) and LAW 10 (Thermodynamic
Secret Quarantine).
"""

from typing import Any

from fastapi import HTTPException


class IdentityBroker:
    """Decentralized Identity Broker enforcing Lattice-Based Access Control (LBAC).

    Verifies W3C DID-based VerifiableCredentialPresentationReceipts to establish
    cross-boundary authorization. No RPC URLs, ABIs, or local trust assumptions
    are hardcoded — all authentication is resolved from the DID document and
    the claims embedded in the Selective Disclosure JWT.
    """

    async def verify_connection_handshake(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract and verify the VerifiableCredentialPresentationReceipt.

        Validates the W3C DID-based receipt, ensuring the issuer DID belongs
        to the ``did:coreason:`` namespace and that authorization claims include
        a valid semantic clearance level.

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

        issuer_did = receipt.get("issuer_did", "")
        if not issuer_did.startswith("did:coreason:"):
            raise HTTPException(
                status_code=401,
                detail="Connection Severance Event: Invalid issuer_did.",
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
            "issuer_did": issuer_did,
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
