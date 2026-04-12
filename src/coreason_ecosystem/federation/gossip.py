# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""P2P Gossip Protocol for Federated Swarm Discovery.

Implements the Tensor Beacon emission and reception protocol for
B2B swarm federation. Broadcasts FederatedDiscoveryManifests to
bootstrap nodes over mTLS and evaluates incoming beacons for
ontological overlap before authorizing handshake initiation.

Security constraints:
- Only SHA-256 ontology hashes and public MCP endpoints are broadcast.
- Internal SemanticNodeState text chunks are NEVER exposed.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from typing import Any

from loguru import logger


# ── Bootstrap Configuration ────────────────────────────────────────────

DEFAULT_BEACON_INTERVAL_SECONDS = 60
MAX_PEER_STALENESS_SECONDS = 300


class GossipDaemon:
    """Lightweight background daemon for P2P Tensor Beacon broadcasts.

    Periodically emits the local swarm's FederatedDiscoveryManifest
    to known bootstrap nodes and processes incoming beacons for
    ontological overlap detection.
    """

    def __init__(
        self,
        swarm_id: str,
        local_manifest: dict[str, Any],
        bootstrap_nodes: list[str] | None = None,
        mtls_cert_path: str | None = None,
        mtls_key_path: str | None = None,
        beacon_interval: int = DEFAULT_BEACON_INTERVAL_SECONDS,
    ) -> None:
        self.swarm_id = swarm_id
        self.local_manifest = local_manifest
        self.bootstrap_nodes = bootstrap_nodes or []
        self.mtls_cert_path = mtls_cert_path
        self.mtls_key_path = mtls_key_path
        self.beacon_interval = beacon_interval

        # Peer registry: swarm_id -> {manifest, last_seen_ns, overlap}
        self.peer_registry: dict[str, dict[str, Any]] = {}

        # Handshake queue for SLA evaluation
        self._handshake_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        self._running = False

    def build_tensor_beacon(self) -> dict[str, Any]:
        """Build a sanitized beacon payload for broadcast.

        Only exposes SHA-256 ontology hashes and public endpoints.
        Never exposes internal SemanticNodeState text.
        """
        supported_ontologies = self.local_manifest.get("supported_ontologies", [])
        ontology_hashes = [
            hashlib.sha256(onto.encode("utf-8")).hexdigest()
            for onto in supported_ontologies
        ]

        return {
            "beacon_id": f"beacon-{uuid.uuid4().hex[:12]}",
            "swarm_id": self.swarm_id,
            "ontology_hashes": ontology_hashes,
            "public_mcp_endpoint": self.local_manifest.get("public_mcp_endpoint", ""),
            "supported_topologies": self.local_manifest.get("supported_topologies", []),
            "max_permitted_classification": self.local_manifest.get(
                "max_permitted_classification", "UNCLASSIFIED"
            ),
            "geographic_region": self.local_manifest.get("geographic_region", ""),
            "grid_carbon_intensity": self.local_manifest.get("grid_carbon_intensity", 0.0),
            "timestamp_ns": time.time_ns(),
        }

    async def broadcast_tensor_beacon(
        self, manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Broadcast the swarm's tensor beacon to all bootstrap nodes via mTLS.

        Args:
            manifest: Optional override manifest. Uses local_manifest if None.

        Returns:
            Summary dict with broadcast results per node.
        """
        beacon = manifest or self.build_tensor_beacon()
        results: dict[str, str] = {}

        try:
            import httpx  # type: ignore
        except ImportError:
            logger.warning("httpx not installed. Beacon broadcast skipped.")
            return {"error": "httpx_not_installed", "beacon": beacon}

        ssl_context = None
        if self.mtls_cert_path and self.mtls_key_path:
            ssl_context = httpx.create_ssl_context(
                cert=(self.mtls_cert_path, self.mtls_key_path),
            )

        async with httpx.AsyncClient(verify=ssl_context or True, timeout=10.0) as client:
            for node_url in self.bootstrap_nodes:
                endpoint = f"{node_url.rstrip('/')}/api/v1/federation/beacon"
                try:
                    response = await client.post(endpoint, json=beacon)
                    if response.status_code == 200:
                        results[node_url] = "delivered"
                        logger.info(f"[Gossip] Beacon delivered to {node_url}")
                    else:
                        results[node_url] = f"rejected:{response.status_code}"
                        logger.warning(
                            f"[Gossip] Beacon rejected by {node_url}: {response.status_code}"
                        )
                except Exception as e:
                    results[node_url] = f"unreachable:{e}"
                    logger.debug(f"[Gossip] Node {node_url} unreachable: {e}")

        return {"beacon_id": beacon["beacon_id"], "results": results}

    async def ingest_remote_beacon(self, beacon: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming beacon from a remote swarm.

        Checks for ontological overlap via SHA-256 hash intersection.
        If overlap exists, enqueues the beacon for SLA evaluation.

        Args:
            beacon: The remote swarm's tensor beacon payload.

        Returns:
            Evaluation result with overlap status.
        """
        remote_swarm_id = beacon.get("swarm_id", "unknown")

        if remote_swarm_id == self.swarm_id:
            return {"status": "self_beacon_ignored"}

        # Compute ontological overlap
        local_hashes = set(self.build_tensor_beacon()["ontology_hashes"])
        remote_hashes = set(beacon.get("ontology_hashes", []))
        overlap = local_hashes & remote_hashes

        # Update peer registry
        self.peer_registry[remote_swarm_id] = {
            "manifest": beacon,
            "last_seen_ns": time.time_ns(),
            "overlap_count": len(overlap),
            "overlap_hashes": list(overlap),
        }

        if overlap:
            logger.info(
                f"[Gossip] Ontological overlap detected with {remote_swarm_id}: "
                f"{len(overlap)} shared hash(es). Enqueueing for SLA evaluation."
            )
            await self._handshake_queue.put(beacon)
            return {
                "status": "overlap_detected",
                "remote_swarm_id": remote_swarm_id,
                "overlap_count": len(overlap),
                "handshake_authorized": True,
            }

        logger.debug(
            f"[Gossip] No ontological overlap with {remote_swarm_id}. "
            f"Beacon registered but no handshake."
        )
        return {
            "status": "no_overlap",
            "remote_swarm_id": remote_swarm_id,
            "overlap_count": 0,
            "handshake_authorized": False,
        }

    async def get_next_handshake_candidate(
        self, timeout: float = 5.0,
    ) -> dict[str, Any] | None:
        """Retrieve the next beacon queued for SLA handshake evaluation."""
        try:
            return await asyncio.wait_for(self._handshake_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def prune_stale_peers(self) -> int:
        """Remove peers that haven't sent a beacon within the staleness window."""
        now_ns = time.time_ns()
        cutoff_ns = now_ns - (MAX_PEER_STALENESS_SECONDS * 1_000_000_000)
        stale = [
            sid for sid, info in self.peer_registry.items()
            if info["last_seen_ns"] < cutoff_ns
        ]
        for sid in stale:
            del self.peer_registry[sid]
        if stale:
            logger.info(f"[Gossip] Pruned {len(stale)} stale peer(s).")
        return len(stale)

    async def run_daemon(self) -> None:
        """Run the gossip daemon loop. Broadcasts beacons at fixed intervals."""
        self._running = True
        logger.info(
            f"[Gossip] Daemon started for swarm {self.swarm_id}. "
            f"Beacon interval: {self.beacon_interval}s"
        )
        while self._running:
            try:
                await self.broadcast_tensor_beacon()
                self.prune_stale_peers()
            except Exception as e:
                logger.error(f"[Gossip] Daemon error: {e}")
            await asyncio.sleep(self.beacon_interval)

    def stop(self) -> None:
        """Stop the gossip daemon."""
        self._running = False
        logger.info(f"[Gossip] Daemon stopped for swarm {self.swarm_id}.")
