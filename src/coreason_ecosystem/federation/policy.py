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


# ---------------------------------------------------------------------------
# Contribution Governance (Private → Public publishing)
# ---------------------------------------------------------------------------


class ContributionRole(str, Enum):
    """RBAC roles governing who may contribute capabilities to the Public mesh.

    Follows enterprise-grade separation of duties: the person who
    develops a capability cannot be the same person who approves its
    publication to the Public network.
    """

    CONTRIBUTOR = "CONTRIBUTOR"
    """May submit a ContributionIntent (propose a capability for publication)."""

    APPROVER = "APPROVER"
    """May approve or reject a ContributionIntent. Must hold Security Officer
    or Data Governance Officer authority in the enterprise."""

    ADMIN = "ADMIN"
    """May modify ContributionPolicy settings (required approvals, URN scope,
    clearance limits). Typically the enterprise CISO or platform owner."""


class ContributionPolicy(BaseModel):
    """Enterprise RBAC policy governing capability contributions from
    a Private instance to the Public mesh.

    Contributions are a higher-privilege operation than read-only
    federation — they publish proprietary URN capabilities to the
    open network. This policy enforces multi-party approval, DLP
    scanning, clearance limits, and full audit trails.
    """

    enabled: bool = Field(
        default=False,
        description=(
            "Whether contributions to the Public mesh are permitted. "
            "Disabled by default — enterprises must explicitly opt in."
        ),
    )
    required_approvals: int = Field(
        default=2,
        ge=1,
        le=10,
        description=(
            "Number of distinct APPROVER-role signatures required before "
            "a ContributionIntent is executed. Minimum 1, default 2 "
            "(separation of duties)."
        ),
    )
    allowed_contribution_urns: list[str] = Field(
        default_factory=list,
        description=(
            "URN patterns permitted for contribution. Empty list means "
            "NO contributions are allowed (allowlist-only model). "
            "Supports glob-style suffix matching with '*'."
        ),
    )
    max_contribution_clearance: Literal["PUBLIC"] = Field(
        default="PUBLIC",
        description=(
            "Maximum data clearance level that may be contributed. "
            "Locked to PUBLIC — CONFIDENTIAL and RESTRICTED data "
            "can never be published to the open mesh."
        ),
    )
    require_dlp_scan: bool = Field(
        default=True,
        description=(
            "Whether DLP scanning is mandatory before contribution. "
            "Non-negotiable for enterprise deployments."
        ),
    )
    require_legal_attestation: bool = Field(
        default=True,
        description=(
            "Whether the contributor must attest that the capability "
            "is cleared for open-source publication under Prosperity 3.0."
        ),
    )

    @field_validator("allowed_contribution_urns")
    @classmethod
    def _sort_contribution_urns(cls, v: list[str]) -> list[str]:
        """Enforce canonical sort for deterministic hashing."""
        return sorted(v)


class ContributionIntent(BaseModel):
    """A signed request to publish a capability from Private to Public.

    Follows a multi-party approval workflow:
    1. A CONTRIBUTOR submits the intent (proposed URN + metadata).
    2. One or more APPROVERs review and sign.
    3. Once required_approvals are met, the FederationProxy executes
       the contribution with full DLP scanning and audit.

    The intent is immutable once submitted — modifications require
    a new intent with a new intent_id.
    """

    intent_id: str = Field(
        description="Unique identifier for this contribution intent."
    )
    urn: str = Field(description="The URN of the capability being contributed.")
    contributor_id: str = Field(
        description=(
            "SPIFFE ID or enterprise identity of the contributor "
            "(e.g., 'spiffe://alpha.internal/ns/eng/sa/jane.doe')."
        ),
    )
    contributor_role: ContributionRole = Field(
        default=ContributionRole.CONTRIBUTOR,
        description="The role of the submitter. Must be CONTRIBUTOR.",
    )
    justification: str = Field(
        description=(
            "Business justification for contributing this capability "
            "to the Public mesh. Required for audit trail."
        ),
    )
    legal_attestation: bool = Field(
        default=False,
        description=(
            "Whether the contributor attests that this capability "
            "contains no proprietary trade secrets, PII/PHI, or "
            "data above PUBLIC clearance."
        ),
    )
    approvals: list[str] = Field(
        default_factory=list,
        description=(
            "SPIFFE IDs of APPROVERs who have signed this intent. "
            "Must reach the required_approvals threshold before execution."
        ),
    )
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the intent was submitted.",
    )
    status: Literal["PENDING", "APPROVED", "REJECTED", "EXECUTED"] = Field(
        default="PENDING",
        description="Current status of the contribution intent.",
    )

    @field_validator("approvals")
    @classmethod
    def _sort_approvals(cls, v: list[str]) -> list[str]:
        """Enforce canonical sort for deterministic hashing."""
        return sorted(v)

    def compute_intent_hash(self) -> str:
        """Compute RFC 8785 canonical hash for signing."""
        canonical = json.dumps(
            {
                "intent_id": self.intent_id,
                "urn": self.urn,
                "contributor_id": self.contributor_id,
                "justification": self.justification,
                "legal_attestation": self.legal_attestation,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
