# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

"""
Federation module for inter-instance CoReason communication.

Governs the controlled air gap between CoReason Private (VPC) and
CoReason Public (open mesh), as well as Private-to-Private DMZ
federation.

MIGRATION NOTE (2026-05):
    The legacy FederationProxy (httpx P2P mTLS) and AirGapPolicy
    (custom Pydantic models) have been replaced by the NATS-native
    ``NATSFederationProxy`` in ``coreason_ecosystem.wasmcloud.nats_federation``.

    Air gap enforcement is now handled by NATS account isolation and
    leaf node configuration (server-side), not application code.

    The policy models (``AirGapPolicy``, ``FederationAgreementState``, etc.)
    are retained in ``policy.py`` as data contracts for backward compatibility
    with existing tests and downstream consumers. They are no longer used
    by the active federation proxy.
"""

from .policy import (
    AirGapPolicy,
    ConnectivityDirection,
    ContributionIntent,
    ContributionPolicy,
    ContributionRole,
    FederationAgreementState,
    FederationPeerState,
    InstanceType,
)

# Re-export the NATS-native proxy as the primary federation mechanism
from coreason_ecosystem.wasmcloud.nats_federation import (
    NATSFederationProxy,
    FederatedExecutionReceipt,
)

# Canonical public mesh identity constants (migrated from proxy.py)
COREASON_PUBLIC_INSTANCE_ID = "mesh.coreason.ai"
COREASON_PUBLIC_TENANT_CID = (
    "889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531"
)
COREASON_PUBLIC_SPIFFE_DOMAIN = "spiffe://mesh.coreason.ai"


def create_public_peer() -> FederationPeerState:
    """Create the canonical CoReason Public peer state.

    There is exactly one public network — CoReason's default open mesh.
    This factory returns its identity anchors.
    """
    return FederationPeerState(
        instance_id=COREASON_PUBLIC_INSTANCE_ID,
        instance_type=InstanceType.PUBLIC,
        spiffe_trust_domain=COREASON_PUBLIC_SPIFFE_DOMAIN,
        trust_bundle_endpoint=f"https://spire.{COREASON_PUBLIC_INSTANCE_ID}/.well-known/spiffe-bundle",
        gateway_endpoint=f"https://gateway.{COREASON_PUBLIC_INSTANCE_ID}",
        tenant_cid=COREASON_PUBLIC_TENANT_CID,
        clearance="PUBLIC",
    )


__all__ = [
    "AirGapPolicy",
    "COREASON_PUBLIC_INSTANCE_ID",
    "COREASON_PUBLIC_SPIFFE_DOMAIN",
    "COREASON_PUBLIC_TENANT_CID",
    "ConnectivityDirection",
    "ContributionIntent",
    "ContributionPolicy",
    "ContributionRole",
    "FederatedExecutionReceipt",
    "FederationAgreementState",
    "FederationPeerState",
    "InstanceType",
    "NATSFederationProxy",
    "create_public_peer",
]
