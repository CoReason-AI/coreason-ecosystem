from typing import Any
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from coreason_ecosystem.fleet.expansion_loop import von_neumann_expansion_daemon, TREASURY_URN

@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.resolve_urn = AsyncMock(return_value="http://treasury")
    return registry

@pytest.fixture
def mock_oracle():
    oracle = MagicMock()
    oracle.calculate_optimal_bid = AsyncMock(return_value=None)
    return oracle

@pytest.mark.asyncio
async def test_von_neumann_treasury_urn_missing(mock_registry: Any, mock_oracle: Any) -> None:
    mock_registry.resolve_urn.side_effect = KeyError("urn missing")
    
    # Should return immediately without looping
    await von_neumann_expansion_daemon(mock_registry, mock_oracle, "key", "ip")
    mock_registry.resolve_urn.assert_called_once_with(TREASURY_URN)

@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure")
@patch("coreason_ecosystem.fleet.expansion_loop.PulumiActuator")
async def test_von_neumann_economic_guillotine(mock_actuator_cls: Any, mock_assess: Any, mock_registry: Any, mock_oracle: Any) -> None:
    mock_assess.return_value = MagicMock(threshold_breached=True, expenditure_gwei=10)
    mock_actuator = MagicMock()
    mock_actuator.reconcile_state = AsyncMock(return_value=[])
    mock_actuator.execute_thermodynamic_guillotine = AsyncMock()
    mock_actuator_cls.return_value = mock_actuator

    # Should exit the loop when guillotine triggers
    await von_neumann_expansion_daemon(mock_registry, mock_oracle, "key", "ip")
    
    mock_actuator.execute_thermodynamic_guillotine.assert_called_once()

@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure")
@patch("coreason_ecosystem.fleet.expansion_loop.PulumiActuator")
@patch("asyncio.sleep")
async def test_von_neumann_no_bids(mock_sleep: Any, mock_actuator_cls: Any, mock_assess: Any, mock_registry: Any, mock_oracle: Any) -> None:
    mock_assess.return_value = MagicMock(threshold_breached=False, expenditure_gwei=10)
    mock_actuator = MagicMock()
    mock_actuator.reconcile_state = AsyncMock(return_value=[])
    mock_actuator_cls.return_value = mock_actuator
    mock_oracle.calculate_optimal_bid.return_value = None
    
    mock_sleep.side_effect = asyncio.CancelledError()

    await von_neumann_expansion_daemon(mock_registry, mock_oracle, "key", "ip")
    mock_oracle.calculate_optimal_bid.assert_called_once()

@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure")
@patch("coreason_ecosystem.fleet.expansion_loop.PulumiActuator")
@patch("asyncio.sleep")
async def test_von_neumann_provision_bid(mock_sleep: Any, mock_actuator_cls: Any, mock_assess: Any, mock_registry: Any, mock_oracle: Any) -> None:
    mock_assess.return_value = MagicMock(threshold_breached=False, expenditure_gwei=10)
    mock_actuator = MagicMock()
    # active stacks with one on-demand and two spot
    mock_actuator.reconcile_state = AsyncMock(return_value=[
        {"vram_capacity": 10, "market_type": "on-demand"},
        {"vram_capacity": 10, "market_type": "spot"},
    ])
    mock_actuator.provision_node = AsyncMock()
    mock_actuator_cls.return_value = mock_actuator
    
    bid = MagicMock(provider="aws", bid_price_gwei=10, target_region="us-east-1", market_type="spot")
    mock_oracle.calculate_optimal_bid.return_value = bid
    
    mock_sleep.side_effect = asyncio.CancelledError()

    await von_neumann_expansion_daemon(mock_registry, mock_oracle, "key", "ip")
    
    mock_actuator.provision_node.assert_called_once()
    assert bid.market_type == "spot"
    
@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure")
@patch("coreason_ecosystem.fleet.expansion_loop.PulumiActuator")
@patch("asyncio.sleep")
async def test_von_neumann_provision_bid_on_demand(mock_sleep: Any, mock_actuator_cls: Any, mock_assess: Any, mock_registry: Any, mock_oracle: Any) -> None:
    mock_assess.return_value = MagicMock(threshold_breached=False, expenditure_gwei=10)
    mock_actuator = MagicMock()
    # active stacks with 0 on-demand, total_active = 1
    mock_actuator.reconcile_state = AsyncMock(return_value=[
        {"vram_capacity": 10, "market_type": "spot"},
    ])
    mock_actuator.provision_node = AsyncMock()
    mock_actuator_cls.return_value = mock_actuator
    
    bid = MagicMock(provider="aws", bid_price_gwei=10, target_region="us-east-1", market_type="spot")
    mock_oracle.calculate_optimal_bid.return_value = bid
    
    mock_sleep.side_effect = asyncio.CancelledError()

    await von_neumann_expansion_daemon(mock_registry, mock_oracle, "key", "ip")
    
    mock_actuator.provision_node.assert_called_once()
    assert bid.market_type == "on-demand"

@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure")
@patch("coreason_ecosystem.fleet.expansion_loop.PulumiActuator")
@patch("asyncio.sleep")
async def test_von_neumann_runtime_exception(mock_sleep: Any, mock_actuator_cls: Any, mock_assess: Any, mock_registry: Any, mock_oracle: Any) -> None:
    mock_actuator_cls.side_effect = Exception("Actuator initialization failed")
    
    mock_sleep.side_effect = asyncio.CancelledError()

    await von_neumann_expansion_daemon(mock_registry, mock_oracle, "key", "ip")
    # exception is caught, logged, and then sleep raises CancelledError, stopping the loop
