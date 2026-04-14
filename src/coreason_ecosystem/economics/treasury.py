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
import math
import asyncio
from typing import Any, Dict
from pydantic import BaseModel
from loguru import logger

from coreason_manifest.spec.ontology import PredictionMarketState, HypothesisStakeReceipt

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

class LMSRMarketMaker:
    """
    High-Frequency Prediction Market Engine running Robin Hanson's 
    Logarithmic Market Scoring Rule (LMSR). It calculates probability wave collapses.
    """
    def __init__(self, liquidity_parameter_b: float = 100.0):
        self.B = liquidity_parameter_b
        # Map hypothesis unique ID to current token stake (q_i)
        self.stakes: Dict[str, float] = {}
        # Concurrency protection ensuring race safety during high-frequency stakes
        self._market_lock = asyncio.Lock()

    async def calculate_current_cost(self) -> float:
        """Cost = B * ln(sum(e^(q_i / B)))"""
        if not self.stakes:
            return 0.0
        sum_exp = sum(math.exp(q / self.B) for q in self.stakes.values())
        return self.B * math.log(sum_exp)

    async def stake_hypothesis(self, hypothesis_id: str, amount_gwei: float) -> float:
        """
        Thread-safely stakes tokens into a hypothesis pool and returns the marginal cost.
        """
        async with self._market_lock:
            initial_cost = await self.calculate_current_cost()
            
            current_q = self.stakes.get(hypothesis_id, 0.0)
            self.stakes[hypothesis_id] = current_q + amount_gwei
            
            new_cost = await self.calculate_current_cost()
            marginal_cost = new_cost - initial_cost
            
            # Dynamic wave collapse tracking
            logger.info(f"Staked {amount_gwei} on {hypothesis_id}. Marginal cost: {marginal_cost}")
            return marginal_cost

    async def get_probabilities(self) -> Dict[str, float]:
        """p_i = exp(q_i/B) / sum(exp(q_j/B))"""
        async with self._market_lock:
            if not self.stakes:
                return {}
            sum_exp = sum(math.exp(q / self.B) for q in self.stakes.values())
            return {k: math.exp(v / self.B) / sum_exp for k, v in self.stakes.items()}
