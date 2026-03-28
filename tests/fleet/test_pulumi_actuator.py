# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from coreason_ecosystem.fleet.pulumi_actuator import (
    PulumiFleetDriver,
    ComputeNodeTarget,
)


@pytest.fixture
def tmp_templates_dir(tmp_path: Path) -> Path:
    aws_dir = tmp_path / "aws_spot"
    vast_dir = tmp_path / "vast_ai"
    aws_dir.mkdir(parents=True, exist_ok=True)
    vast_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def driver(tmp_templates_dir: Path) -> PulumiFleetDriver:
    return PulumiFleetDriver(tmp_templates_dir)


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_provision_node_aws(
    mock_auto: MagicMock, driver: PulumiFleetDriver
) -> None:
    target = ComputeNodeTarget(
        provider="aws", instance_id="t3.micro", hourly_cost=0.01, vram_gb=0.0
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
    mock_auto: MagicMock, driver: PulumiFleetDriver
) -> None:
    target = ComputeNodeTarget(
        provider="vast", instance_id="12345", hourly_cost=0.40, vram_gb=24.0
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
async def test_destroy_node(mock_auto: MagicMock, driver: PulumiFleetDriver) -> None:
    mock_stack = MagicMock()
    mock_auto.select_stack.return_value = mock_stack

    await driver.destroy_node("fleet-worker-xyz", "aws")

    mock_auto.select_stack.assert_called_once()
    mock_stack.destroy.assert_called_once()
    mock_stack.workspace.remove_stack.assert_called_once_with("fleet-worker-xyz")


@pytest.mark.asyncio
async def test_reconcile_state(
    driver: PulumiFleetDriver, tmp_templates_dir: Path
) -> None:
    mock_workspace = MagicMock()
    mock_stack1 = MagicMock()
    mock_stack1.name = "fleet-worker-abc"
    mock_stack2 = MagicMock()
    mock_stack2.name = "other-stack"

    mock_workspace.list_stacks.return_value = [mock_stack1, mock_stack2]

    with patch(
        "coreason_ecosystem.fleet.pulumi_actuator.auto.LocalWorkspace",
        return_value=mock_workspace,
    ):
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
    mock_auto: MagicMock, driver: PulumiFleetDriver
) -> None:
    # Trigger exception reading workspace
    mock_auto.LocalWorkspace.side_effect = Exception("Workspace fail")

    orphans = await driver.reconcile_state()
    assert orphans == []
