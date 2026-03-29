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
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from coreason_ecosystem.fleet.daemon import AutonomicFleetManager
from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile
from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget


@pytest.fixture
def templates_path(tmp_path: Path) -> Path:
    return tmp_path / "infrastructure/ephemeral"


@pytest.fixture
def manager(templates_path: Path) -> AutonomicFleetManager:
    return AutonomicFleetManager(
        max_budget_hr=5.0,
        polling_interval_sec=10,
        templates_path=templates_path,
        mesh_auth_key="test_auth_key",
        temporal_mesh_ip="10.0.0.5",
    )


@pytest.mark.asyncio
async def test_daemon_start_scale_up(manager: AutonomicFleetManager) -> None:
    # We want to break the infinite loop after 1 iteration, so we make sleep throw CancelledError
    setattr(manager.monitor, "get_queue_derivative", AsyncMock(return_value=1.5))

    profile = HardwareProfile(
        min_vram_gb=16.0, provider_whitelist=["aws"], accelerator_type="ampere"
    )
    security_profile = SecurityProfile(network_isolation=True)
    setattr(
        manager.monitor,
        "get_active_task_security_profile",
        AsyncMock(return_value=security_profile),
    )
    setattr(
        manager.monitor,
        "get_active_task_hardware_profile",
        AsyncMock(return_value=profile),
    )

    security_profile = SecurityProfile(network_isolation=True)
    setattr(
        manager.monitor,
        "get_active_task_security_profile",
        AsyncMock(return_value=security_profile),
    )

    bid = ComputeNodeTarget(
        provider="aws", instance_id="p3.2xlarge", hourly_cost=3.0, vram_gb=16.0
    )
    setattr(manager.oracle, "calculate_optimal_bid", AsyncMock(return_value=bid))

    setattr(
        manager.driver,
        "provision_node",
        AsyncMock(return_value={"stack_name": "fleet-worker-test"}),
    )

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manager.start()

    getattr(manager.monitor, "get_queue_derivative").assert_awaited_once()
    getattr(manager.monitor, "get_active_task_hardware_profile").assert_awaited_once()
    getattr(manager.monitor, "get_active_task_security_profile").assert_awaited_once()
    getattr(manager.oracle, "calculate_optimal_bid").assert_awaited_once_with(
        profile, 5.0
    )

    bid.hardware_profile = profile
    bid.security_profile = security_profile
    bid.mesh_auth_key = manager.mesh_auth_key
    bid.temporal_mesh_ip = manager.temporal_mesh_ip
    getattr(manager.driver, "provision_node").assert_awaited_once_with(bid)
    assert manager._running is False


@pytest.mark.asyncio
async def test_daemon_start_scale_down(manager: AutonomicFleetManager) -> None:
    setattr(manager.monitor, "get_queue_derivative", AsyncMock(return_value=0.0))

    setattr(
        manager.driver,
        "reconcile_state",
        AsyncMock(
            return_value=[{"stack_name": "fleet-worker-orphan", "provider": "aws"}]
        ),
    )
    setattr(manager.driver, "destroy_node", AsyncMock())

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manager.start()

    getattr(manager.monitor, "get_queue_derivative").assert_awaited_once()
    getattr(manager.driver, "reconcile_state").assert_awaited_once()
    getattr(manager.driver, "destroy_node").assert_awaited_once_with(
        "fleet-worker-orphan", "aws"
    )


@pytest.mark.asyncio
async def test_daemon_start_scale_down_queue_empty_nothing_to_destroy(
    manager: AutonomicFleetManager,
) -> None:
    setattr(manager.monitor, "get_queue_derivative", AsyncMock(return_value=0.0))

    setattr(
        manager.driver,
        "reconcile_state",
        AsyncMock(return_value=[]),
    )

    setattr(manager.driver, "destroy_node", AsyncMock())

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manager.start()

    getattr(manager.driver, "destroy_node").assert_not_called()


@pytest.mark.asyncio
async def test_daemon_start_cancelled_error_main_loop(
    manager: AutonomicFleetManager,
) -> None:
    setattr(
        manager.monitor,
        "get_queue_derivative",
        AsyncMock(side_effect=asyncio.CancelledError("Shutdown requested")),
    )

    await manager.start()

    getattr(manager.monitor, "get_queue_derivative").assert_awaited_once()
    assert manager._running is False


@pytest.mark.asyncio
async def test_daemon_start_general_exception(manager: AutonomicFleetManager) -> None:
    setattr(
        manager.monitor,
        "get_queue_derivative",
        AsyncMock(side_effect=Exception("API down")),
    )

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manager.start()

    getattr(manager.monitor, "get_queue_derivative").assert_awaited_once()
    # The loop should catch the exception and sleep (which raises CancelledError, exiting loop)
    assert manager._running is False


@pytest.mark.asyncio
async def test_daemon_start_no_bid_found(manager: AutonomicFleetManager) -> None:
    setattr(manager.monitor, "get_queue_derivative", AsyncMock(return_value=1.5))

    profile = HardwareProfile(
        min_vram_gb=16.0, provider_whitelist=["aws"], accelerator_type="ampere"
    )
    setattr(
        manager.monitor,
        "get_active_task_hardware_profile",
        AsyncMock(return_value=profile),
    )

    setattr(manager.oracle, "calculate_optimal_bid", AsyncMock(return_value=None))
    setattr(manager.driver, "provision_node", AsyncMock())

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manager.start()

    getattr(manager.driver, "provision_node").assert_not_called()


@pytest.mark.asyncio
async def test_daemon_start_no_bid_found_with_requirements(
    manager: AutonomicFleetManager,
) -> None:
    setattr(manager.monitor, "get_queue_derivative", AsyncMock(return_value=1.5))
    profile = HardwareProfile(
        min_vram_gb=16.0, provider_whitelist=["aws"], accelerator_type="ampere"
    )
    security_profile = SecurityProfile(network_isolation=True)
    setattr(
        manager.monitor,
        "get_active_task_hardware_profile",
        AsyncMock(return_value=profile),
    )
    setattr(
        manager.monitor,
        "get_active_task_security_profile",
        AsyncMock(return_value=security_profile),
    )
    setattr(manager.oracle, "calculate_optimal_bid", AsyncMock(return_value=None))
    setattr(manager.driver, "provision_node", AsyncMock())

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        await manager.start()

    getattr(manager.driver, "provision_node").assert_not_called()
