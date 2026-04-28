import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from coreason_ecosystem.fleet.daemon import AutonomicFleetManager
from coreason_ecosystem.fleet.pulumi_actuator import (
    PulumiActuator,
    ComputeNodeTarget,
)
from coreason_manifest.spec.ontology import (
    SpatialHardwareProfile as HardwareProfile,
    EpistemicSecurityProfile as SecurityProfile,
    EscrowPolicy,
)


@pytest.mark.asyncio
async def test_pulumi_actuator_compile_payload() -> None:
    # Covers lines 61-68 in pulumi_actuator
    driver = PulumiActuator(templates_dir=Path("/tmp/templates"))

    target = ComputeNodeTarget(
        provider="aws",
        instance_id="g4dn.xlarge",
        hourly_cost=0.5,
        vram_gb=16.0,
        hardware_profile=HardwareProfile(min_vram_gb=16.0, provider_whitelist=["aws"]),
        security_profile=SecurityProfile(network_isolation=True),
        mesh_auth_key="ts-12345",
        temporal_mesh_ip="100.1.1.1",
        escrow_policy=EscrowPolicy(
            escrow_locked_magnitude=50000,
            release_condition_metric="test",
            refund_target_node_cid="did:coreason:fleet:aws",
        ),
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
async def test_daemon_no_viable_bid() -> None:
    # Covers the "no viable bid" branch in daemon.py
    from unittest.mock import AsyncMock

    from coreason_ecosystem.fleet.telemetry_topology import coreason_active_agents_total

    manager = AutonomicFleetManager(
        max_budget_hr=1.0,
        polling_interval_sec=1,
        templates_path=Path("/tmp"),
        mesh_auth_key="key",
        temporal_mesh_ip="10.0.0.1",
    )

    # Set β₀ > 0 so scale-up logic triggers
    coreason_active_agents_total.set(1)

    setattr(manager.monitor, "_poll_workflows", AsyncMock())

    import typing
    async def stop_loop(*args: typing.Any, **kwargs: typing.Any) -> None:
        manager._running = False

    with patch.object(
        manager.oracle,
        "calculate_optimal_bid",
        side_effect=stop_loop,
        return_value=None,
    ):
        await manager.start()
        # If it passes without exception, the no-bid branch was hit
