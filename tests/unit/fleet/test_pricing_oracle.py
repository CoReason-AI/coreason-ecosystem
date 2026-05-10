# Copyright (c) 2026 CoReason, Inc.
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
from coreason_manifest.spec.ontology import SpatialHardwareProfile as HardwareProfile


@pytest.fixture
def oracle() -> PricingOracle:
    return PricingOracle()


@pytest.fixture
def mock_boto3() -> Generator[MagicMock, None, None]:
    """Mock boto3 with both describe_instance_types paginator and spot pricing."""
    mock_boto = MagicMock()
    sys.modules["boto3"] = mock_boto
    mock_client = MagicMock()
    mock_boto.client.return_value = mock_client

    # Mock the paginator for describe_instance_types (dynamic VRAM discovery)
    mock_paginator = MagicMock()
    mock_client.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {
            "InstanceTypes": [
                {
                    "InstanceType": "g4dn.xlarge",
                    "GpuInfo": {
                        "Gpus": [{"Count": 1, "MemoryInfo": {"SizeInMiB": 16384}}]
                    },
                },
                {
                    "InstanceType": "p3.2xlarge",
                    "GpuInfo": {
                        "Gpus": [{"Count": 1, "MemoryInfo": {"SizeInMiB": 16384}}]
                    },
                },
            ]
        }
    ]

    # Mock spot pricing
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
async def test_calculate_optimal_bid_valid(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    profile = HardwareProfile(min_vram_gb=10.0, provider_whitelist=["aws"])
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is not None
    assert bid.provider == "aws"
    assert bid.instance_id == "g4dn.xlarge"


@pytest.mark.asyncio
async def test_calculate_optimal_bid_exceeds_budget(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    profile = HardwareProfile(min_vram_gb=10.0, provider_whitelist=["aws"])
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=0.1)
    assert bid is None


@pytest.mark.asyncio
async def test_calculate_optimal_bid_provider_not_whitelisted(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    profile = HardwareProfile(
        min_vram_gb=10.0,
        provider_whitelist=["gcp"],
        accelerator_type="urn:coreason:accelerator:bf16_tensor",
    )
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is None


@pytest.mark.asyncio
async def test_calculate_optimal_bid_lowest_price(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    profile = HardwareProfile(min_vram_gb=0.1, provider_whitelist=["aws"])
    # Both g4dn.xlarge ($0.52) and p3.2xlarge ($3.06) are valid. g4dn.xlarge should win.
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is not None
    assert bid.instance_id == "g4dn.xlarge"


@pytest.mark.asyncio
async def test_vfe_assessment_safe() -> None:
    """VFE divergence below threshold does not trigger the guillotine."""
    from coreason_ecosystem.fleet.pricing_oracle import assess_thermodynamic_expenditure

    profile = HardwareProfile(min_vram_gb=1.0, provider_whitelist=["aws"])
    assessment = await assess_thermodynamic_expenditure(
        hardware_profile=profile,
        max_budget_hr=10.0,
        current_gpu_utilization=0.3,
        current_api_cost_hourly=2.0,
    )
    assert not assessment.threshold_breached
    assert assessment.vfe_divergence < 0.85


@pytest.mark.asyncio
async def test_vfe_assessment_breach() -> None:
    """VFE divergence at or above threshold triggers the Economic Guillotine."""
    from coreason_ecosystem.fleet.pricing_oracle import assess_thermodynamic_expenditure

    profile = HardwareProfile(min_vram_gb=1.0, provider_whitelist=["aws"])
    assessment = await assess_thermodynamic_expenditure(
        hardware_profile=profile,
        max_budget_hr=10.0,
        current_gpu_utilization=0.95,
        current_api_cost_hourly=9.0,
    )
    assert assessment.threshold_breached
    assert assessment.vfe_divergence >= 0.85


@pytest.mark.asyncio
async def test_vfe_assessment_zero_budget() -> None:
    """Zero budget forces cost_pressure to 1.0."""
    from coreason_ecosystem.fleet.pricing_oracle import assess_thermodynamic_expenditure

    profile = HardwareProfile(min_vram_gb=1.0, provider_whitelist=["aws"])
    assessment = await assess_thermodynamic_expenditure(
        hardware_profile=profile,
        max_budget_hr=0.0,
        current_gpu_utilization=0.0,
    )
    # cost_pressure = 1.0, vfe = 0.6*0.0 + 0.4*1.0 = 0.4
    assert assessment.vfe_divergence == pytest.approx(0.4)
    assert not assessment.threshold_breached


@pytest.mark.asyncio
async def test_calculate_optimal_bid_no_qualifying_instances(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    profile = HardwareProfile(min_vram_gb=100.0, provider_whitelist=["aws"])
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is None


@pytest.mark.asyncio
async def test_calculate_optimal_bid_aws_exception(
    oracle: PricingOracle, mock_boto3: MagicMock
) -> None:
    # Cause an exception inside fetch_aws_spot
    mock_boto3.client.side_effect = Exception("API down")
    profile = HardwareProfile(min_vram_gb=10.0, provider_whitelist=["aws"])
    bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
    assert bid is None


@pytest.mark.asyncio
async def test_calculate_optimal_bid_vast_success(oracle: PricingOracle) -> None:
    from unittest.mock import patch

    profile = HardwareProfile(min_vram_gb=10.0, provider_whitelist=["vast"])

    class MockResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "offers": [
                    {"gpu_ram": 16384, "dph_base": 0.5, "machine_id": "1234"},
                    {"gpu_ram": 8192, "dph_base": 0.2, "machine_id": "5678"},
                ]
            }

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, *args, **kwargs):
            return MockResponse()

    with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
        bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
        assert bid is not None
        assert bid.provider == "vast"
        assert bid.instance_id == "1234"
        assert bid.vram_gb == 16.0
        assert bid.hourly_cost == 0.5


@pytest.mark.asyncio
async def test_calculate_optimal_bid_vast_exception(oracle: PricingOracle) -> None:
    from unittest.mock import patch

    profile = HardwareProfile(min_vram_gb=10.0, provider_whitelist=["vast"])

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, *args, **kwargs):
            raise Exception("API Error")

    with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
        bid = await oracle.calculate_optimal_bid(profile, max_budget_hr=5.0)
        assert bid is None
