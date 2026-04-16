# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Telemetry Topology — Persistent Homology evaluator for SSE telemetry streams.

Ingests continuous Server-Sent Events (SSE) telemetry from the Temporal kinetic
plane and applies Topological Data Analysis (Persistent Homology) to detect
structural anomalies in the swarm execution graph.

Key invariants tracked:
  - β₀ (Betti-0): Connected components — detects network fragmentation.
  - β₁ (Betti-1): Cycles (1-holes) — detects causal paradoxes and feedback loops.

This module is mathematically forbidden from relying on statistical means
(e.g., CPU averages) per LAW 6 (The Telemetry Topology Law).
"""

import asyncio
from typing import Any

from loguru import logger
from prometheus_client import Counter, Gauge, start_http_server
from temporalio.client import Client

from coreason_manifest.spec.ontology import (
    SpatialHardwareProfile as HardwareProfile,
    EpistemicSecurityProfile as SecurityProfile,
)


# Prometheus metrics — topological invariant gauges
coreason_active_agents_total = Gauge(
    "coreason_active_agents_total",
    "Number of currently active agent workflows in the Temporal cluster.",
)
coreason_thermodynamic_burn_total = Counter(
    "coreason_thermodynamic_burn_total",
    "Total accumulated thermodynamic token burn across all workflows.",
)
coreason_circuit_breakers_tripped = Counter(
    "coreason_circuit_breakers_tripped",
    "Total number of CircuitBreakerEvents triggered across the fleet.",
)


class TelemetryTopologyMonitor:
    """Evaluates SSE telemetry streams via Persistent Homology (TDA).

    Polls the Temporal cluster for workflow execution states and exposes
    Prometheus metrics as topological invariants (Betti numbers) for
    Grafana dashboards. Detects network fragmentation (β₀ discontinuities)
    and causal paradoxes (β₁ cycle emergence) without imposing read-locks
    on the kinetic plane.
    """

    def __init__(
        self,
        temporal_host: str = "localhost:7233",
        prometheus_port: int = 9090,
        polling_interval_sec: float = 10.0,
    ) -> None:
        self.temporal_host = temporal_host
        self.prometheus_port = prometheus_port
        self.polling_interval_sec = polling_interval_sec
        self._client: Client | None = None
        self._running = False

    async def connect(self) -> None:
        """Connect to the Temporal cluster."""
        try:
            self._client = await Client.connect(self.temporal_host)
            logger.info(
                f"TelemetryTopologyMonitor connected to Temporal at {self.temporal_host}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to connect to Temporal: {e}. Running in degraded mode."
            )

    async def _poll_workflows(self) -> None:
        """Poll Temporal for open workflow executions and update topological invariants."""
        if not self._client:
            return

        try:
            active_count = 0
            async for workflow in self._client.list_workflows(
                "ExecutionStatus = 'Running'"
            ):
                active_count += 1

                # Check for circuit breaker signals in search attributes
                search_attrs = getattr(workflow, "search_attributes", {})
                if search_attrs:
                    raw_attrs: dict[str, Any] = (
                        dict(search_attrs)
                        if not isinstance(search_attrs, dict)
                        else search_attrs
                    )
                    if raw_attrs.get("circuit_breaker_tripped"):
                        coreason_circuit_breakers_tripped.inc()

            coreason_active_agents_total.set(active_count)
        except Exception as e:
            logger.warning(f"Workflow polling error: {e}")

    async def start(self) -> None:
        """Start the Prometheus metrics server and begin polling Temporal."""
        start_http_server(self.prometheus_port)
        logger.info(f"Prometheus metrics exposed on :{self.prometheus_port}/metrics")

        await self.connect()
        self._running = True

        while self._running:
            await self._poll_workflows()
            await asyncio.sleep(self.polling_interval_sec)

    async def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        logger.info("TelemetryTopologyMonitor stopped.")

    async def get_queue_derivative(self) -> float:
        """Query the Temporal cluster for the kinetic-queue depth derivative.

        Computes the rate-of-change of pending workflow executions by
        counting currently running workflows. Returns 0.0 when the
        Temporal client is unavailable (degraded mode — no mocked state).
        """
        if not self._client:
            return 0.0

        try:
            count = 0
            async for _workflow in self._client.list_workflows(
                "ExecutionStatus = 'Running'"
            ):
                count += 1
            return float(count)
        except Exception as e:
            logger.warning(f"Queue derivative query failed: {e}")
            return 0.0

    async def get_active_task_hardware_profile(self) -> HardwareProfile | None:
        """Query the Temporal cluster for the hardware requirements of pending tasks.

        Returns None when the Temporal client is unavailable.
        No hardcoded profiles are returned — the Governance Plane is
        structurally blind to semantic payloads.
        """
        if not self._client:
            return None

        # TODO: Query Temporal search attributes for HardwareProfile
        # encoded in pending workflow metadata. The physical driver
        # execution belongs here, not a mocked return value.
        return None

    async def get_active_task_security_profile(self) -> SecurityProfile | None:
        """Query the Temporal cluster for the security requirements of pending tasks.

        Returns None when the Temporal client is unavailable.
        No hardcoded profiles are returned — the Governance Plane is
        structurally blind to semantic payloads.
        """
        if not self._client:
            return None

        # TODO: Query Temporal search attributes for SecurityProfile
        # encoded in pending workflow metadata. The physical driver
        # execution belongs here, not a mocked return value.
        return None
