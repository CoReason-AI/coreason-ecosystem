# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Unit tests for AutonomicFleetManifold — topological scaling verification."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from coreason_ecosystem.fleet.daemon import AutonomicFleetManifold
from coreason_ecosystem.fleet.telemetry_topology import (
    coreason_active_agents_total,
)
from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget
from coreason_manifest.spec.ontology import EscrowPolicy


@pytest.fixture
def templates_path(tmp_path: Path) -> Path:
    return tmp_path / "infrastructure/ephemeral"


@pytest.fixture
def manifold(templates_path: Path) -> AutonomicFleetManifold:
    return AutonomicFleetManifold(
        max_budget_hr=5.0,
        polling_interval_sec=10,
        templates_path=templates_path,
        mesh_auth_key="test_auth_key",
        temporal_mesh_ip="10.0.0.5",
    )


@pytest.mark.asyncio
async def test_daemon_start_scale_up(manifold: AutonomicFleetManifold) -> None:
    """When β₀ > 0, the daemon provisions compute."""
    coreason_active_agents_total.set(2)

    setattr(manifold.monitor, "_poll_workflows", AsyncMock())

    bid = ComputeNodeTarget(
        provider="aws",
        instance_id="p3.2xlarge",
        hourly_cost=3.0,
        vram_gb=16.0,
        escrow_policy=EscrowPolicy(
            escrow_locked_magnitude=50000,
            release_condition_metric="test",
            refund_target_node_cid="did:coreason:fleet:aws",
        ),
    )
    setattr(manifold.oracle, "calculate_optimal_bid", AsyncMock(return_value=bid))
    setattr(
        manifold.driver,
        "provision_node",
        AsyncMock(return_value={"stack_name": "fleet-worker-test"}),
    )

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manifold.start()

    getattr(manifold.oracle, "calculate_optimal_bid").assert_awaited_once()
    getattr(manifold.driver, "provision_node").assert_awaited_once()
    assert manifold._running is False


@pytest.mark.asyncio
async def test_daemon_start_scale_down(manifold: AutonomicFleetManifold) -> None:
    """When β₀ == 0, the daemon destroys orphaned stacks."""
    coreason_active_agents_total.set(0)

    setattr(manifold.monitor, "_poll_workflows", AsyncMock())
    setattr(
        manifold.driver,
        "reconcile_state",
        AsyncMock(
            return_value=[{"stack_name": "fleet-worker-orphan", "provider": "aws"}]
        ),
    )
    setattr(manifold.driver, "destroy_node", AsyncMock())

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manifold.start()

    getattr(manifold.driver, "reconcile_state").assert_awaited_once()
    getattr(manifold.driver, "destroy_node").assert_awaited_once_with(
        "fleet-worker-orphan", "aws"
    )


@pytest.mark.asyncio
async def test_daemon_start_scale_down_queue_empty_nothing_to_destroy(
    manifold: AutonomicFleetManifold,
) -> None:
    """When β₀ == 0 and no stacks, no destruction occurs."""
    coreason_active_agents_total.set(0)

    setattr(manifold.monitor, "_poll_workflows", AsyncMock())
    setattr(
        manifold.driver,
        "reconcile_state",
        AsyncMock(return_value=[]),
    )
    setattr(manifold.driver, "destroy_node", AsyncMock())

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manifold.start()

    getattr(manifold.driver, "destroy_node").assert_not_called()


@pytest.mark.asyncio
async def test_daemon_start_cancelled_error_main_loop(
    manifold: AutonomicFleetManifold,
) -> None:
    """CancelledError during poll cleanly exits the loop."""
    setattr(
        manifold.monitor,
        "_poll_workflows",
        AsyncMock(side_effect=asyncio.CancelledError("Shutdown requested")),
    )

    await manifold.start()

    getattr(manifold.monitor, "_poll_workflows").assert_awaited_once()
    assert manifold._running is False


@pytest.mark.asyncio
async def test_daemon_start_general_exception(manifold: AutonomicFleetManifold) -> None:
    """General exceptions are logged and the loop continues to sleep."""
    setattr(
        manifold.monitor,
        "_poll_workflows",
        AsyncMock(side_effect=Exception("API down")),
    )

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manifold.start()

    getattr(manifold.monitor, "_poll_workflows").assert_awaited_once()
    assert manifold._running is False


@pytest.mark.asyncio
async def test_daemon_start_no_bid_found(manifold: AutonomicFleetManifold) -> None:
    """When oracle returns None, no provisioning occurs."""
    coreason_active_agents_total.set(1)

    setattr(manifold.monitor, "_poll_workflows", AsyncMock())
    setattr(manifold.oracle, "calculate_optimal_bid", AsyncMock(return_value=None))
    setattr(manifold.driver, "provision_node", AsyncMock())

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manifold.start()

    getattr(manifold.driver, "provision_node").assert_not_called()
