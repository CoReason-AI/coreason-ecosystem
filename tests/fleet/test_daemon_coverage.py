# Copyright (c) 2026 CoReason, Inc.
import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        manager.driver = MagicMock()
        manager.driver.reconcile_state = AsyncMock(return_value=[])
        manager.driver.provision_node = AsyncMock(
            return_value={"cluster_name": "test_stack"}
        )
        manager.driver.destroy_node = AsyncMock()
        return manager


@pytest.mark.asyncio
async def test_daemon_cooldown_decrement(fleet_manager: Any) -> None:
    """Cover lines 113-117: background _cooldown_and_decrement task."""
    fleet_manager.driver.reconcile_state.return_value = [{"vram_capacity": -10.0}]

    with patch("asyncio.sleep", AsyncMock()):

        async def stop_after_one(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
            fleet_manager._running = False
            return [{"vram_capacity": -10.0}]

        fleet_manager.driver.reconcile_state.side_effect = stop_after_one

        await fleet_manager.start()

        assert fleet_manager.pending_provisions == 1
        assert len(fleet_manager._background_tasks) == 1

        await asyncio.gather(*fleet_manager._background_tasks)

        assert fleet_manager.pending_provisions == 0


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_daemon_idle_no_nodes(_mock_sleep: Any, fleet_manager: Any) -> None:
    """Cover line 143: idle with no active stacks."""

    async def stop_after_one() -> list[Any]:
        fleet_manager._running = False
        return []

    fleet_manager.driver.reconcile_state.side_effect = stop_after_one

    await fleet_manager.start()
    fleet_manager.driver.destroy_node.assert_not_called()
