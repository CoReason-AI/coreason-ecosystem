# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import pytest

from coreason_ecosystem.fleet.expansion_loop import (
    HARDWARE_NODE_COST_GWEI,
    SAFETY_MARGIN_GWEI,
    TREASURY_URN,
    von_neumann_expansion_daemon,
)
from coreason_ecosystem.fleet.pricing_oracle import PricingOracle
from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry


def _seeded_registry() -> SovereignMCPRegistry:
    """Create a registry with the Sovereign Treasury MCP registered."""
    registry = SovereignMCPRegistry()
    registry._cache = {
        TREASURY_URN: {
            "endpoint": "http://treasury-mcp:8000",
            "clearance": "RESTRICTED",
            "epistemic_status": "PUBLISHED",
        },
    }
    return registry


@pytest.mark.asyncio
async def test_expansion_loop_raises_not_implemented() -> None:
    """Expansion loop raises NotImplementedError until Sovereign Treasury MCP is deployed."""
    registry = _seeded_registry()
    oracle = PricingOracle()

    with pytest.raises(NotImplementedError, match="Sovereign Treasury MCP"):
        await von_neumann_expansion_daemon(registry, oracle)


@pytest.mark.asyncio
async def test_expansion_loop_economic_guillotine() -> None:
    """When VFE threshold is breached, the daemon exits cleanly (no NotImplementedError)."""
    from unittest.mock import AsyncMock, patch

    from coreason_ecosystem.fleet.pricing_oracle import ThermodynamicAssessment

    registry = _seeded_registry()
    oracle = PricingOracle()

    mock_assessment = ThermodynamicAssessment(
        gpu_utilization=0.95,
        token_velocity=100.0,
        api_cost_hourly=50.0,
        vfe_divergence=0.99,
        threshold_breached=True,
    )

    with patch(
        "coreason_ecosystem.fleet.expansion_loop.assess_thermodynamic_expenditure",
        new_callable=AsyncMock,
        return_value=mock_assessment,
    ):
        # Should NOT raise — the guillotine triggers a clean return.
        await von_neumann_expansion_daemon(registry, oracle)


@pytest.mark.asyncio
async def test_expansion_loop_missing_treasury_urn() -> None:
    """When treasury URN is not registered, daemon exits cleanly with a log."""
    empty_registry = SovereignMCPRegistry()
    oracle = PricingOracle()

    # Should NOT raise — logs error and returns.
    await von_neumann_expansion_daemon(empty_registry, oracle)


def test_constants() -> None:
    """Test that constants are sensible values."""
    assert HARDWARE_NODE_COST_GWEI == 10_000_000_000
    assert SAFETY_MARGIN_GWEI == 2_000_000_000
    assert TREASURY_URN == "urn:coreason:state:treasury"
