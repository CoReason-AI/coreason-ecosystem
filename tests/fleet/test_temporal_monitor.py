# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.

import pytest

from coreason_ecosystem.fleet.temporal_monitor import ThermodynamicMonitor


@pytest.fixture
def monitor() -> ThermodynamicMonitor:
    return ThermodynamicMonitor()


@pytest.mark.asyncio
async def test_get_queue_derivative(monitor: ThermodynamicMonitor) -> None:
    derivative = await monitor.get_queue_derivative()
    assert derivative == 1.5


@pytest.mark.asyncio
async def test_get_active_task_hardware_profile(monitor: ThermodynamicMonitor) -> None:
    profile = await monitor.get_active_task_hardware_profile()
    assert profile is not None
    assert profile.min_vram_gb == 16.0
    assert "aws" in profile.provider_whitelist
    assert "vast" in profile.provider_whitelist
    assert profile.accelerator_type == "ampere"
