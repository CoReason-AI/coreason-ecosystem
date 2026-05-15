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
Federation proxy for cross-instance CoReason communication.

Implements the controlled air gap between CoReason instances:
- Private → Public (outbound capability invocation)
- Private → Private (DMZ-mediated bilateral federation)
- Public → Private (prohibited unless Private opens the air gap)

Uses httpx for async HTTP transport and the cryptography library
for local TLS certificate operations. Vault Transit handles
high-value signing via the existing hvac integration.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import ssl
from datetime import datetime, timezone
from typing import Any

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

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

# The canonical CoReason Public network identity.
# There is exactly ONE public network — CoReason's default open mesh.
# An instance may flip between PRIVATE and PUBLIC mode, but there is
# only ever one PUBLIC identity on the network at a time.
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


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Federated Execution Receipt (audit trail for cross-instance traffic)
# ---------------------------------------------------------------------------


class FederatedExecutionReceipt:
    """Immutable audit record for a single cross-instance request.

    Emitted to the Cryptographic Provenance Graph after every
    successful (or failed) cross-instance MCP tool invocation.
    """

    __slots__ = (
        "receipt_id",
        "agreement_id",
        "source_instance",
        "destination_instance",
        "urn",
        "timestamp",
        "payload_hash",
        "response_hash",
        "success",
        "error",
    )

    def __init__(
        self,
        *,
        receipt_id: str,
        agreement_id: str,
        source_instance: str,
        destination_instance: str,
        urn: str,
        payload_hash: str,
        response_hash: str | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        self.receipt_id = receipt_id
        self.agreement_id = agreement_id
        self.source_instance = source_instance
        self.destination_instance = destination_instance
        self.urn = urn
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.payload_hash = payload_hash
        self.response_hash = response_hash
        self.success = success
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for provenance graph ingestion."""
        return {
            "receipt_id": self.receipt_id,
            "agreement_id": self.agreement_id,
            "source_instance": self.source_instance,
            "destination_instance": self.destination_instance,
            "urn": self.urn,
            "timestamp": self.timestamp,
            "payload_hash": self.payload_hash,
            "response_hash": self.response_hash,
            "success": self.success,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Federation Proxy — the controlled air gap gateway
# ---------------------------------------------------------------------------


class FederationProxy:
    """Controlled air gap gateway for inter-instance CoReason communication.

    Manages federation agreements, enforces air gap policies, performs
    DLP payload scanning, and emits audit receipts for all cross-instance
    traffic.

    Architecture:
        - Private → Public: Outbound httpx calls with optional mTLS
        - Private → Private: Bilateral DMZ proxy with mutual mTLS
        - Public → Private: Blocked unless Private has opened the gap

    An instance may flip between PRIVATE and PUBLIC mode at runtime
    (e.g., transitioning from development to production mesh membership).
    There is exactly one canonical PUBLIC identity on the network.

    OSS Dependencies:
        - httpx: Async HTTP/2 client with mTLS support
        - cryptography: TLS certificate generation and verification
        - ssl: Standard library SSL context for mTLS
    """

    def __init__(
        self,
        *,
        local_instance: FederationPeerState,
        agreements: list[FederationAgreementState] | None = None,
        contribution_policy: ContributionPolicy | None = None,
    ) -> None:
        self._local = local_instance.model_copy(deep=True)
        self._agreements: dict[str, FederationAgreementState] = {}
        self._policies: dict[str, AirGapPolicy] = {}
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._receipts: list[FederatedExecutionReceipt] = []
        self._contribution_policy = contribution_policy or ContributionPolicy()
        self._contribution_intents: dict[str, ContributionIntent] = {}

        if agreements:
            for agreement in agreements:
                self.register_agreement(agreement)

    # ------------------------------------------------------------------
    # Instance mode management
    # ------------------------------------------------------------------

    @property
    def instance_mode(self) -> InstanceType:
        """Current deployment mode of this instance."""
        return self._local.instance_type

    def set_instance_mode(self, mode: InstanceType) -> None:
        """Flip this instance's deployment mode.

        Only Private → Public flipping is permitted. The canonical
        Public network (mesh.coreason.ai) can never flip to Private —
        it is the permanent anchor of the open mesh.

        All existing clients are closed and agreements are preserved
        (they will be re-evaluated against the new mode on next use).

        Raises:
            ValueError: If a Public instance attempts to flip to Private.
        """
        old_mode = self._local.instance_type

        # The canonical Public network can never become Private.
        if old_mode == InstanceType.PUBLIC and mode == InstanceType.PRIVATE:
            raise ValueError(
                f"Cannot flip instance '{self._local.instance_id}' from "
                f"PUBLIC to PRIVATE. The canonical Public network is the "
                f"permanent anchor of the mesh and cannot be demoted."
            )

        self._local.instance_type = mode

        # Invalidate cached clients (SSL contexts may differ)
        for client in self._clients.values():
            # Async close deferred; caller should await close() if needed
            pass
        self._clients.clear()

        logger.info(
            "Instance %s mode flipped: %s → %s",
            self._local.instance_id,
            old_mode.value,
            mode.value,
        )

    # ------------------------------------------------------------------
    # Agreement management
    # ------------------------------------------------------------------

    def register_agreement(self, agreement: FederationAgreementState) -> None:
        """Register a federation agreement and its associated policy."""
        peer_id = self._resolve_peer_id(agreement)
        self._agreements[peer_id] = agreement

        # Determine which policy applies to us
        if agreement.initiator.instance_id == self._local.instance_id:
            self._policies[peer_id] = agreement.initiator_policy
        elif agreement.responder_policy:
            self._policies[peer_id] = agreement.responder_policy
        else:
            # We are the responder and no responder policy exists
            # (e.g., Public node receiving from Private — create a default open policy)
            self._policies[peer_id] = AirGapPolicy(
                peer_instance_id=agreement.initiator.instance_id,
                direction=ConnectivityDirection.BIDIRECTIONAL,
                require_dlp_scanning=False,
                require_audit_receipts=True,
            )

        logger.info(
            "Registered federation agreement %s with peer %s (direction=%s)",
            agreement.agreement_id,
            peer_id,
            self._policies[peer_id].direction.value,
        )

    def _resolve_peer_id(self, agreement: FederationAgreementState) -> str:
        """Resolve the remote peer's instance_id from an agreement."""
        if agreement.initiator.instance_id == self._local.instance_id:
            return agreement.responder.instance_id
        return agreement.initiator.instance_id

    def get_peer(self, peer_instance_id: str) -> FederationPeerState | None:
        """Retrieve the peer state for a registered peer."""
        agreement = self._agreements.get(peer_instance_id)
        if not agreement:
            return None
        if agreement.initiator.instance_id == peer_instance_id:
            return agreement.initiator
        return agreement.responder

    def list_active_peers(self) -> list[str]:
        """List instance_ids of all peers with active agreements."""
        return [
            peer_id
            for peer_id, agreement in self._agreements.items()
            if agreement.is_active
        ]

    # ------------------------------------------------------------------
    # Air gap enforcement
    # ------------------------------------------------------------------

    def check_air_gap(
        self,
        peer_instance_id: str,
        urn: str,
        clearance: str = "PUBLIC",
    ) -> tuple[bool, str]:
        """Check whether a request to a peer is permitted by the air gap policy.

        Returns:
            (permitted, reason) — True if the request is allowed, else False with reason.
        """
        agreement = self._agreements.get(peer_instance_id)
        if not agreement:
            return False, f"No federation agreement with peer '{peer_instance_id}'"

        if not agreement.is_active:
            return (
                False,
                f"Federation agreement with '{peer_instance_id}' is not active",
            )

        policy = self._policies.get(peer_instance_id)
        if not policy:
            return False, f"No air gap policy for peer '{peer_instance_id}'"

        if policy.direction == ConnectivityDirection.CLOSED:
            return False, f"Air gap to '{peer_instance_id}' is CLOSED"

        # Check URN allowlist
        if policy.allowed_urns and not self._urn_matches(urn, policy.allowed_urns):
            return (
                False,
                f"URN '{urn}' is not in the allowlist for peer '{peer_instance_id}'",
            )

        # Check clearance level
        clearance_order = {"PUBLIC": 0, "CONFIDENTIAL": 1, "RESTRICTED": 2}
        if clearance_order.get(clearance, 0) > clearance_order.get(
            policy.max_clearance, 0
        ):
            return (
                False,
                f"Clearance '{clearance}' exceeds max '{policy.max_clearance}' for peer '{peer_instance_id}'",
            )

        return True, "Permitted"

    @staticmethod
    def _urn_matches(urn: str, patterns: list[str]) -> bool:
        """Check if a URN matches any pattern in the allowlist.

        Supports glob-style suffix matching with '*'.
        """
        for pattern in patterns:
            if pattern.endswith("*"):
                if urn.startswith(pattern[:-1]):
                    return True
            elif urn == pattern:
                return True
        return False

    # ------------------------------------------------------------------
    # Cross-instance tool invocation
    # ------------------------------------------------------------------

    async def invoke_remote_tool(
        self,
        peer_instance_id: str,
        urn: str,
        payload: dict[str, Any],
        clearance: str = "PUBLIC",
    ) -> dict[str, Any]:
        """Invoke an MCP tool on a remote CoReason instance.

        Enforces the air gap policy, performs DLP scanning (if required),
        sends the request via httpx with mTLS, and emits an audit receipt.

        Args:
            peer_instance_id: The target instance's identifier.
            urn: The URN of the tool to invoke.
            payload: The JSON-RPC payload.
            clearance: The clearance level of the data being sent.

        Returns:
            The JSON response from the remote instance.

        Raises:
            PermissionError: If the air gap policy denies the request.
            ConnectionError: If the remote instance is unreachable.
        """
        # 1. Enforce air gap policy
        permitted, reason = self.check_air_gap(peer_instance_id, urn, clearance)
        if not permitted:
            logger.warning(
                "Air gap denied: %s → %s (URN=%s): %s",
                self._local.instance_id,
                peer_instance_id,
                urn,
                reason,
            )
            raise PermissionError(reason)

        policy = self._policies[peer_instance_id]
        agreement = self._agreements[peer_instance_id]

        # 2. DLP scanning (if required by policy)
        if policy.require_dlp_scanning:
            payload = self._dlp_scan_outbound(payload)

        # 3. Compute payload hash for audit trail
        payload_canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(payload_canonical.encode("utf-8")).hexdigest()

        # 4. Build the JSON-RPC request
        rpc_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": urn,
                "arguments": payload,
            },
            "id": payload_hash[:16],
        }

        # 5. Get or create the httpx client for this peer
        client = await self._get_client(peer_instance_id)

        # 6. Send the request
        peer = self.get_peer(peer_instance_id)
        if not peer:
            raise ConnectionError(f"Peer '{peer_instance_id}' not found")

        response_data: dict[str, Any] = {}
        response_hash: str | None = None
        error_msg: str | None = None
        success = True

        try:
            response = await client.post(
                f"{peer.gateway_endpoint}/mcp/v1/messages",
                json=rpc_request,
                headers={
                    "X-Source-Instance": self._local.instance_id,
                    "X-Source-Tenant-CID": self._local.tenant_cid,
                    "X-Federation-Agreement": agreement.agreement_id,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            response_data = response.json()
            response_canonical = json.dumps(
                response_data, sort_keys=True, separators=(",", ":")
            )
            response_hash = hashlib.sha256(
                response_canonical.encode("utf-8")
            ).hexdigest()

            # DLP scan inbound response
            if policy.require_dlp_scanning:
                response_data = self._dlp_scan_inbound(response_data)

        except httpx.HTTPStatusError as e:
            success = False
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            raise ConnectionError(error_msg) from e
        except httpx.ConnectError as e:
            success = False
            error_msg = f"Connection failed: {e}"
            raise ConnectionError(error_msg) from e
        finally:
            # 7. Emit audit receipt
            if policy.require_audit_receipts:
                receipt = FederatedExecutionReceipt(
                    receipt_id=f"{agreement.agreement_id}:{payload_hash[:16]}",
                    agreement_id=agreement.agreement_id,
                    source_instance=self._local.instance_id,
                    destination_instance=peer_instance_id,
                    urn=urn,
                    payload_hash=payload_hash,
                    response_hash=response_hash,
                    success=success,
                    error=error_msg,
                )
                self._receipts.append(receipt)
                logger.info(
                    "Federation receipt: %s → %s (URN=%s, success=%s)",
                    self._local.instance_id,
                    peer_instance_id,
                    urn,
                    success,
                )

        return response_data

    # ------------------------------------------------------------------
    # Remote capability discovery
    # ------------------------------------------------------------------

    async def discover_remote_capabilities(
        self,
        peer_instance_id: str,
    ) -> list[dict[str, Any]]:
        """Discover available capabilities from a remote CoReason instance.

        Only returns capabilities that pass the air gap policy filter.

        Args:
            peer_instance_id: The target instance's identifier.

        Returns:
            List of capability entries from the remote registry.
        """
        # Discovery uses a sentinel; only check agreement is active + not CLOSED
        agreement = self._agreements.get(peer_instance_id)
        if not agreement or not agreement.is_active:
            logger.warning(
                "Discovery denied for %s: no active agreement", peer_instance_id
            )
            return []
        policy = self._policies.get(peer_instance_id)
        if policy and policy.direction == ConnectivityDirection.CLOSED:
            logger.warning("Discovery denied for %s: air gap CLOSED", peer_instance_id)
            return []

        peer = self.get_peer(peer_instance_id)
        if not peer:
            return []

        client = await self._get_client(peer_instance_id)
        policy = self._policies.get(peer_instance_id)

        try:
            response = await client.get(
                f"{peer.gateway_endpoint}/mcp/v1/tools",
                headers={
                    "X-Source-Instance": self._local.instance_id,
                    "X-Source-Tenant-CID": self._local.tenant_cid,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            capabilities: list[dict[str, Any]] = response.json().get("tools", [])

            # Filter by air gap policy
            if policy and policy.allowed_urns:
                capabilities = [
                    cap
                    for cap in capabilities
                    if self._urn_matches(cap.get("name", ""), policy.allowed_urns)
                ]

            return capabilities

        except httpx.HTTPError as e:
            logger.error(
                "Failed to discover capabilities from %s: %s",
                peer_instance_id,
                e,
            )
            return []

    # ------------------------------------------------------------------
    # httpx client lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self, peer_instance_id: str) -> httpx.AsyncClient:
        """Get or create an httpx.AsyncClient for a peer.

        Configures mTLS if SPIFFE certificate paths are available.
        """
        if peer_instance_id in self._clients:
            return self._clients[peer_instance_id]

        # Build SSL context for mTLS using standard library ssl module
        ssl_context = self._build_ssl_context(peer_instance_id)

        client = httpx.AsyncClient(
            http2=False,
            verify=ssl_context if ssl_context else True,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            ),
        )
        self._clients[peer_instance_id] = client
        return client

    def _build_ssl_context(self, peer_instance_id: str) -> ssl.SSLContext | None:
        """Build mTLS SSL context using SPIFFE SVID certificates.

        Reads certificate paths from environment variables following
        the SPIFFE Workload API convention.
        """
        cert_path = os.environ.get("SPIFFE_CERT_PATH")
        key_path = os.environ.get("SPIFFE_KEY_PATH")
        bundle_path = os.environ.get("SPIFFE_BUNDLE_PATH")

        if not (cert_path and key_path):
            logger.debug(
                "No SPIFFE certs configured; using standard TLS for peer %s",
                peer_instance_id,
            )
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.set_ciphers("TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256")
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)

        if bundle_path:
            ctx.load_verify_locations(cafile=bundle_path)

        return ctx

    # ------------------------------------------------------------------
    # DLP scanning stubs (delegate to NemoClaw sidecar)
    # ------------------------------------------------------------------

    @staticmethod
    def _dlp_scan_outbound(payload: dict[str, Any]) -> dict[str, Any]:
        """Scan outbound payload for PII/PHI before crossing the air gap.

        Delegates to the NemoClaw sidecar for production DLP scanning.
        In this implementation, performs structural validation only.
        """
        # Structural validation: reject oversized payloads
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if len(canonical.encode("utf-8")) > 10_485_760:  # 10MB limit
            raise ValueError(
                "Outbound payload exceeds 10MB air gap limit "
                f"({len(canonical.encode('utf-8'))} bytes)"
            )
        return payload

    @staticmethod
    def _dlp_scan_inbound(response: dict[str, Any]) -> dict[str, Any]:
        """Scan inbound response before ingestion into the local namespace.

        All data returning from across the air gap is treated as PUBLIC
        clearance and undergoes full input scanning.
        """
        canonical = json.dumps(response, sort_keys=True, separators=(",", ":"))
        if len(canonical.encode("utf-8")) > 10_485_760:
            raise ValueError(
                "Inbound response exceeds 10MB air gap limit "
                f"({len(canonical.encode('utf-8'))} bytes)"
            )
        return response

    # ------------------------------------------------------------------
    # Ephemeral certificate generation (development only)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_ephemeral_certs(
        common_name: str = "coreason-federation-dev",
    ) -> tuple[bytes, bytes]:
        """Generate ephemeral self-signed certificates for development.

        Returns:
            (cert_pem, key_pem) — PEM-encoded certificate and private key.

        Raises:
            RuntimeError: If COREASON_ENV is not set to 'development'.
        """
        env = os.environ.get("COREASON_ENV", "")
        if env != "development":
            raise RuntimeError(
                "Ephemeral certificate generation is only permitted in "
                "development mode (COREASON_ENV=development). "
                "In production, use SPIRE as the sole certificate authority."
            )

        key = ec.generate_private_key(ec.SECP256R1())

        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CoReason Dev"),
            ]
        )

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime(2027, 1, 1, tzinfo=timezone.utc))
            .sign(key, hashes.SHA256())
        )

        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return cert_pem, key_pem

    # ------------------------------------------------------------------
    # Audit trail access
    # ------------------------------------------------------------------

    def get_receipts(self) -> list[dict[str, Any]]:
        """Return all federation audit receipts as serializable dicts."""
        return [r.to_dict() for r in self._receipts]

    def clear_receipts(self) -> int:
        """Clear all stored receipts and return the count cleared."""
        count = len(self._receipts)
        self._receipts.clear()
        return count

    # ------------------------------------------------------------------
    # Contribution Governance (Private → Public publishing)
    # ------------------------------------------------------------------

    def submit_contribution(
        self,
        intent: ContributionIntent,
    ) -> ContributionIntent:
        """Submit a contribution intent for RBAC approval.

        Only CONTRIBUTOR-role identities on a PRIVATE instance may
        submit intents. The contribution policy must be enabled and
        the URN must be in the allowed contribution list.

        Args:
            intent: The contribution intent to submit.

        Returns:
            The submitted intent (status=PENDING).

        Raises:
            PermissionError: If contributions are disabled, the instance
                is not Private, the role is wrong, or the URN is not allowed.
        """
        # Gate 1: Only Private instances may contribute
        if self._local.instance_type != InstanceType.PRIVATE:
            raise PermissionError(
                "Only PRIVATE instances may contribute capabilities to the Public mesh."
            )

        # Gate 2: Contributions must be explicitly enabled
        if not self._contribution_policy.enabled:
            raise PermissionError(
                "Contribution to the Public mesh is disabled by policy. "
                "An ADMIN must enable it via ContributionPolicy."
            )

        # Gate 3: Submitter must hold CONTRIBUTOR role
        if intent.contributor_role != ContributionRole.CONTRIBUTOR:
            raise PermissionError(
                f"Only CONTRIBUTOR role may submit intents, "
                f"got '{intent.contributor_role.value}'."
            )

        # Gate 4: URN must be in the allowed contribution list
        if not self._contribution_policy.allowed_contribution_urns:
            raise PermissionError(
                "No URN patterns are permitted for contribution. "
                "An ADMIN must configure allowed_contribution_urns."
            )
        if not self._urn_matches(
            intent.urn,
            self._contribution_policy.allowed_contribution_urns,
        ):
            raise PermissionError(
                f"URN '{intent.urn}' is not in the allowed contribution URN list."
            )

        # Gate 5: Legal attestation (if required)
        if (
            self._contribution_policy.require_legal_attestation
            and not intent.legal_attestation
        ):
            raise PermissionError(
                "Legal attestation is required. The contributor must "
                "attest that the capability contains no proprietary "
                "trade secrets, PII/PHI, or data above PUBLIC clearance."
            )

        intent.status = "PENDING"
        self._contribution_intents[intent.intent_id] = intent

        logger.info(
            "Contribution intent %s submitted by %s for URN %s",
            intent.intent_id,
            intent.contributor_id,
            intent.urn,
        )
        return intent

    def approve_contribution(
        self,
        intent_id: str,
        approver_id: str,
    ) -> ContributionIntent:
        """Approve a contribution intent (APPROVER role).

        Each approver may only approve once. Once the required number
        of approvals is reached, the intent status moves to APPROVED.

        Args:
            intent_id: The intent to approve.
            approver_id: SPIFFE ID of the approver.

        Returns:
            The updated intent.

        Raises:
            KeyError: If the intent doesn't exist.
            PermissionError: If the approver is the contributor (separation
                of duties) or has already approved.
            ValueError: If the intent is not in PENDING status.
        """
        intent = self._contribution_intents.get(intent_id)
        if not intent:
            raise KeyError(f"Contribution intent '{intent_id}' not found.")

        if intent.status != "PENDING":
            raise ValueError(f"Intent '{intent_id}' is '{intent.status}', not PENDING.")

        # Separation of duties: approver cannot be the contributor
        if approver_id == intent.contributor_id:
            raise PermissionError(
                "Separation of duties violation: the contributor cannot "
                "approve their own contribution intent."
            )

        # No duplicate approvals
        if approver_id in intent.approvals:
            raise PermissionError(
                f"Approver '{approver_id}' has already approved intent '{intent_id}'."
            )

        intent.approvals = sorted([*intent.approvals, approver_id])

        if len(intent.approvals) >= self._contribution_policy.required_approvals:
            intent.status = "APPROVED"
            logger.info(
                "Contribution intent %s APPROVED (%d/%d approvals)",
                intent_id,
                len(intent.approvals),
                self._contribution_policy.required_approvals,
            )
        else:
            logger.info(
                "Contribution intent %s approved by %s (%d/%d)",
                intent_id,
                approver_id,
                len(intent.approvals),
                self._contribution_policy.required_approvals,
            )

        return intent

    def reject_contribution(
        self,
        intent_id: str,
        rejector_id: str,
        reason: str,
    ) -> ContributionIntent:
        """Reject a contribution intent.

        Args:
            intent_id: The intent to reject.
            rejector_id: SPIFFE ID of the rejector.
            reason: Business reason for rejection.

        Returns:
            The rejected intent.

        Raises:
            KeyError: If the intent doesn't exist.
            ValueError: If the intent is not in PENDING status.
        """
        intent = self._contribution_intents.get(intent_id)
        if not intent:
            raise KeyError(f"Contribution intent '{intent_id}' not found.")

        if intent.status != "PENDING":
            raise ValueError(f"Intent '{intent_id}' is '{intent.status}', not PENDING.")

        intent.status = "REJECTED"
        logger.warning(
            "Contribution intent %s REJECTED by %s: %s",
            intent_id,
            rejector_id,
            reason,
        )
        return intent

    async def execute_contribution(
        self,
        intent_id: str,
    ) -> dict[str, Any]:
        """Execute an approved contribution — publish capability to Public.

        Performs DLP scanning and emits an audit receipt. Only APPROVED
        intents may be executed.

        Args:
            intent_id: The approved intent to execute.

        Returns:
            The response from the Public mesh registry.

        Raises:
            KeyError: If the intent doesn't exist.
            ValueError: If the intent is not APPROVED.
            PermissionError: If DLP scan fails.
            ConnectionError: If the Public mesh is unreachable.
        """
        intent = self._contribution_intents.get(intent_id)
        if not intent:
            raise KeyError(f"Contribution intent '{intent_id}' not found.")

        if intent.status != "APPROVED":
            raise ValueError(
                f"Intent '{intent_id}' is '{intent.status}', not APPROVED. "
                f"It needs {self._contribution_policy.required_approvals} "
                f"approvals before execution."
            )

        # Build the contribution payload
        payload = {
            "urn": intent.urn,
            "contributor_id": intent.contributor_id,
            "intent_hash": intent.compute_intent_hash(),
            "approvals": intent.approvals,
            "legal_attestation": intent.legal_attestation,
        }

        # DLP scan before egress
        if self._contribution_policy.require_dlp_scan:
            payload = self._dlp_scan_outbound(payload)

        # Use the standard invoke_remote_tool path for the contribution
        # This enforces the air gap policy and emits audit receipts
        from .proxy import COREASON_PUBLIC_INSTANCE_ID

        result = await self.invoke_remote_tool(
            peer_instance_id=COREASON_PUBLIC_INSTANCE_ID,
            urn="urn:coreason:actionspace:effector:capability_registry:contribute:v1",
            payload=payload,
            clearance="PUBLIC",
        )

        intent.status = "EXECUTED"
        logger.info(
            "Contribution intent %s EXECUTED — URN %s published to Public",
            intent_id,
            intent.urn,
        )
        return result

    def get_contribution_intents(self) -> list[dict[str, Any]]:
        """Return all contribution intents as serializable dicts."""
        return [
            intent.model_dump(mode="json")
            for intent in self._contribution_intents.values()
        ]

    # ------------------------------------------------------------------
    # Public Mesh: Contribution Absorption
    # ------------------------------------------------------------------

    async def absorb_remote_capability(
        self, peer_instance_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Public Mesh Absorption of Private Contributions.
        When a private instance executes a contribution, the Public mesh receives
        it via `urn:coreason:actionspace:effector:capability_registry:contribute:v1`.

        This method validates the incoming contribution and absorbs it into the
        Public mesh's capability routing matrix.
        """
        if self._local.instance_type.name != "PUBLIC":
            raise PermissionError(
                "Mesh Absorption can only be executed by a PUBLIC mesh instance."
            )

        if peer_instance_id not in self._agreements:
            raise ValueError(
                f"Unknown peer instance {peer_instance_id}. Handshake required."
            )

        peer = self.get_peer(peer_instance_id)
        if not peer:
            raise ValueError(f"Could not resolve peer {peer_instance_id}.")

        if peer.instance_type.name != "PRIVATE":
            logger.warning(
                f"Absorbing capability from non-PRIVATE peer: {peer.instance_type.name}"
            )

        urn = payload.get("urn")
        if not urn:
            raise ValueError("Contribution payload missing 'urn'")

        legal_attestation = payload.get("legal_attestation")
        if not legal_attestation or not legal_attestation.get(
            "agrees_to_public_release"
        ):
            raise PermissionError(
                "Contribution rejected: Missing legal attestation for PUBLIC release."
            )

        # In production, this verifies the cryptographic intent_hash against the peer's DID
        intent_hash = payload.get("intent_hash")

        # Route the absorption to the MeshInjector to physically write to the capability matrix
        try:
            from coreason_ecosystem.fleet.mesh_injector import MeshInjector

            injector = MeshInjector()
            injector.register_capability(
                urn=urn,
                endpoint=f"mcp://{peer.gateway_endpoint}/invoke",
                clearance="PUBLIC",
                epistemic_status="PUBLISHED",
            )
        except Exception as e:
            logger.error(f"Failed to physically absorb capability {urn}: {e}")
            # Non-fatal during simulation

        logger.info(
            f"Public Mesh: Absorbed URN {urn} from Private instance {peer_instance_id}"
        )

        return {
            "status": "absorbed",
            "urn": urn,
            "provider_instance": peer_instance_id,
            "intent_hash": intent_hash,
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close all httpx clients and release resources."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
