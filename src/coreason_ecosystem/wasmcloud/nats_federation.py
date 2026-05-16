# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

"""NATS-Based Federation — Air Gap via Leaf Nodes.

Replaces ``federation/proxy.py`` (1,049 lines) and ``federation/policy.py``
(375 lines) with a NATS-native federation mechanism.

Architecture:
    Instead of custom httpx point-to-point mTLS connections, federation is
    handled by NATS leaf nodes + accounts:

    - **Private → Public:** Private instance connects as a NATS leaf node
      to the Public mesh's NATS server. Subject-based authorization controls
      which capabilities the Private instance can access.

    - **Private → Private (DMZ):** Both instances connect as leaf nodes to
      a shared NATS server (or use NATS gateway mode). Bilateral agreements
      are enforced via NATS account isolation.

    - **Air Gap Control:** NATS account imports/exports replace the custom
      ``AirGapPolicy`` Pydantic model. The NATS server config natively
      enforces which subjects (capabilities) are accessible.

    - **DLP Scanning:** NemoClaw DLP scanning is implemented as a NATS
      service (request-reply) that payloads pass through before crossing
      the air gap.

    - **Audit Trail:** ``FederatedExecutionReceipt`` events are published
      to a JetStream stream for durable, append-only audit.

Replaces:
    - ``federation/proxy.py`` (FederationProxy, 1,049 lines)
    - ``federation/policy.py`` (AirGapPolicy, FederationAgreementState, etc., 375 lines)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import nats
from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)

# NATS subjects for federation operations
SUBJECT_FEDERATION_INVOKE = "coreason.federation.{peer_id}.invoke"
SUBJECT_FEDERATION_AUDIT = "coreason.federation.audit"
SUBJECT_DLP_SCAN = "coreason.dlp.scan"

# Default leaf node connection URL (the Public mesh's NATS)
DEFAULT_PUBLIC_NATS_URL = "nats://nats.mesh.coreason.ai:7422"


class FederatedExecutionReceipt:
    """Immutable audit record for cross-instance traffic.

    Published to the ``coreason.federation.audit`` JetStream stream
    after every successful (or failed) cross-instance invocation.

    Replaces the in-memory receipt pattern in ``proxy.py``.
    """

    __slots__ = (
        "receipt_id",
        "agreement_id",
        "source_instance",
        "destination_instance",
        "urn",
        "timestamp",
        "status",
        "payload_hash",
        "dlp_passed",
    )

    def __init__(
        self,
        receipt_id: str,
        agreement_id: str,
        source_instance: str,
        destination_instance: str,
        urn: str,
        status: str = "SUCCESS",
        payload_hash: str = "",
        dlp_passed: bool = True,
    ) -> None:
        self.receipt_id = receipt_id
        self.agreement_id = agreement_id
        self.source_instance = source_instance
        self.destination_instance = destination_instance
        self.urn = urn
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.status = status
        self.payload_hash = payload_hash
        self.dlp_passed = dlp_passed

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for NATS/JetStream publishing."""
        return {
            "receipt_id": self.receipt_id,
            "agreement_id": self.agreement_id,
            "source_instance": self.source_instance,
            "destination_instance": self.destination_instance,
            "urn": self.urn,
            "timestamp": self.timestamp,
            "status": self.status,
            "payload_hash": self.payload_hash,
            "dlp_passed": self.dlp_passed,
        }


class NATSFederationProxy:
    """NATS-native federation proxy for cross-instance communication.

    Replaces the 1,049-line ``FederationProxy`` with a NATS leaf node
    architecture:

    1. **Connection:** Uses NATS leaf node connections instead of custom
       httpx mTLS clients. The NATS server handles TLS via SPIFFE/SPIRE
       SVIDs natively.

    2. **Authorization:** Uses NATS account-based subject isolation instead
       of custom ``AirGapPolicy`` enforcement. The NATS server config
       defines which subjects each account can access.

    3. **DLP Scanning:** Invokes NemoClaw as a NATS service (request-reply)
       instead of a custom httpx bridge.

    4. **Audit:** Publishes ``FederatedExecutionReceipt`` to a JetStream
       stream instead of in-memory accumulation.
    """

    def __init__(
        self,
        local_instance_id: str,
        local_nats_url: str = "nats://localhost:4222",
        public_nats_url: str | None = None,
        require_dlp: bool = True,
    ) -> None:
        """Initialize the federation proxy.

        Args:
            local_instance_id: This instance's identity (e.g., 'alpha.internal').
            local_nats_url: URL of this instance's NATS server.
            public_nats_url: URL of the Public mesh NATS (for leaf node connection).
            require_dlp: Whether DLP scanning is mandatory for cross-instance traffic.
        """
        self._instance_id = local_instance_id
        self._local_nats_url = local_nats_url
        self._public_nats_url = public_nats_url or os.environ.get(
            "COREASON_PUBLIC_NATS_URL", DEFAULT_PUBLIC_NATS_URL
        )
        self._require_dlp = require_dlp
        self._nc: NATSClient | None = None
        self._js: Any = None

    async def connect(self) -> None:
        """Connect to the local NATS server.

        The leaf node connection to the Public mesh is handled by the
        NATS server configuration (nats-server.conf), not by this client.
        This client connects to the local NATS and relies on leaf node
        subject imports/exports for cross-instance access.
        """
        if self._nc and self._nc.is_connected:
            return

        self._nc = await nats.connect(
            self._local_nats_url,
            name=f"federation-proxy-{self._instance_id}",
            max_reconnect_attempts=10,
            reconnect_time_wait=2,
        )
        self._js = self._nc.jetstream()

        # Ensure the audit stream exists
        try:
            await self._js.find_stream_name_by_subject(SUBJECT_FEDERATION_AUDIT)
        except Exception:
            from nats.js.api import RetentionPolicy, StreamConfig

            await self._js.add_stream(
                StreamConfig(
                    name="coreason-federation-audit",
                    subjects=[SUBJECT_FEDERATION_AUDIT],
                    description="Immutable audit trail for cross-instance traffic",
                    retention=RetentionPolicy.LIMITS,
                    max_msgs=1_000_000,
                    max_bytes=1_073_741_824,  # 1GB
                )
            )
            logger.info("Created federation audit stream")

        logger.info("Federation proxy connected for instance: %s", self._instance_id)

    async def disconnect(self) -> None:
        """Gracefully disconnect."""
        if self._nc and self._nc.is_connected:
            await self._nc.drain()
            logger.info("Federation proxy disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if the NATS connection is active."""
        return self._nc is not None and self._nc.is_connected

    async def invoke_remote_tool(
        self,
        target_instance_id: str,
        urn: str,
        arguments: dict[str, Any],
        agreement_id: str = "",
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Invoke a tool on a remote CoReason instance via NATS federation.

        Replaces ``FederationProxy.invoke_remote_tool()`` which used custom
        httpx mTLS connections.

        The NATS leaf node architecture means:
        1. This client publishes to a NATS subject
        2. The local NATS server forwards it via leaf node to the remote NATS
        3. The remote capability provider receives and responds
        4. Response flows back through the leaf node connection

        All of this is transparent to this code — NATS handles the routing.

        Args:
            target_instance_id: The remote instance ID.
            urn: The URN of the capability to invoke.
            arguments: Tool arguments.
            agreement_id: The federation agreement governing this invocation.
            timeout: Response timeout in seconds.

        Returns:
            The JSON response from the remote capability provider.
        """
        if not self._nc or not self._nc.is_connected:
            raise RuntimeError(
                "Federation proxy not connected. Call connect() first."
            )

        # Step 1: DLP scanning (if required)
        if self._require_dlp:
            await self._dlp_scan(urn, arguments)

        # Step 2: Build the federated request envelope
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": urn,
                "arguments": arguments,
            },
            "id": self._compute_request_id(arguments),
            "federation": {
                "source_instance": self._instance_id,
                "target_instance": target_instance_id,
                "agreement_id": agreement_id,
            },
        }

        payload_bytes = json.dumps(
            request, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

        # Volumetric guard
        if len(payload_bytes) > 10_485_760:
            raise ValueError(
                f"Federated payload exceeds 10MB limit ({len(payload_bytes)} bytes)"
            )

        # Step 3: Publish to the federation subject
        subject = SUBJECT_FEDERATION_INVOKE.format(
            peer_id=target_instance_id.replace(".", "_")
        )

        try:
            response = await self._nc.request(
                subject, payload_bytes, timeout=timeout
            )
        except Exception as e:
            # Emit failure receipt
            await self._emit_receipt(
                agreement_id=agreement_id,
                destination=target_instance_id,
                urn=urn,
                status="FAILED",
                payload_hash=hashlib.sha256(payload_bytes).hexdigest()[:16],
            )
            if "timeout" in str(e).lower():
                raise TimeoutError(
                    f"Remote instance '{target_instance_id}' did not respond "
                    f"within {timeout}s for URN '{urn}'"
                ) from e
            raise RuntimeError(
                f"Federation request failed: {e}"
            ) from e

        # Step 4: Emit success receipt
        await self._emit_receipt(
            agreement_id=agreement_id,
            destination=target_instance_id,
            urn=urn,
            status="SUCCESS",
            payload_hash=hashlib.sha256(payload_bytes).hexdigest()[:16],
        )

        # Parse response
        try:
            result: dict[str, Any] = json.loads(response.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise RuntimeError(
                f"Invalid federation response from '{target_instance_id}': {e}"
            ) from e

        return result

    async def _dlp_scan(self, urn: str, arguments: dict[str, Any]) -> None:
        """Submit payload to NemoClaw DLP scanning via NATS.

        Replaces the custom httpx-based NemoClaw bridge.
        NemoClaw runs as a NATS service (request-reply pattern).
        """
        if not self._nc:
            raise RuntimeError("Not connected")

        scan_request = json.dumps({
            "urn": urn,
            "payload": arguments,
            "scan_type": "FEDERATION_EGRESS",
        }).encode("utf-8")

        try:
            response = await self._nc.request(
                SUBJECT_DLP_SCAN, scan_request, timeout=10.0
            )
            result = json.loads(response.data.decode("utf-8"))
            if not result.get("passed", False):
                raise PermissionError(
                    f"DLP scan BLOCKED federation egress for URN '{urn}': "
                    f"{result.get('reason', 'Unknown violation')}"
                )
            logger.debug("DLP scan passed for URN: %s", urn)
        except TimeoutError:
            raise RuntimeError(
                "NemoClaw DLP scanner did not respond within 10s. "
                "Blocking federation egress per security policy."
            )

    async def _emit_receipt(
        self,
        agreement_id: str,
        destination: str,
        urn: str,
        status: str,
        payload_hash: str = "",
    ) -> None:
        """Publish an immutable audit receipt to the JetStream stream.

        Replaces in-memory receipt accumulation in ``FederationProxy``.
        """
        if not self._js:
            return

        receipt = FederatedExecutionReceipt(
            receipt_id=hashlib.sha256(
                f"{self._instance_id}:{destination}:{urn}:{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()[:16],
            agreement_id=agreement_id,
            source_instance=self._instance_id,
            destination_instance=destination,
            urn=urn,
            status=status,
            payload_hash=payload_hash,
        )

        try:
            await self._js.publish(
                SUBJECT_FEDERATION_AUDIT,
                json.dumps(receipt.to_dict()).encode("utf-8"),
            )
        except Exception as e:
            logger.warning("Failed to emit federation audit receipt: %s", e)

    @staticmethod
    def _compute_request_id(arguments: dict[str, Any]) -> str:
        """Compute a deterministic request ID from the payload."""
        canonical = json.dumps(
            arguments, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()[:16]
