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
Federation policy models.

Defines the air gap connectivity policies, federation agreements, and
peer identity state for Private↔Public and Private↔Private communication.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ConnectivityDirection(str, Enum):
    """Permitted direction of traffic across the air gap."""

    CLOSED = "CLOSED"
    OUTBOUND_ONLY = "OUTBOUND_ONLY"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class InstanceType(str, Enum):
    """Deployment mode of a CoReason instance."""

    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class FederationPeerState(BaseModel):
    """Identity and trust anchor for a remote CoReason instance.

    Captures the SPIFFE trust domain, Vault authority, and connectivity
    metadata for a federated peer. Used by the FederationProxy to
    establish mTLS channels and verify schema seals from remote sources.
    """

    instance_id: str = Field(
        description="Unique identifier for this CoReason instance (e.g., 'alpha.coreason.ai')."
    )
    instance_type: InstanceType = Field(
        description="Whether this instance is a Private VPC deployment or the Public mesh."
    )
    spiffe_trust_domain: str = Field(
        description=(
            "The SPIFFE trust domain URI for this instance "
            "(e.g., 'spiffe://alpha.coreason.ai')."
        )
    )
    trust_bundle_endpoint: str | None = Field(
        default=None,
        description=(
            "HTTPS endpoint serving the SPIFFE trust bundle "
            "(e.g., 'https://spire.alpha.coreason.ai/.well-known/spiffe-bundle')."
        ),
    )
    gateway_endpoint: str = Field(
        description="The MCP gateway endpoint URI for this instance."
    )
    tenant_cid: str = Field(
        description="The tenant_cid governing this instance's data boundary."
    )
    clearance: Literal["PUBLIC", "CONFIDENTIAL", "RESTRICTED"] = Field(
        default="PUBLIC",
        description="Maximum clearance level this peer is authorized to receive.",
    )


class AirGapPolicy(BaseModel):
    """Connectivity policy governing the air gap between this instance and a peer.

    The controlling instance (always the Private side) defines the
    direction, DLP scanning requirements, and audit obligations for
    all traffic crossing the air gap boundary.
    """

    peer_instance_id: str = Field(
        description="The instance_id of the remote peer this policy governs."
    )
    direction: ConnectivityDirection = Field(
        default=ConnectivityDirection.CLOSED,
        description="Permitted traffic direction across the air gap.",
    )
    require_dlp_scanning: bool = Field(
        default=True,
        description=(
            "Whether NemoClaw DLP scanning is mandatory for all "
            "payloads crossing the air gap."
        ),
    )
    require_audit_receipts: bool = Field(
        default=True,
        description=(
            "Whether every cross-instance request must emit a "
            "FederatedExecutionReceipt to the Cryptographic Provenance Graph."
        ),
    )
    allowed_urns: list[str] = Field(
        default_factory=list,
        description=(
            "Allowlist of URN patterns permitted to cross the air gap. "
            "Empty list means all URNs are permitted (subject to clearance)."
        ),
    )
    max_clearance: Literal["PUBLIC", "CONFIDENTIAL", "RESTRICTED"] = Field(
        default="PUBLIC",
        description="Maximum data clearance level permitted to cross the air gap.",
    )

    @field_validator("allowed_urns")
    @classmethod
    def _sort_urns(cls, v: list[str]) -> list[str]:
        """Enforce canonical sort for RFC 8785 deterministic hashing."""
        return sorted(v)


class FederationAgreementState(BaseModel):
    """Bilateral federation agreement between two CoReason instances.

    Both parties must sign this agreement before any traffic flows.
    For Private↔Public, only the Private side signs (Public is open).
    For Private↔Private (DMZ), both enterprises must sign.
    """

    agreement_id: str = Field(
        description="Unique identifier for this federation agreement."
    )
    initiator: FederationPeerState = Field(
        description="The instance that initiated the federation request."
    )
    responder: FederationPeerState = Field(
        description="The instance that accepted the federation request."
    )
    initiator_policy: AirGapPolicy = Field(
        description="The air gap policy enforced by the initiating instance."
    )
    responder_policy: AirGapPolicy | None = Field(
        default=None,
        description=(
            "The air gap policy enforced by the responding instance. "
            "None for Private→Public (Public has no inbound policy)."
        ),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the agreement was created.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional expiry timestamp. None means no expiry.",
    )
    signed_by_initiator: bool = Field(
        default=False,
        description="Whether the initiating instance has signed this agreement.",
    )
    signed_by_responder: bool = Field(
        default=False,
        description="Whether the responding instance has signed this agreement.",
    )

    @property
    def is_active(self) -> bool:
        """Whether this agreement is currently active (signed, not expired)."""
        if not self.signed_by_initiator:
            return False
        # For Private→Public, only the Private side (initiator) signs.
        # The Public mesh has no signing authority — it is open by default.
        if self.responder.instance_type == InstanceType.PUBLIC:
            pass  # No responder signature needed
        elif not self.signed_by_responder:
            # Private→Private requires both signatures
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def compute_agreement_hash(self) -> str:
        """Compute RFC 8785 canonical hash of the agreement for signing."""
        canonical = json.dumps(
            {
                "agreement_id": self.agreement_id,
                "initiator": self.initiator.instance_id,
                "responder": self.responder.instance_id,
                "direction": self.initiator_policy.direction.value,
                "allowed_urns": self.initiator_policy.allowed_urns,
                "max_clearance": self.initiator_policy.max_clearance,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
