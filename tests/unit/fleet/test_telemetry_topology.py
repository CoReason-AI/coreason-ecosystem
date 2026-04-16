# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import pytest

from coreason_manifest.spec.ontology import AcceleratorProfile  # type: ignore[attr-defined, unused-ignore]

from coreason_ecosystem.fleet.telemetry_topology import TelemetryTopologyMonitor


@pytest.fixture
def monitor() -> TelemetryTopologyMonitor:
    return TelemetryTopologyMonitor()


@pytest.mark.asyncio
async def test_get_queue_derivative(monitor: TelemetryTopologyMonitor) -> None:
    derivative = await monitor.get_queue_derivative()
    assert derivative == 1.5


@pytest.mark.asyncio
async def test_get_active_task_hardware_profile(
    monitor: TelemetryTopologyMonitor,
) -> None:
    profile = await monitor.get_active_task_hardware_profile()
    assert profile is not None
    assert profile.min_vram_gb == 16.0
    assert "aws" in profile.provider_whitelist
    assert "vast" in profile.provider_whitelist
    assert profile.accelerator_type == AcceleratorProfile.BF16_TENSOR
