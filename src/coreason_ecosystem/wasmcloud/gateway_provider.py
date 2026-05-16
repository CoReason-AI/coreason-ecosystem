# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

"""MCP-to-NATS Gateway Provider — The Hollow Plane Bridge.

Replaces the custom FastAPI SSE transport in ``master_mcp.py`` with a
NATS-native routing layer.  External AI agents connect via MCP (JSON-RPC
over SSE/Streamable HTTP), and tool invocations are published as NATS
messages for routing to wasmCloud capability providers on the lattice.

This module implements the "Borrow, Don't Build" mandate by delegating:
  - Mesh networking → NATS Lattice (CNCF OSS)
  - Component sandboxing → wasmCloud / Wasmtime (CNCF OSS)
  - Registry state → wadm + JetStream (CNCF OSS)

The only proprietary logic retained is:
  - MCP protocol handling (MCP SDK — OSS)
  - JWT/OIDC validation (domain logic)
  - Semantic routing (domain logic, future phase)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

import nats
from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)

# NATS subject patterns for the CoReason lattice.
# These follow the wasmCloud convention: {namespace}.{category}.{capability}.{action}
SUBJECT_TOOL_INVOKE = "coreason.tool.{urn}.invoke"
SUBJECT_TOOL_DISCOVER = "coreason.tool.discover"
SUBJECT_REGISTRY_UPDATE = "coreason.registry.update"

# Default NATS connection URL (overridable via environment)
DEFAULT_NATS_URL = "nats://localhost:4222"

# Maximum payload size for NATS messages (aligned with the 10MB air gap limit)
MAX_PAYLOAD_BYTES = 10_485_760


class NATSGatewayProvider:
    """MCP-to-NATS bridge for the CoReason Governance Plane.

    This provider receives MCP JSON-RPC tool invocations from external AI agents
    and publishes them as NATS request-reply messages for routing to the
    appropriate wasmCloud capability provider on the lattice.

    Architecture:
        External Agent → MCP SSE → NATSGatewayProvider → NATS Lattice → Capability Provider

    Replaces:
        - ``master_mcp.py`` (custom FastAPI SSE gateway)
        - ``nemoclaw_client.py`` (custom httpx bridge)
        - Point-to-point httpx routing in ``invoke_actuator()``

    The MCP SSE endpoint layer (FastAPI + mcp.server) is preserved as a thin
    wrapper that delegates tool invocation to this provider.
    """

    def __init__(
        self,
        nats_url: str | None = None,
        tenant_cid: str = "889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531",
    ) -> None:
        """Initialize the NATS gateway provider.

        Args:
            nats_url: NATS server URL. Defaults to NATS_URL env var or localhost:4222.
            tenant_cid: The tenant CID for multi-tenancy enforcement.
        """
        self._nats_url = nats_url or os.environ.get("NATS_URL", DEFAULT_NATS_URL)
        self._tenant_cid = tenant_cid
        self._nc: NATSClient | None = None

    async def connect(self) -> None:
        """Connect to the NATS server.

        Establishes the connection to the NATS lattice. Must be called
        before any tool invocation.
        """
        if self._nc is not None and self._nc.is_connected:
            return

        self._nc = await nats.connect(
            self._nats_url,
            name="coreason-mcp-gateway",
            max_reconnect_attempts=10,
            reconnect_time_wait=2,
        )
        logger.info("Connected to NATS lattice at %s", self._nats_url)

    async def disconnect(self) -> None:
        """Gracefully disconnect from the NATS server."""
        if self._nc and self._nc.is_connected:
            await self._nc.drain()
            logger.info("Disconnected from NATS lattice")

    @property
    def is_connected(self) -> bool:
        """Check if the NATS connection is active."""
        return self._nc is not None and self._nc.is_connected

    async def invoke_tool(
        self,
        urn: str,
        arguments: dict[str, Any],
        spiffe_id: str = "",
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Invoke an MCP tool via the NATS lattice.

        Publishes a JSON-RPC request to the NATS subject corresponding to
        the target URN and awaits a reply from the capability provider.

        This replaces the custom httpx-based ``NemoClawBridgeClient.call_tool()``
        and the point-to-point routing in ``invoke_actuator()``.

        Args:
            urn: The URN of the capability to invoke.
            arguments: The tool arguments (JSON-serializable).
            spiffe_id: The caller's SPIFFE identity for zero-trust enforcement.
            timeout: Maximum wait time for a response (seconds).

        Returns:
            The JSON response from the capability provider.

        Raises:
            RuntimeError: If the NATS connection is not established.
            TimeoutError: If the capability provider does not respond in time.
            ValueError: If the payload exceeds the 10MB limit.
        """
        if not self._nc or not self._nc.is_connected:
            raise RuntimeError("NATS connection not established. Call connect() first.")

        # Build the JSON-RPC request envelope
        rpc_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": urn,
                "arguments": arguments,
            },
            "id": self._compute_request_id(arguments),
        }

        # Volumetric guard: enforce 10MB payload limit
        payload_bytes = json.dumps(
            rpc_request, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

        if len(payload_bytes) > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"Payload exceeds {MAX_PAYLOAD_BYTES} byte limit "
                f"({len(payload_bytes)} bytes). "
                "Reduce payload size or use streaming."
            )

        # Derive the NATS subject from the URN
        subject = SUBJECT_TOOL_INVOKE.format(urn=urn.replace(":", "."))

        # Add routing headers as NATS headers
        headers = {
            "X-Tenant-CID": self._tenant_cid,
            "X-Source-URN": "urn:coreason:actionspace:node:master_gateway:v1",
        }
        if spiffe_id:
            headers["X-SPIFFE-ID"] = spiffe_id

        logger.debug("Publishing tool invocation to %s", subject)

        # NATS request-reply pattern: publish and await response
        try:
            response = await self._nc.request(
                subject,
                payload_bytes,
                timeout=timeout,
                headers=headers,
            )
        except Exception as e:
            if "timeout" in str(e).lower():
                raise TimeoutError(
                    f"Capability provider for '{urn}' did not respond "
                    f"within {timeout}s on subject '{subject}'"
                ) from e
            raise RuntimeError(f"NATS request failed for '{urn}': {e}") from e

        # Parse the response
        try:
            result: dict[str, Any] = json.loads(response.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise RuntimeError(
                f"Invalid JSON response from capability provider '{urn}': {e}"
            ) from e

        return result

    async def discover_capabilities(self, timeout: float = 5.0) -> list[dict[str, Any]]:
        """Discover available capabilities on the NATS lattice.

        Publishes a discovery request and collects responses from all
        capability providers that are listening.

        This replaces ``SovereignMCPRegistry.discover_active_substrates()``.

        Args:
            timeout: Maximum wait time for discovery responses.

        Returns:
            List of capability descriptors from responding providers.
        """
        if not self._nc or not self._nc.is_connected:
            raise RuntimeError("NATS connection not established. Call connect() first.")

        capabilities: list[dict[str, Any]] = []
        inbox = self._nc.new_inbox()
        sub = await self._nc.subscribe(inbox)

        # Publish discovery request
        await self._nc.publish(
            SUBJECT_TOOL_DISCOVER,
            json.dumps({"action": "discover"}).encode("utf-8"),
            reply=inbox,
        )

        # Collect responses until timeout
        import asyncio

        try:
            async for msg in sub.messages:
                try:
                    cap = json.loads(msg.data.decode("utf-8"))
                    capabilities.append(cap)
                except json.JSONDecodeError, UnicodeDecodeError:
                    logger.warning("Invalid discovery response received")

                # Use a short timeout between messages
                try:
                    await asyncio.wait_for(sub.next_msg(), timeout=timeout)
                except TimeoutError:
                    break
        except Exception:
            logger.debug("Discovery collection ended", exc_info=True)
        finally:
            await sub.unsubscribe()

        logger.info("Discovered %d capabilities on the lattice", len(capabilities))
        return capabilities

    @staticmethod
    def _compute_request_id(arguments: dict[str, Any]) -> str:
        """Compute a deterministic request ID from the payload.

        Uses SHA-256 truncated to 16 hex characters, matching the
        existing behavior in master_mcp.py.
        """
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(canonical).hexdigest()[:16]
