# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Sovereign Treasury State.

Tracks the reinvestment capital pool used by the Von Neumann Expansion Loop
to autonomously purchase physical GPU hardware when sufficient capital is aggregated.
"""

from __future__ import annotations


class TreasuryState:
    """Mutable state tracking the swarm's reinvestment capital in Gwei."""

    def __init__(self, reinvestment_capital_gwei: int = 0) -> None:
        self.reinvestment_capital_gwei = reinvestment_capital_gwei


global_treasury: TreasuryState = TreasuryState()
