# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-manifest>

import asyncio
from pathlib import Path
from typing import Any, Dict, List

import pytest

from coreason_ecosystem.fleet.daemon import AutonomicFleetManager


class FakeSkyPilotActuator:
    """Fake actuator for physical substrate testing without mocks."""

    def __init__(self) -> None:
        self.provision_called = False
        self.destroy_called = False
        self.reconcile_data: List[Dict[str, Any]] = []

    async def reconcile_state(self) -> List[Dict[str, Any]]:
        return self.reconcile_data

    async def provision_node(self, target: Any) -> Dict[str, Any]:
        self.provision_called = True
        return {"cluster_name": "test_stack", "status": "provisioned"}

    async def destroy_node(self, cluster_name: str) -> None:
        self.destroy_called = True


@pytest.fixture
def fleet_manager() -> AutonomicFleetManager:
    manager = AutonomicFleetManager(
        max_budget_hr=10.0,
        polling_interval_sec=0,  # No delay for tests
        templates_path=Path("/tmp"),
        cooldown_sec=0,
    )
    manager.driver = FakeSkyPilotActuator()  # type: ignore
    return manager


@pytest.mark.asyncio
async def test_daemon_cooldown_decrement(fleet_manager: AutonomicFleetManager) -> None:
    """Cover background _cooldown_and_decrement task without mocks."""
    fake_driver: Any = fleet_manager.driver
    fake_driver.reconcile_data = [{"vram_capacity": -10.0}]

    # Stop the daemon after one iteration by setting _running to False in the loop
    # We can do this by monkeypatching reconcile_state to also stop the daemon
    original_reconcile = fake_driver.reconcile_state

    async def reconcile_and_stop():
        fleet_manager._running = False
        return await original_reconcile()

    fake_driver.reconcile_state = reconcile_and_stop

    await fleet_manager.start()

    assert fleet_manager.pending_provisions == 1
    assert len(fleet_manager._background_tasks) == 1

    # Wait for background tasks to finish
    await asyncio.gather(*fleet_manager._background_tasks)

    assert fleet_manager.pending_provisions == 0


@pytest.mark.asyncio
async def test_daemon_idle_no_nodes(fleet_manager: AutonomicFleetManager) -> None:
    """Cover idle with no active stacks without mocks."""
    fake_driver: Any = fleet_manager.driver
    fake_driver.reconcile_data = []

    async def reconcile_and_stop():
        fleet_manager._running = False
        return []

    fake_driver.reconcile_state = reconcile_and_stop

    await fleet_manager.start()
    assert not fake_driver.destroy_called
