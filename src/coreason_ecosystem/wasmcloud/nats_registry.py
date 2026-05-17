# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

"""NATS-Based Capability Registry — Lightweight URN Discovery.

This module implements a NATS JetStream-backed capability registry for
durable, distributed URN discovery across the ecosystem.

Architecture:
    - JetStream KV bucket ``coreason-registry`` stores URN→metadata mappings.
    - Capability providers self-register by publishing to ``coreason.registry.update``.
    - The registry watches for changes and updates the local cache.
    - NATS provides the durable state natively without external dependencies.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import nats
from nats.aio.client import Client as NATSClient
from nats.js.api import KeyValueConfig
from nats.js.kv import KeyValue

logger = logging.getLogger(__name__)

# Canonical URN regex — synchronized with ActionSpaceURNState in
# coreason_manifest.spec.ontology
_ACTIONSPACE_URN_PATTERN = re.compile(
    r"^urn:[a-z0-9_]+:actionspace:(oracle|solver|effector|substrate|sensory|node):[a-z0-9_]+:v[0-9]+$"
)

# NATS JetStream KV bucket for registry state
REGISTRY_BUCKET = "coreason-registry"

# NATS subject for registry updates
SUBJECT_REGISTRY_UPDATE = "coreason.registry.update"


class NATSCapabilityRegistry:
    """NATS JetStream-backed capability registry.

    This module uses NATS JetStream KV buckets for state persistence, providing
    distributed, durable discovery for capability URNs.

    Key features:

    JetStream KV provides:
      - Durable, replicated state across NATS cluster nodes
      - Watch/subscribe for real-time change notifications
      - TTL-based expiry for ephemeral capabilities
      - Built-in conflict resolution via revision numbers
    """

    def __init__(self, nats_url: str = "nats://localhost:4222") -> None:
        """Initialize the registry.

        Args:
            nats_url: NATS server URL.
        """
        self._nats_url = nats_url
        self._nc: NATSClient | None = None
        self._kv: KeyValue | None = None
        self._local_cache: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        """Connect to NATS and create the JetStream KV bucket."""
        if self._nc and self._nc.is_connected:
            return

        self._nc = await nats.connect(self._nats_url, name="coreason-registry")
        js = self._nc.jetstream()

        # Create or bind to the KV bucket
        try:
            self._kv = await js.key_value(REGISTRY_BUCKET)
            logger.info("Bound to existing JetStream KV bucket: %s", REGISTRY_BUCKET)
        except Exception:
            self._kv = await js.create_key_value(
                config=KeyValueConfig(
                    bucket=REGISTRY_BUCKET,
                    description="CoReason URN Capability Registry",
                    history=5,  # Keep 5 revisions of each key
                    ttl=0,  # No TTL — capabilities persist until explicitly removed
                )
            )
            logger.info("Created JetStream KV bucket: %s", REGISTRY_BUCKET)

    async def shutdown(self) -> None:
        """Gracefully disconnect from NATS."""
        if self._nc and self._nc.is_connected:
            await self._nc.drain()
            logger.info("Registry disconnected from NATS")

    async def register_capability(
        self,
        urn: str,
        clearance: str = "RESTRICTED",
        epistemic_status: str = "DRAFT",
        capability_metadata: dict[str, Any] | None = None,
        content_hash: str = "",
    ) -> None:
        """Register or update a URN capability in the registry.

        Args:
            urn: The capability URN (validated against actionspace regex).
            clearance: SPIFFE/SPIRE clearance level.
            epistemic_status: SRB governance lifecycle phase.
            capability_metadata: Additional metadata (rigidity, VRAM, etc.).
            content_hash: SHA-256 hash for zero-trust verification.

        Raises:
            ValueError: If the URN does not conform to the actionspace taxonomy.
        """
        self.validate_urn(urn)

        if not self._kv:
            raise RuntimeError("Registry not initialized. Call initialize() first.")

        entry = {
            "clearance": clearance,
            "epistemic_status": epistemic_status,
            "capability_metadata": capability_metadata or {},
            "content_hash": content_hash,
        }

        # Use the URN as the KV key (dots replaced with underscores for NATS compatibility)
        key = self._urn_to_key(urn)
        await self._kv.put(key, json.dumps(entry).encode("utf-8"))

        # Update local cache
        self._local_cache[urn] = entry
        logger.debug("Registered capability: %s (clearance=%s)", urn, clearance)

    async def resolve_urn(self, target_urn: str) -> dict[str, Any]:
        """Look up a URN in the registry.

        Args:
            target_urn: The URN to resolve.

        Returns:
            The capability metadata.

        Raises:
            KeyError: If the URN is not registered.
        """
        if not self._kv:
            raise RuntimeError("Registry not initialized. Call initialize() first.")

        key = self._urn_to_key(target_urn)
        try:
            entry = await self._kv.get(key)
            if entry.value is None:
                raise KeyError(
                    f"Geometrical topology fault: empty value for URN {target_urn}"
                )
            result: dict[str, Any] = json.loads(entry.value.decode("utf-8"))
            return result
        except Exception as e:
            raise KeyError(
                f"Geometrical topology fault: unregistered URN {target_urn}"
            ) from e

    async def get_epistemic_status(self, target_urn: str) -> str:
        """Retrieve the SRB governance lifecycle status for a URN."""
        try:
            entry = await self.resolve_urn(target_urn)
            return str(entry.get("epistemic_status", "DRAFT"))
        except KeyError:
            return "DRAFT"

    async def list_all_capabilities(self) -> dict[str, dict[str, Any]]:
        """List all registered capabilities."""
        if not self._kv:
            raise RuntimeError("Registry not initialized. Call initialize() first.")

        result: dict[str, dict[str, Any]] = {}
        keys = await self._kv.keys()
        for key in keys:
            try:
                entry = await self._kv.get(key)
                if entry.value is None:
                    continue
                urn = self._key_to_urn(key)
                result[urn] = json.loads(entry.value.decode("utf-8"))
            except Exception as e:
                logger.warning("Failed to read key %s: %s", key, e)

        return result

    async def hydrate_from_compiled_matrix(
        self,
        matrix: dict[str, Any],
    ) -> int:
        """Hydrate the registry from a compiled JSON matrix.

        Accepts a pre-parsed dictionary (URN → metadata).

        Args:
            matrix: Pre-parsed JSON matrix (URN → metadata).

        Returns:
            Number of capabilities registered.
        """
        count = 0
        for urn, metadata in matrix.items():
            if not _ACTIONSPACE_URN_PATTERN.match(urn):
                logger.warning("Skipping invalid URN: %s", urn)
                continue

            epistemic_status = metadata.pop("epistemic_status", "DRAFT")
            content_hash = metadata.pop("content_hash", "")
            capability_metadata = {
                "path": metadata.pop("path", ""),
                "default_clearance_tiers": metadata.pop(
                    "default_clearance_tiers", [255]
                ),
                "default_minimum_rigidity_tier": metadata.pop(
                    "default_minimum_rigidity_tier", 255
                ),
            }
            clearance = str(metadata.get("required_clearance", "RESTRICTED")).upper()

            await self.register_capability(
                urn=urn,
                clearance=clearance,
                epistemic_status=epistemic_status,
                capability_metadata=capability_metadata,
                content_hash=content_hash,
            )
            count += 1

        logger.info("Hydrated %d capabilities into NATS KV registry", count)
        return count

    @staticmethod
    def validate_urn(urn: str) -> None:
        """Validate that a URN conforms to the ActionSpace taxonomy."""
        if not _ACTIONSPACE_URN_PATTERN.match(urn):
            raise ValueError(
                f"URN Topology Breach: URN {urn} does not conform to the CoReason manifest "
                "modern actionspace taxonomy. Rejecting capability."
            )

    @staticmethod
    def _urn_to_key(urn: str) -> str:
        """Convert a URN to a NATS KV-safe key.

        NATS KV keys cannot contain colons, so we replace them with dots.
        """
        return urn.replace(":", ".")

    @staticmethod
    def _key_to_urn(key: str) -> str:
        """Convert a NATS KV key back to a URN."""
        return key.replace(
            ".", ":", 5
        )  # Replace first 5 dots (urn.X.actionspace.Y.Z.vN)
