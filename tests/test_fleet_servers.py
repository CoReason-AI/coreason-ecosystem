import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from coreason_ecosystem.fleet.daemon import AutonomicFleetManager
from coreason_ecosystem.fleet.pulumi_actuator import (
    PulumiFleetDriver,
    ComputeNodeTarget,
)
from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile


@pytest.mark.asyncio
async def test_pulumi_actuator_compile_payload():
    # Covers lines 61-68 in pulumi_actuator
    driver = PulumiFleetDriver(templates_dir=Path("/tmp/templates"))

    target = ComputeNodeTarget(
        provider="aws",
        instance_id="g4dn.xlarge",
        hourly_cost=0.5,
        vram_gb=16.0,
        hardware_profile=HardwareProfile(
            min_vram_gb=16.0, provider_whitelist=["aws"], accelerator_type="ampere"
        ),
        security_profile=SecurityProfile(network_isolation=True),
        mesh_auth_key="ts-12345",
        temporal_mesh_ip="100.1.1.1",
    )

    with patch("coreason_ecosystem.fleet.pulumi_actuator.auto") as mock_auto:
        mock_stack = MagicMock()
        mock_auto.create_stack.return_value = mock_stack
        mock_stack.up.return_value = MagicMock(
            outputs={"ip": MagicMock(value="10.0.0.1")}
        )

        result = await driver.provision_node(target)

        # Verify set_config was called with boot_payload_b64 due to passing all parameters properly
        mock_stack.set_config.assert_any_call(
            "boot_payload_b64", mock_auto.ConfigValue()
        )
        assert result["stack_name"].startswith("fleet-worker-")


@pytest.mark.asyncio
async def test_daemon_no_viable_bid():
    # Covers line 72 in daemon.py
    manager = AutonomicFleetManager(
        max_budget_hr=1.0,
        polling_interval_sec=1,
        templates_path=Path("/tmp"),
        mesh_auth_key="key",
        temporal_mesh_ip="10.0.0.1",
    )

    # We explicitly throw a cancel error to jump out of the infinite while true loop after 1 pass
    async def get_q():
        manager._running = False
        return 1.5

    with patch.object(manager.monitor, "get_queue_derivative", side_effect=get_q):
        with patch.object(manager.oracle, "calculate_optimal_bid", return_value=None):
            await manager.start()
            # If it passes without exception, coverage on line 72 is hit
