# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

from coreason_ecosystem.economics.treasury import TreasuryState, global_treasury


def test_treasury_state_default() -> None:
    """Test TreasuryState default initialization."""
    state = TreasuryState()
    assert state.reinvestment_capital_gwei == 0


def test_treasury_state_custom() -> None:
    """Test TreasuryState with custom initial capital."""
    state = TreasuryState(reinvestment_capital_gwei=1_000_000)
    assert state.reinvestment_capital_gwei == 1_000_000


def test_global_treasury_instance() -> None:
    """Test that the global treasury is a TreasuryState instance."""
    assert isinstance(global_treasury, TreasuryState)
