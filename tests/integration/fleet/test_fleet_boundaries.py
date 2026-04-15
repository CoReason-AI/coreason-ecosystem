import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch, MagicMock

from coreason_ecosystem.fleet.mesh_injector import (
    FederatedCapabilityAttestationReceipt,
    MeshInjector,
)
from coreason_ecosystem.fleet.pricing_oracle import PricingOracle
from coreason_ecosystem.fleet.temporal_monitor import ThermodynamicMonitor
from coreason_manifest.spec.ontology import SpatialHardwareProfile as HardwareProfile


def test_mesh_injector_jwt_validation() -> None:
    # Lines 31-33
    with pytest.raises(ValidationError):
        FederatedCapabilityAttestationReceipt(token="invalid_token", payload="data")


def test_mesh_injector_epistemic_bounding() -> None:
    # Lines 38-47
    def build_nested_dict(depth: int) -> dict[str, object]:
        if depth == 0:
            return {}
        return {"k": build_nested_dict(depth - 1)}

    # Needs to exceed 10000 nodes! We can use a large list.
    large_payload = [1] * 10001
    with pytest.raises(ValidationError):
        FederatedCapabilityAttestationReceipt(
            token="valid.jwt.token", payload=large_payload
        )


def test_mesh_injector_middleware() -> None:
    # Lines 59-60
    injector = MeshInjector()
    payload = {"query": "resolve"}
    result = injector.inject_ocap_middleware("valid.jwt.token", payload)
    assert result == payload


@pytest.mark.asyncio
async def test_temporal_monitor_security_profile() -> None:
    # Line 40
    monitor = ThermodynamicMonitor()
    sec_profile = await monitor.get_active_task_security_profile()
    assert sec_profile is not None
    assert sec_profile.network_isolation is True


@pytest.mark.asyncio
async def test_pricing_oracle_vast() -> None:
    # Lines 87-112, 118, 120
    hardware = HardwareProfile(min_vram_gb=16.0, provider_whitelist=["vast"])
    oracle = PricingOracle()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "offers": [
                {
                    "gpu_ram": 24576,
                    "dph_base": 0.5,
                    "machine_id": "mach1",
                },  # valid (24GB)
                {
                    "gpu_ram": 8192,
                    "dph_base": 0.1,
                    "machine_id": "mach2",
                },  # invalid (8GB)
            ]
        }
        mock_get.return_value = mock_resp

        target = await oracle.calculate_optimal_bid(hardware, max_budget_hr=1.0)
        assert target is not None
        assert target.provider == "vast"
        assert target.instance_id == "mach1"
        assert target.hourly_cost == 0.5


@pytest.mark.asyncio
async def test_pricing_oracle_vast_failure() -> None:
    hardware = HardwareProfile(min_vram_gb=16.0, provider_whitelist=["vast"])
    oracle = PricingOracle()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("network fail")
        target = await oracle.calculate_optimal_bid(hardware, max_budget_hr=1.0)
        assert target is None


@pytest.mark.asyncio
async def test_pricing_oracle_aws_boto_failure() -> None:
    # Lines 51, 75-81
    hardware = HardwareProfile(min_vram_gb=16.0, provider_whitelist=["aws"])
    oracle = PricingOracle()

    from moto import mock_aws

    with mock_aws():
        with patch("boto3.client") as mock_client:
            mock_client.side_effect = Exception("boto error")
            target = await oracle.calculate_optimal_bid(hardware, max_budget_hr=1.0)
            assert target is None


@pytest.mark.asyncio
async def test_pricing_oracle_aws_no_instances() -> None:
    # Line 51 -> empty valid instances
    hardware = HardwareProfile(min_vram_gb=9999.0, provider_whitelist=["aws"])
    oracle = PricingOracle()
    target = await oracle.calculate_optimal_bid(hardware, max_budget_hr=1.0)
    assert target is None
