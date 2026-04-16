# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Sovereign Treasury State Schema.

Defines the thermodynamic capital schema used by the Von Neumann Expansion Loop
to track reinvestment capital. This module provides the schema definition only —
instances are constructed and injected at runtime via the Governance Plane CLI,
never stored as mutable module-level singletons.
"""

from __future__ import annotations


from pydantic import BaseModel


class TreasuryState(BaseModel):
    """Schema defining the swarm's reinvestment capital tracking in Gwei.

    Instances are constructed at runtime boundaries and injected
    into subsystems that require capital-aware decision making.
    """

    reinvestment_capital_gwei: int = 0
