# Copyright (c) 2026 CoReason, Inc.
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from coreason_ecosystem.fleet.daemon import AutonomicFleetManager

@pytest.fixture
def fleet_manager():
    with patch("coreason_ecosystem.fleet.daemon.PulumiActuator"), \
         patch("coreason_ecosystem.fleet.daemon.PricingOracle"):
        manager = AutonomicFleetManager(
            max_budget_hr=10.0,
            polling_interval_sec=1,
            templates_path=Path("/tmp"),
            mesh_auth_key="key",
            temporal_mesh_ip="ip",
        )
        manager.driver = MagicMock()
        manager.driver.reconcile_state = AsyncMock(return_value=[])
        manager.driver.provision_node = AsyncMock(return_value={"stack_name": "test_stack"})
        manager.driver.destroy_node = AsyncMock()
        manager.oracle = MagicMock()
        manager.oracle.calculate_optimal_bid = AsyncMock(return_value=None)
        return manager

@pytest.mark.asyncio
async def test_daemon_cooldown_decrement(fleet_manager):
    # Trigger scale up
    fleet_manager.driver.reconcile_state.return_value = [{"vram_capacity": -10.0}]
    bid = MagicMock()
    bid.provider = "aws"
    fleet_manager.oracle.calculate_optimal_bid.return_value = bid

    # We want to wait for the background task
    # But sleep is 300s. We MUST mock asyncio.sleep.
    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        # First iteration: provision
        # Second iteration: stop
        
        # We need to control the loop.
        # We'll make it run twice.
        
        original_start = fleet_manager.start
        
        # We'll use a side effect on reconcile_state to stop after 1 call
        async def stop_after_one(*args, **kwargs):
            fleet_manager._running = False
            return [{"vram_capacity": -10.0}]
            
        fleet_manager.driver.reconcile_state.side_effect = stop_after_one
        
        await fleet_manager.start()
        
        # Now check if the task was created
        assert fleet_manager.pending_provisions == 1
        assert len(fleet_manager._background_tasks) == 1
        
        # Wait for background tasks to finish
        await asyncio.gather(*fleet_manager._background_tasks)
        
        assert fleet_manager.pending_provisions == 0

@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_daemon_idle_no_nodes(mock_sleep, fleet_manager):
    # betti_0=0, pending=0, active_stacks=[]
    fleet_manager.driver.reconcile_state.return_value = []
    
    # Stop after one loop
    async def stop_after_one():
        fleet_manager._running = False
        return []
    fleet_manager.driver.reconcile_state.side_effect = stop_after_one
    
    await fleet_manager.start()
    # It should hit the else at line 143
    # No assertion needed for coverage, but we can check it didn't call destroy
    fleet_manager.driver.destroy_node.assert_not_called()
