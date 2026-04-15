# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import sys
from collections.abc import Generator
from unittest.mock import MagicMock
import pytest

from coreason_ecosystem.fleet.pricing_oracle import PricingOracle
from coreason_manifest.spec.ontology import SpatialHardwareProfile as HardwareProfile, AcceleratorProfile


@pytest.fixture
def oracle() -> PricingOracle:
    return PricingOracle()


@pytest.fixture
def mock_boto3() -> Generator[MagicMock, None, None]:
    mock_boto = MagicMock()
    sys.modules["boto3"] = mock_boto
    mock_client = MagicMock()
    mock_boto.client.return_value = mock_client
    mock_client.describe_spot_price_history.return_value = {
        "SpotPriceHistory": [
            {"InstanceType": "p3.2xlarge", "SpotPrice": "3.06"},
            {"InstanceType": "g4dn.xlarge", "SpotPrice": "0.52"},
        ]
    }
    yield mock_boto
    if "boto3" in sys.modules:
        del sys.modules["boto3"]


@pytest.mark.asyncio
async def test_calculate_optimal_bid_valid(oracle: PricingOracle, mock_boto3: MagicMock) -> None:
    profile = HardwareProfile(
        min_vram_gb=10.0, provider_whitelist=["aws"]
    )
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is not None
    assert bid.provider == "aws"
    assert bid.instance_id == "g4dn.xlarge"


@pytest.mark.asyncio
async def test_calculate_optimal_bid_exceeds_budget(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    profile = HardwareProfile(
        min_vram_gb=10.0, provider_whitelist=["aws"]
    )
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=0.1)
    assert bid is None


@pytest.mark.asyncio
async def test_calculate_optimal_bid_provider_not_whitelisted(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    profile = HardwareProfile(
        min_vram_gb=10.0,
        provider_whitelist=["gcp"],
        accelerator_type=AcceleratorProfile.BF16_TENSOR,
    )
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is None


@pytest.mark.asyncio
async def test_calculate_optimal_bid_lowest_price(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    profile = HardwareProfile(
        min_vram_gb=0.1, provider_whitelist=["aws"]
    )
    # Both g4dn.xlarge ($0.52) and p3.2xlarge ($3.06) are valid. g4dn.xlarge should win.
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is not None
    assert bid.instance_id == "g4dn.xlarge"
