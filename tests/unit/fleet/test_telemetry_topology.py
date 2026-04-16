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

from coreason_ecosystem.fleet.telemetry_topology import TelemetryTopologyMonitor


@pytest.fixture
def monitor() -> TelemetryTopologyMonitor:
    return TelemetryTopologyMonitor()


@pytest.mark.asyncio
async def test_get_queue_derivative_no_client(
    monitor: TelemetryTopologyMonitor,
) -> None:
    """Without a Temporal client, derivative must return 0.0 (degraded mode)."""
    assert monitor._client is None
    derivative = await monitor.get_queue_derivative()
    assert derivative == 0.0


@pytest.mark.asyncio
async def test_get_active_task_hardware_profile_no_client(
    monitor: TelemetryTopologyMonitor,
) -> None:
    """Without a Temporal client, hardware profile must return None."""
    assert monitor._client is None
    profile = await monitor.get_active_task_hardware_profile()
    assert profile is None


@pytest.mark.asyncio
async def test_get_active_task_security_profile_no_client(
    monitor: TelemetryTopologyMonitor,
) -> None:
    """Without a Temporal client, security profile must return None."""
    assert monitor._client is None
    profile = await monitor.get_active_task_security_profile()
    assert profile is None
