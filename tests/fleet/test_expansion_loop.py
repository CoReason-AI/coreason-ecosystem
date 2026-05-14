from typing import Any
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from coreason_ecosystem.fleet.expansion_loop import (
    von_neumann_expansion_daemon,
    TREASURY_URN,
)


@pytest.fixture
def mock_registry() -> Any:
    registry = MagicMock()
    registry.resolve_urn = AsyncMock(return_value="http://treasury")
    return registry


@pytest.mark.asyncio
async def test_von_neumann_treasury_urn_missing(mock_registry: Any) -> None:
    mock_registry.resolve_urn.side_effect = KeyError("urn missing")

    # Should return immediately without looping
    await von_neumann_expansion_daemon(mock_registry, "key", "ip")
    mock_registry.resolve_urn.assert_called_once_with(TREASURY_URN)


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure")
@patch("coreason_ecosystem.fleet.expansion_loop.SkyPilotActuator")
async def test_von_neumann_economic_guillotine(
    mock_actuator_cls: Any, mock_assess: Any, mock_registry: Any
) -> None:
    mock_assess.return_value = MagicMock(threshold_breached=True, expenditure_gwei=10)
    mock_actuator = MagicMock()
    mock_actuator.reconcile_state = AsyncMock(return_value=[])
    mock_actuator.execute_thermodynamic_guillotine = AsyncMock()
    mock_actuator_cls.return_value = mock_actuator

    # Should exit the loop when guillotine triggers
    await von_neumann_expansion_daemon(mock_registry, "key", "ip")

    mock_actuator.execute_thermodynamic_guillotine.assert_called_once_with(True)


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure")
@patch("coreason_ecosystem.fleet.expansion_loop.SkyPilotActuator")
@patch("asyncio.sleep")
async def test_von_neumann_provision_bid(
    mock_sleep: Any,
    mock_actuator_cls: Any,
    mock_assess: Any,
    mock_registry: Any,
) -> None:
    mock_assess.return_value = MagicMock(threshold_breached=False, expenditure_gwei=10)
    mock_actuator = MagicMock()
    mock_actuator.reconcile_state = AsyncMock(
        return_value=[
            {"vram_capacity": 10, "status": "UP"},
        ]
    )
    mock_actuator.provision_node = AsyncMock()
    mock_actuator_cls.return_value = mock_actuator

    mock_sleep.side_effect = asyncio.CancelledError()

    await von_neumann_expansion_daemon(mock_registry, "key", "ip")

    mock_actuator.provision_node.assert_called_once()
    target = mock_actuator.provision_node.call_args[0][0]
    assert target.use_spot is True


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure")
@patch("coreason_ecosystem.fleet.expansion_loop.SkyPilotActuator")
@patch("asyncio.sleep")
async def test_von_neumann_runtime_exception(
    mock_sleep: Any,
    mock_actuator_cls: Any,
    mock_assess: Any,
    mock_registry: Any,
) -> None:
    mock_actuator_cls.side_effect = Exception("Actuator initialization failed")

    mock_sleep.side_effect = asyncio.CancelledError()

    await von_neumann_expansion_daemon(mock_registry, "key", "ip")
    # exception is caught, logged, and then sleep raises CancelledError, stopping the loop
