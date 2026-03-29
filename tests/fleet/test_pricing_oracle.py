# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import pytest

from coreason_ecosystem.fleet.pricing_oracle import PricingOracle
from coreason_manifest.spec.ontology import HardwareProfile  # type: ignore[attr-defined]


@pytest.fixture
def oracle() -> PricingOracle:
    return PricingOracle()


@pytest.mark.asyncio
async def test_calculate_optimal_bid_valid(oracle: PricingOracle) -> None:
    profile = HardwareProfile(
        min_vram_gb=10.0, provider_whitelist=["aws"], accelerator_type="ampere"
    )
    # AWS p3.2xlarge has 16GB, cost $3.06, AWS t3.micro has 0GB
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is not None
    assert bid.provider == "aws"
    assert bid.instance_id == "p3.2xlarge"


@pytest.mark.asyncio
async def test_calculate_optimal_bid_exceeds_budget(oracle: PricingOracle) -> None:
    profile = HardwareProfile(
        min_vram_gb=10.0, provider_whitelist=["aws"], accelerator_type="ampere"
    )
    # AWS p3.2xlarge cost $3.06, which exceeds budget of $2.0
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=2.0)
    assert bid is None


@pytest.mark.asyncio
async def test_calculate_optimal_bid_provider_not_whitelisted(
    oracle: PricingOracle,
) -> None:
    profile = HardwareProfile(
        min_vram_gb=10.0,
        provider_whitelist=["gcp"],  # "vast" and "aws" are in the mock order book
        accelerator_type="ampere",
    )
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is None


@pytest.mark.asyncio
async def test_calculate_optimal_bid_lowest_price(oracle: PricingOracle) -> None:
    profile = HardwareProfile(
        min_vram_gb=0.0, provider_whitelist=["aws"], accelerator_type="any"
    )
    # Both t3.micro ($0.01) and p3.2xlarge ($3.06) are valid. t3.micro should win.
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is not None
    assert bid.instance_id == "t3.micro"
