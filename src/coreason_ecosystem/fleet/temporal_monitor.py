# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import asyncio
from typing import Any

from loguru import logger
from prometheus_client import Counter, Gauge, start_http_server
from temporalio.client import Client

from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile


# Prometheus metrics
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


class ThermodynamicMonitor:
    """Polls the Temporal cluster for workflow execution states and exposes Prometheus metrics.

    Bridges Temporal execution history (budget exhaustion, circuit breakers, active agents)
    into Prometheus gauges and counters for Grafana dashboards.
    """

    def __init__(
        self,
        temporal_host: str = "localhost:7233",
        prometheus_port: int = 9090,
        polling_interval_sec: int = 10,
    ) -> None:
        self.temporal_host = temporal_host
        self.prometheus_port = prometheus_port
        self.polling_interval_sec = polling_interval_sec
        self._client: Client | None = None
        self._running = False

        # Legacy compat
        self._mock_derivative = 1.5
        self._mock_hardware_profile = HardwareProfile(
            min_vram_gb=16.0,
            provider_whitelist=["aws", "vast"],
            accelerator_type="ampere",
        )
        self._mock_security_profile = SecurityProfile(network_isolation=True)

    async def connect(self) -> None:
        """Connect to the Temporal cluster."""
        try:
            self._client = await Client.connect(self.temporal_host)
            logger.info(f"ThermodynamicMonitor connected to Temporal at {self.temporal_host}")
        except Exception as e:
            logger.warning(f"Failed to connect to Temporal: {e}. Running in degraded mode.")

    async def _poll_workflows(self) -> None:
        """Poll Temporal for open workflow executions and update Prometheus metrics."""
        if not self._client:
            return

        try:
            active_count = 0
            async for workflow in self._client.list_workflows("ExecutionStatus = 'Running'"):
                active_count += 1

                # Check for circuit breaker signals in search attributes
                search_attrs = getattr(workflow, "search_attributes", {})
                if search_attrs:
                    raw_attrs: dict[str, Any] = dict(search_attrs) if not isinstance(search_attrs, dict) else search_attrs
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
        logger.info("ThermodynamicMonitor stopped.")

    # Legacy compatibility methods
    async def get_queue_derivative(self) -> float:
        """Simulate fetching Temporal kinetic-queue depth via Prometheus."""
        await asyncio.sleep(0.1)
        return self._mock_derivative

    async def get_active_task_hardware_profile(self) -> HardwareProfile | None:
        """Simulate fetching the requirements of the pending tasks."""
        await asyncio.sleep(0.1)
        return self._mock_hardware_profile

    async def get_active_task_security_profile(self) -> SecurityProfile | None:
        """Simulate fetching the security requirements of the pending tasks."""
        await asyncio.sleep(0.1)
        return self._mock_security_profile
