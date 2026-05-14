from typing import Any
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from coreason_ecosystem.fleet.daemon import AutonomicFleetManager


@pytest.fixture
def fleet_manager() -> Any:
    with patch("coreason_ecosystem.fleet.daemon.SkyPilotActuator"):
        manager = AutonomicFleetManager(
            max_budget_hr=10.0,
            polling_interval_sec=1,
            templates_path=Path("/tmp"),
            mesh_auth_key="key",
            temporal_mesh_ip="ip",
        )
        # Mock dependencies
        manager.driver = MagicMock()
        manager.driver.reconcile_state = AsyncMock(return_value=[])
        manager.driver.provision_node = AsyncMock(
            return_value={"cluster_name": "test_stack"}
        )
        manager.driver.destroy_node = AsyncMock()

        return manager


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_autonomic_fleet_manager_scale_zero(
    mock_sleep: Any, fleet_manager: Any
) -> None:
    # delta <= 0, active_stacks > 0
    fleet_manager.driver.reconcile_state.return_value = [{"cluster_name": "stack1"}]

    # Cancel sleep to stop loop
    mock_sleep.side_effect = asyncio.CancelledError()

    await fleet_manager.start()

    fleet_manager.driver.destroy_node.assert_called_once_with("stack1")


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_autonomic_fleet_manager_scale_up_success(
    mock_sleep: Any, fleet_manager: Any
) -> None:
    # Setup delta > 0. Since required_vram = 0, delta is required - provisioned.
    # But wait, in the code required_vram = 0.0, so delta = 0.0 - provisioned.
    # To get delta > 0, provisioned must be negative.
    # So let's mock provisioned_vram to -10, or mock active_stacks to have negative vram (which is weird but makes delta > 0)
    fleet_manager.driver.reconcile_state.return_value = [{"vram_capacity": -10.0}]

    mock_sleep.side_effect = asyncio.CancelledError()

    await fleet_manager.start()

    fleet_manager.driver.provision_node.assert_called_once()
    assert fleet_manager.pending_provisions == 1


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_autonomic_fleet_manager_scale_up_failure(
    mock_sleep: Any, fleet_manager: Any
) -> None:
    fleet_manager.driver.reconcile_state.return_value = [{"vram_capacity": -10.0}]

    fleet_manager.driver.provision_node.side_effect = Exception("Failed")

    mock_sleep.side_effect = asyncio.CancelledError()

    await fleet_manager.start()

    assert fleet_manager.pending_provisions == 0


@pytest.mark.asyncio
async def test_autonomic_fleet_manager_cancelled_during_reconcile(
    fleet_manager: Any,
) -> None:
    fleet_manager.driver.reconcile_state.side_effect = asyncio.CancelledError()

    await fleet_manager.start()

    assert fleet_manager._running is False


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_autonomic_fleet_manager_exception_caught(
    mock_sleep: Any, fleet_manager: Any
) -> None:
    fleet_manager.driver.reconcile_state.side_effect = Exception("Random error")
    mock_sleep.side_effect = asyncio.CancelledError()

    await fleet_manager.start()

    # ensure we caught it and went to sleep
    mock_sleep.assert_called_once()
