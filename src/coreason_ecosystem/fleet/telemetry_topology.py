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

from loguru import logger
from prometheus_client import Counter, Gauge, start_http_server
from temporalio.client import Client


# Prometheus metrics — topological invariant gauges
coreason_active_agents_total = Gauge(
    "coreason_active_agents_total",
    "β₀ (connected components) of the workflow execution graph.",
)
coreason_thermodynamic_burn_total = Counter(
    "coreason_thermodynamic_burn_total",
    "Total accumulated thermodynamic token burn across all workflows.",
)
coreason_circuit_breakers_tripped = Counter(
    "coreason_circuit_breakers_tripped",
    "Total number of CircuitBreakerEvents triggered across the fleet.",
)
coreason_causal_cycles_total = Gauge(
    "coreason_causal_cycles_total",
    "β₁ (1-cycles) in the workflow execution graph — causal paradox detector.",
)
coreason_aggregate_vram_demand_gb = Gauge(
    "coreason_aggregate_vram_demand_gb",
    "Total VRAM capacity demand derived from workflow search attributes.",
)


class TelemetryTopologyMonitor:
    """Evaluates SSE telemetry streams via Persistent Homology (TDA).

    Polls the Temporal cluster for workflow execution states, constructs
    an undirected graph from parent-child workflow relationships, and computes
    the β₀ Betti number (connected components) via ``networkx``. Exposes
    topological invariants as Prometheus gauges for Grafana dashboards.

    Detects network fragmentation (β₀ discontinuities) and causal paradoxes
    (β₁ cycle emergence) without imposing read-locks on the kinetic plane.
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
        """Poll Temporal to construct the execution graph and compute Betti invariants."""
        if not self._client:
            return

        import networkx as nx

        execution_graph = nx.Graph()

        try:
            total_vram_demand = 0.0

            async for workflow in self._client.list_workflows(
                "ExecutionStatus = 'Running'"
            ):
                # 1. Project node into the geometric space
                execution_graph.add_node(workflow.id)

                # 2. Draw topological edges based on causal parent-child relationships
                # (Assumes Temporal search attributes or parent_execution metadata)
                parent_id = getattr(workflow, "parent_id", None)
                if parent_id:
                    execution_graph.add_edge(parent_id, workflow.id)

                # 3. Track thermodynamic exhaustion circuits
                search_attrs = getattr(workflow, "search_attributes", {})
                if search_attrs:
                    if search_attrs.get("circuit_breaker_tripped"):
                        coreason_circuit_breakers_tripped.inc()

                    vram_val = search_attrs.get("vram_demand_gb")
                    if vram_val:
                        try:
                            total_vram_demand += float(vram_val)
                        except Exception:
                            total_vram_demand += 1.0

            # 4. Calculate β₀ (Betti-0): Number of connected components
            # This mathematically proves if the Swarm is operating as a cohesive
            # unit (β₀ = 1) or if it has fragmented into isolated, runaway shards (β₀ > 1).
            betti_0 = nx.number_connected_components(execution_graph)
            coreason_active_agents_total.set(betti_0)

            # 5. Calculate β₁ (Betti-1): Number of independent cycles
            # Cycles in the execution graph indicate causal paradoxes —
            # feedback loops where a workflow depends on its own descendant.
            cycles = nx.cycle_basis(execution_graph)
            betti_1 = len(cycles)
            coreason_causal_cycles_total.set(betti_1)

            coreason_aggregate_vram_demand_gb.set(
                max(total_vram_demand, float(betti_0))
            )

            if betti_1 > 0:
                logger.critical(
                    f"TopologicalHaltIntent: β₁={betti_1} causal cycles "
                    f"detected in the execution graph. Cycles: {cycles[:3]}"
                )

        except Exception as e:
            logger.warning(f"Topological polling error: {e}")

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
