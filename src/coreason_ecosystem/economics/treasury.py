# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Sovereign Treasury Management.

Aggregates incoming crypto revenue and mathematically allocates capital 
to operating expenses vs reinvestment funds.
"""

from __future__ import annotations

import time
from typing import Any
from pydantic import BaseModel
from loguru import logger

class TaskAwardReceipt(BaseModel):
    execution_id: str
    escrow_id: str
    amount_gwei: int
    wallet_address: str

class TreasuryState:
    """Singleton tracking sovereign capital."""
    def __init__(self) -> None:
        self.operating_expenses_gwei: int = 0
        self.reinvestment_capital_gwei: int = 0
        self.total_revenue_gwei: int = 0

    async def process_settled_revenue(self, award_receipt: TaskAwardReceipt) -> dict[str, Any]:
        """Split incoming settled execution receipts into capital groups."""
        amount = award_receipt.amount_gwei
        
        # Split logic: 40% operating, 60% reinvestment for scaling
        op_ex_split = int(amount * 0.40)
        reinvest_split = amount - op_ex_split
        
        self.operating_expenses_gwei += op_ex_split
        self.reinvestment_capital_gwei += reinvest_split
        self.total_revenue_gwei += amount
        
        logger.info(f"[Treasury] Settled {amount} Gwei. OpEx: {self.operating_expenses_gwei}, Reinvest: {self.reinvestment_capital_gwei}")
        
        return {
            "status": "settled",
            "operating_expenses_gwei": self.operating_expenses_gwei,
            "reinvestment_capital_gwei": self.reinvestment_capital_gwei,
            "timestamp_ns": time.time_ns(),
        }

# Global Mock Context
global_treasury = TreasuryState()
