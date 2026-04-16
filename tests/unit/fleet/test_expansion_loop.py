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
    von_neumann_expansion_daemon,
)
from coreason_ecosystem.fleet.pricing_oracle import PricingOracle
from coreason_ecosystem.web3.treasury_manager import TreasuryManager


@pytest.mark.asyncio
async def test_expansion_loop_raises_not_implemented() -> None:
    """Expansion loop raises NotImplementedError until physical Web3 provider exists."""
    treasury = TreasuryManager(treasury_contract_address="0xTestContract")
    oracle = PricingOracle()

    with pytest.raises(NotImplementedError, match="Von Neumann Expansion Loop"):
        await von_neumann_expansion_daemon(treasury, oracle)


def test_constants() -> None:
    """Test that constants are sensible values."""
    assert HARDWARE_NODE_COST_GWEI == 10_000_000_000
    assert SAFETY_MARGIN_GWEI == 2_000_000_000
