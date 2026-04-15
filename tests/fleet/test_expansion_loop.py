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
from unittest.mock import AsyncMock, patch

import pytest

from coreason_ecosystem.economics.treasury import TreasuryState
from coreason_ecosystem.fleet.expansion_loop import (
    HARDWARE_NODE_COST_GWEI,
    SAFETY_MARGIN_GWEI,
    PulumiActuatorMock,
    von_neumann_expansion_daemon,
)


@pytest.mark.asyncio
async def test_pulumi_actuator_mock() -> None:
    """Test the PulumiActuatorMock.provision_node method."""
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await PulumiActuatorMock.provision_node("p4d.24xlarge")


@pytest.mark.asyncio
async def test_expansion_loop_below_threshold() -> None:
    """Test expansion loop when capital is below the threshold."""
    mock_treasury = TreasuryState(reinvestment_capital_gwei=0)

    iteration_count = 0

    async def mock_sleep(_: float) -> None:
        nonlocal iteration_count
        iteration_count += 1
        if iteration_count >= 1:
            raise asyncio.CancelledError()

    with (
        patch("coreason_ecosystem.fleet.expansion_loop.global_treasury", mock_treasury),
        patch("asyncio.sleep", side_effect=mock_sleep),
    ):
        try:
            await von_neumann_expansion_daemon()
        except asyncio.CancelledError:
            pass

    # Capital should remain unchanged since threshold was not met
    assert mock_treasury.reinvestment_capital_gwei == 0


@pytest.mark.asyncio
async def test_expansion_loop_above_threshold() -> None:
    """Test expansion loop when capital exceeds the threshold."""
    target_cost = HARDWARE_NODE_COST_GWEI + SAFETY_MARGIN_GWEI
    mock_treasury = TreasuryState(reinvestment_capital_gwei=target_cost)

    iteration_count = 0

    async def mock_sleep(_: float) -> None:
        nonlocal iteration_count
        iteration_count += 1
        if iteration_count >= 1:
            raise asyncio.CancelledError()

    with (
        patch("coreason_ecosystem.fleet.expansion_loop.global_treasury", mock_treasury),
        patch("asyncio.sleep", side_effect=mock_sleep),
        patch.object(PulumiActuatorMock, "provision_node", new_callable=AsyncMock),
    ):
        try:
            await von_neumann_expansion_daemon()
        except asyncio.CancelledError:
            pass

    # Capital should be drawn down by HARDWARE_NODE_COST_GWEI
    expected = target_cost - HARDWARE_NODE_COST_GWEI
    assert mock_treasury.reinvestment_capital_gwei == expected


def test_constants() -> None:
    """Test that constants are sensible values."""
    assert HARDWARE_NODE_COST_GWEI == 10_000_000_000
    assert SAFETY_MARGIN_GWEI == 2_000_000_000
