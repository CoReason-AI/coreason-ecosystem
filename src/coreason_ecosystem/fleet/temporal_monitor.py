# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.
#

import asyncio

from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile  # type: ignore[attr-defined]


class ThermodynamicMonitor:
    def __init__(self, prometheus_url: str = "http://localhost:9090") -> None:
        self.prometheus_url = prometheus_url
        self._mock_derivative = 1.5
        self._mock_hardware_profile = HardwareProfile(
            min_vram_gb=16.0,
            provider_whitelist=["aws", "vast"],
            accelerator_type="ampere",
        )
        self._mock_security_profile = SecurityProfile(network_isolation=True)

    async def get_queue_derivative(self) -> float:
        # Simulate fetching Temporal kinetic-queue depth via Prometheus HTTP call.
        await asyncio.sleep(0.1)
        return self._mock_derivative

    async def get_active_task_hardware_profile(self) -> HardwareProfile | None:
        # Simulate fetching the requirements of the pending tasks
        await asyncio.sleep(0.1)
        return self._mock_hardware_profile

    async def get_active_task_security_profile(self) -> SecurityProfile | None:
        # Simulate fetching the security requirements of the pending tasks
        await asyncio.sleep(0.1)
        return self._mock_security_profile
