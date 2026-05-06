import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from coreason_ecosystem.fleet.expansion_loop import von_neumann_expansion_daemon


class MockAssessment:
    def __init__(self, breached: bool = False) -> None:
        self.threshold_breached = breached


class MockBid:
    def __init__(self, provider: str = "aws") -> None:
        self.provider = provider
        self.market_type = None
        self.hardware_profile = None
        self.security_profile = None
        self.mesh_auth_key = None
        self.temporal_mesh_ip = None
        self.escrow_policy = None


@pytest.mark.asyncio
async def test_von_neumann_expansion_daemon_missing_treasury() -> None:
    registry = MagicMock()
    registry.resolve_urn = AsyncMock(side_effect=KeyError("Not found"))
    oracle = MagicMock()

    with patch("coreason_ecosystem.fleet.expansion_loop.logger.error") as mock_err:
        await von_neumann_expansion_daemon(registry, oracle, "key", "ip")
        mock_err.assert_called_once()
        assert "not registered" in mock_err.call_args[0][0]


@pytest.mark.asyncio
async def test_von_neumann_expansion_daemon_economic_guillotine() -> None:
    registry = MagicMock()
    registry.resolve_urn = AsyncMock(return_value="http://treasury")
    oracle = MagicMock()

    # We will raise CancelledError after first iteration to exit loop
    with (
        patch(
            "coreason_ecosystem.fleet.expansion_loop.coreason_aggregate_vram_demand_gb._value.get",
            return_value=40.0,
        ),
        patch(
            "coreason_ecosystem.fleet.expansion_loop.PulumiActuator"
        ) as mock_actuator_cls,
        patch(
            "coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure",
            new_callable=AsyncMock,
        ) as mock_assess,
    ):
        mock_actuator = MagicMock()
        mock_actuator.reconcile_state = AsyncMock(return_value=[{"vram_capacity": 10}])
        mock_actuator.execute_thermodynamic_guillotine = AsyncMock()
        mock_actuator_cls.return_value = mock_actuator

        mock_assess.return_value = MockAssessment(breached=True)

        await von_neumann_expansion_daemon(registry, oracle, "key", "ip")

        mock_actuator.execute_thermodynamic_guillotine.assert_awaited_once()


@pytest.mark.asyncio
async def test_von_neumann_expansion_daemon_provision_success() -> None:
    registry = MagicMock()
    registry.resolve_urn = AsyncMock(return_value="http://treasury")
    oracle = MagicMock()
    oracle.calculate_optimal_bid = AsyncMock(return_value=MockBid("vast"))

    # We will raise CancelledError in sleep to exit the loop gracefully
    async def mock_sleep(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.CancelledError()

    with (
        patch(
            "coreason_ecosystem.fleet.expansion_loop.coreason_aggregate_vram_demand_gb._value.get",
            return_value=10.0,
        ),
        patch(
            "coreason_ecosystem.fleet.expansion_loop.PulumiActuator"
        ) as mock_actuator_cls,
        patch(
            "coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure",
            new_callable=AsyncMock,
        ) as mock_assess,
        patch("asyncio.sleep", side_effect=mock_sleep),
    ):
        mock_actuator = MagicMock()
        # total_active > 0, on_demand_count = 0 => target_market_type = 'on-demand'
        mock_actuator.reconcile_state = AsyncMock(
            return_value=[{"vram_capacity": 5, "market_type": "spot"}]
        )
        mock_actuator.provision_node = AsyncMock()
        mock_actuator_cls.return_value = mock_actuator

        mock_assess.return_value = MockAssessment(breached=False)

        await von_neumann_expansion_daemon(registry, oracle, "key", "ip")

        mock_actuator.provision_node.assert_awaited_once()
        bid = mock_actuator.provision_node.call_args[0][0]
        assert bid.market_type == "on-demand"
        assert bid.provider == "vast"


@pytest.mark.asyncio
async def test_von_neumann_expansion_daemon_provision_spot() -> None:
    registry = MagicMock()
    registry.resolve_urn = AsyncMock(return_value="http://treasury")
    oracle = MagicMock()
    oracle.calculate_optimal_bid = AsyncMock(return_value=MockBid("aws"))

    async def mock_sleep(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.CancelledError()

    with (
        patch(
            "coreason_ecosystem.fleet.expansion_loop.coreason_aggregate_vram_demand_gb._value.get",
            return_value=10.0,
        ),
        patch(
            "coreason_ecosystem.fleet.expansion_loop.PulumiActuator"
        ) as mock_actuator_cls,
        patch(
            "coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure",
            new_callable=AsyncMock,
        ) as mock_assess,
        patch("asyncio.sleep", side_effect=mock_sleep),
    ):
        mock_actuator = MagicMock()
        # 1 active, 1 on-demand => 100% on-demand > 0.3 => target_market_type = 'spot'
        mock_actuator.reconcile_state = AsyncMock(
            return_value=[{"vram_capacity": 5, "market_type": "on-demand"}]
        )
        mock_actuator.provision_node = AsyncMock()
        mock_actuator_cls.return_value = mock_actuator

        mock_assess.return_value = MockAssessment(breached=False)

        await von_neumann_expansion_daemon(registry, oracle, "key", "ip")

        mock_actuator.provision_node.assert_awaited_once()
        bid = mock_actuator.provision_node.call_args[0][0]
        assert bid.market_type == "spot"


@pytest.mark.asyncio
async def test_von_neumann_expansion_daemon_no_bids() -> None:
    registry = MagicMock()
    registry.resolve_urn = AsyncMock(return_value="http://treasury")
    oracle = MagicMock()
    oracle.calculate_optimal_bid = AsyncMock(return_value=None)

    async def mock_sleep(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.CancelledError()

    with (
        patch(
            "coreason_ecosystem.fleet.expansion_loop.coreason_aggregate_vram_demand_gb._value.get",
            return_value=10.0,
        ),
        patch(
            "coreason_ecosystem.fleet.expansion_loop.PulumiActuator"
        ) as mock_actuator_cls,
        patch(
            "coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure",
            new_callable=AsyncMock,
        ) as mock_assess,
        patch("coreason_ecosystem.fleet.expansion_loop.logger.warning") as mock_warn,
        patch("asyncio.sleep", side_effect=mock_sleep),
    ):
        mock_actuator = MagicMock()
        mock_actuator.reconcile_state = AsyncMock(return_value=[])
        mock_actuator_cls.return_value = mock_actuator

        mock_assess.return_value = MockAssessment(breached=False)

        await von_neumann_expansion_daemon(registry, oracle, "key", "ip")

        mock_warn.assert_called_with("[ExpansionLoop] No viable bids found.")


@pytest.mark.asyncio
async def test_von_neumann_expansion_daemon_exception_handling() -> None:
    registry = MagicMock()
    registry.resolve_urn = AsyncMock(return_value="http://treasury")
    oracle = MagicMock()

    async def mock_sleep(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.CancelledError()

    with (
        patch(
            "coreason_ecosystem.fleet.expansion_loop.coreason_aggregate_vram_demand_gb._value.get",
            side_effect=RuntimeError("Test error"),
        ),
        patch("coreason_ecosystem.fleet.expansion_loop.logger.error") as mock_err,
        patch("asyncio.sleep", side_effect=mock_sleep),
    ):
        await von_neumann_expansion_daemon(registry, oracle, "key", "ip")

        # Ensure it caught the exception and didn't crash
        mock_err.assert_called_once()
        assert "Runtime execution anomaly" in str(mock_err.call_args)
