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
from unittest.mock import patch, MagicMock
from pathlib import Path

from coreason_ecosystem.fleet.pulumi_actuator import (
    PulumiActuator,
    ComputeNodeTarget,
)
from coreason_manifest.spec.ontology import EscrowPolicy


@pytest.fixture
def tmp_templates_dir(tmp_path: Path) -> Path:
    aws_dir = tmp_path / "aws_spot"
    vast_dir = tmp_path / "vast_ai"
    aws_dir.mkdir(parents=True, exist_ok=True)
    vast_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def driver(tmp_templates_dir: Path) -> PulumiActuator:
    return PulumiActuator(tmp_templates_dir)


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_provision_node_aws(mock_auto: MagicMock, driver: PulumiActuator) -> None:
    target = ComputeNodeTarget(
        provider="aws",
        instance_id="t3.micro",
        hourly_cost=0.01,
        vram_gb=0.0,
        escrow_policy=EscrowPolicy(
            escrow_locked_magnitude=10000,
            release_condition_metric="test",
            refund_target_node_cid="did:coreason:fleet:aws",
        ),
    )

    mock_stack = MagicMock()
    mock_auto.create_stack.return_value = mock_stack
    mock_stack.up.return_value.outputs = {"public_ip": MagicMock(value="1.2.3.4")}

    res = await driver.provision_node(target)

    assert "stack_name" in res
    assert res["stack_name"].startswith("fleet-worker-")
    assert res["outputs"] == "{'public_ip': '1.2.3.4'}"

    mock_auto.create_stack.assert_called_once()
    mock_stack.set_config.assert_any_call("provider", mock_auto.ConfigValue("aws"))
    mock_stack.set_config.assert_any_call(
        "instance_type", mock_auto.ConfigValue("t3.micro")
    )
    mock_stack.up.assert_called_once()


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_provision_node_vast(
    mock_auto: MagicMock, driver: PulumiActuator
) -> None:
    target = ComputeNodeTarget(
        provider="vast",
        instance_id="12345",
        hourly_cost=0.40,
        vram_gb=24.0,
        escrow_policy=EscrowPolicy(
            escrow_locked_magnitude=10000,
            release_condition_metric="test",
            refund_target_node_cid="did:coreason:fleet:vast",
        ),
    )

    mock_stack = MagicMock()
    mock_auto.create_stack.return_value = mock_stack
    mock_stack.up.return_value.outputs = {"ssh_ip": MagicMock(value="5.6.7.8")}

    res = await driver.provision_node(target)

    assert "stack_name" in res
    assert res["outputs"] == "{'ssh_ip': '5.6.7.8'}"

    mock_stack.set_config.assert_any_call("provider", mock_auto.ConfigValue("vast"))
    mock_stack.set_config.assert_any_call("machine_id", mock_auto.ConfigValue("12345"))


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_destroy_node(mock_auto: MagicMock, driver: PulumiActuator) -> None:
    mock_stack = MagicMock()
    mock_auto.select_stack.return_value = mock_stack

    await driver.destroy_node("fleet-worker-xyz", "aws")

    mock_auto.select_stack.assert_called_once()
    mock_stack.destroy.assert_called_once()
    mock_stack.workspace.remove_stack.assert_called_once_with("fleet-worker-xyz")


@pytest.mark.asyncio
async def test_reconcile_state(driver: PulumiActuator, tmp_templates_dir: Path) -> None:
    mock_workspace = MagicMock()
    mock_stack1 = MagicMock()
    mock_stack1.name = "fleet-worker-abc"
    mock_stack2 = MagicMock()
    mock_stack2.name = "other-stack"

    mock_workspace.list_stacks.return_value = [mock_stack1, mock_stack2]

    with (
        patch(
            "coreason_ecosystem.fleet.pulumi_actuator.auto.LocalWorkspace",
            return_value=mock_workspace,
        ),
        patch(
            "coreason_ecosystem.fleet.pulumi_actuator.auto.select_stack"
        ) as mock_select_stack,
    ):
        mock_select_stack.return_value.outputs.return_value = {
            "market_type": MagicMock(value="spot")
        }
        active_stacks = await driver.reconcile_state()

        # 1 matching stack from aws_spot, 1 from vast_ai
        assert len(active_stacks) == 2
        assert active_stacks[0]["stack_name"] == "fleet-worker-abc"
        assert active_stacks[0]["provider"] in ["aws", "vast"]
        assert active_stacks[1]["stack_name"] == "fleet-worker-abc"
        assert active_stacks[1]["provider"] in ["aws", "vast"]


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_reconcile_state_exception(
    mock_auto: MagicMock, driver: PulumiActuator
) -> None:
    # Trigger exception reading workspace
    mock_auto.LocalWorkspace.side_effect = Exception("Workspace fail")

    orphans = await driver.reconcile_state()
    assert orphans == []


@pytest.mark.asyncio
async def test_provision_node_rejects_missing_escrow(driver: PulumiActuator) -> None:
    """Hardware Guillotine: no EscrowPolicy → provisioning rejected."""
    target = ComputeNodeTarget(
        provider="aws", instance_id="t3.micro", hourly_cost=0.01, vram_gb=0.0
    )
    with pytest.raises(ValueError, match="Hardware Guillotine"):
        await driver.provision_node(target)


@pytest.mark.asyncio
async def test_provision_node_rejects_exceeded_budget(driver: PulumiActuator) -> None:
    """Hardware Guillotine: hourly_cost > escrow_locked_magnitude → rejected."""
    target = ComputeNodeTarget(
        provider="aws",
        instance_id="p5.48xlarge",
        hourly_cost=99.0,
        vram_gb=640.0,
        escrow_policy=EscrowPolicy(
            escrow_locked_magnitude=1,
            release_condition_metric="test",
            refund_target_node_cid="did:coreason:fleet:aws",
        ),
    )
    with pytest.raises(ValueError, match="Hardware Guillotine"):
        await driver.provision_node(target)


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_provision_node_vast_with_payload(
    mock_auto: MagicMock, driver: PulumiActuator
) -> None:
    """Cover the boot-payload + market_type config paths for vast provider."""
    from coreason_manifest.spec.ontology import (
        SpatialHardwareProfile,
        EpistemicSecurityProfile,
    )

    target = ComputeNodeTarget(
        provider="vast",
        instance_id="99999",
        hourly_cost=0.10,
        vram_gb=24.0,
        escrow_policy=EscrowPolicy(
            escrow_locked_magnitude=10000,
            release_condition_metric="test",
            refund_target_node_cid="did:coreason:fleet:vast",
        ),
        hardware_profile=SpatialHardwareProfile(
            min_vram_gb=24.0, provider_whitelist=["vast"]
        ),
        security_profile=EpistemicSecurityProfile(network_isolation=True),
        mesh_auth_key="auth-key",
        temporal_mesh_ip="10.0.0.1",
        market_type="spot",
    )

    mock_stack = MagicMock()
    mock_auto.create_stack.return_value = mock_stack
    mock_stack.up.return_value.outputs = {}

    with patch.object(driver.injector, "compile_payload", return_value="BASE64PAYLOAD"):
        res = await driver.provision_node(target)

    assert "stack_name" in res
    mock_stack.set_config.assert_any_call(
        "boot_payload_b64", mock_auto.ConfigValue(value="BASE64PAYLOAD")
    )
    mock_stack.set_config.assert_any_call("market_type", mock_auto.ConfigValue("spot"))


@pytest.mark.asyncio
async def test_reconcile_state_uses_cache(driver: PulumiActuator) -> None:
    """Cover the TTL cache-hit branch in reconcile_state."""
    import time

    driver._cached_stacks = [{"stack_name": "cached", "provider": "aws"}]
    driver._last_sync_time = time.time()

    result = await driver.reconcile_state()
    assert result == [{"stack_name": "cached", "provider": "aws"}]


@pytest.mark.asyncio
async def test_execute_thermodynamic_guillotine_no_breach(
    driver: PulumiActuator,
) -> None:
    from coreason_ecosystem.fleet.pricing_oracle import ThermodynamicAssessment

    assessment = ThermodynamicAssessment(
        threshold_breached=False,
        vfe_divergence=0.0,
        current_epistemic_value=0.0,
        current_thermodynamic_cost=0.0,
        gpu_utilization=0.0,
        token_velocity=0.0,
        api_cost_hourly=0.0,
    )
    with patch.object(driver, "reconcile_state") as mock_reconcile:
        await driver.execute_thermodynamic_guillotine(assessment)
        mock_reconcile.assert_not_called()


@pytest.mark.asyncio
async def test_execute_thermodynamic_guillotine_no_stacks(
    driver: PulumiActuator,
) -> None:
    """Cover the early-return when coroutines list is empty."""
    from coreason_ecosystem.fleet.pricing_oracle import ThermodynamicAssessment

    assessment = ThermodynamicAssessment(
        threshold_breached=True,
        vfe_divergence=1.0,
        current_epistemic_value=0.0,
        current_thermodynamic_cost=0.0,
        gpu_utilization=0.0,
        token_velocity=0.0,
        api_cost_hourly=0.0,
    )
    with patch.object(driver, "reconcile_state", return_value=[]):
        # Should return early without error
        await driver.execute_thermodynamic_guillotine(assessment)


@pytest.mark.asyncio
async def test_execute_thermodynamic_guillotine_destroy_exception(
    driver: PulumiActuator,
) -> None:
    from unittest.mock import AsyncMock
    from coreason_ecosystem.fleet.pricing_oracle import ThermodynamicAssessment

    assessment = ThermodynamicAssessment(
        threshold_breached=True,
        vfe_divergence=2.0,
        current_epistemic_value=0.0,
        current_thermodynamic_cost=0.0,
        gpu_utilization=0.0,
        token_velocity=0.0,
        api_cost_hourly=0.0,
    )
    with (
        patch.object(
            driver,
            "reconcile_state",
            return_value=[{"stack_name": "s1", "provider": "aws"}],
        ),
        patch.object(
            driver,
            "destroy_node",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
        patch("coreason_ecosystem.fleet.pulumi_actuator.logger.error") as mock_err,
    ):
        await driver.execute_thermodynamic_guillotine(assessment)
        mock_err.assert_called()
        assert "boom" in str(mock_err.call_args)


@pytest.mark.asyncio
async def test_execute_thermodynamic_guillotine_timeout(driver: PulumiActuator) -> None:
    import asyncio
    from unittest.mock import AsyncMock
    from coreason_ecosystem.fleet.pricing_oracle import ThermodynamicAssessment

    assessment = ThermodynamicAssessment(
        threshold_breached=True,
        vfe_divergence=3.0,
        current_epistemic_value=0.0,
        current_thermodynamic_cost=0.0,
        gpu_utilization=0.0,
        token_velocity=0.0,
        api_cost_hourly=0.0,
    )

    from typing import Any

    async def _timeout(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.TimeoutError()

    with (
        patch.object(
            driver,
            "reconcile_state",
            return_value=[{"stack_name": "s1", "provider": "aws"}],
        ),
        patch.object(driver, "destroy_node", new_callable=AsyncMock),
        patch("asyncio.wait_for", side_effect=_timeout),
        patch("coreason_ecosystem.fleet.pulumi_actuator.logger.error") as mock_err,
    ):
        await driver.execute_thermodynamic_guillotine(assessment)
        mock_err.assert_called()
        assert "timed out" in str(mock_err.call_args)
