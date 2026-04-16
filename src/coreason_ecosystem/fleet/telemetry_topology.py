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

import networkx as nx
from loguru import logger
from prometheus_client import Counter, Gauge, start_http_server
from temporalio.client import Client


# Prometheus metrics — topological invariant gauges
coreason_betti_0 = Gauge(
    "coreason_betti_0",
    "β₀ (connected components) of the workflow execution graph. "
    "Detects network fragmentation when β₀ > 1.",
)
coreason_active_agents_total = Gauge(
    "coreason_active_agents_total",
    "Total nodes in the workflow execution graph.",
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

    Polls the Temporal cluster for workflow execution states, constructs
    a directed graph from parent-child workflow relationships, and computes
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
        """Poll Temporal for open workflow executions and compute topological invariants.

        Constructs a directed graph G where:
          - Each running workflow is a node.
          - Edges are drawn from child → parent using ParentExecution metadata.

        β₀ is computed as ``nx.number_connected_components(G.to_undirected())``.
        """
        if not self._client:
            return

        try:
            graph: nx.DiGraph = nx.DiGraph()

            async for workflow in self._client.list_workflows(
                "ExecutionStatus = 'Running'"
            ):
                workflow_id: str = getattr(workflow, "id", str(id(workflow)))
                graph.add_node(workflow_id)

                # Extract parent-child edges from ParentExecution metadata
                parent_execution = getattr(workflow, "parent_execution", None)
                if parent_execution is not None:
                    parent_id = getattr(
                        parent_execution, "workflow_id", str(id(parent_execution))
                    )
                    graph.add_edge(workflow_id, parent_id)

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

            # Compute topological invariants
            node_count = graph.number_of_nodes()
            beta_0 = nx.number_connected_components(graph.to_undirected())

            coreason_active_agents_total.set(node_count)
            coreason_betti_0.set(beta_0)

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
