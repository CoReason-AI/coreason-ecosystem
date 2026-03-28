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
def driver() -> PulumiFleetDriver:
    return PulumiFleetDriver(Path("/tmp/templates"))


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_provision_node_aws(mock_auto: MagicMock, driver: PulumiFleetDriver) -> None:
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
async def test_provision_node_vast(mock_auto: MagicMock, driver: PulumiFleetDriver) -> None:
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
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_reconcile_state(mock_auto: MagicMock, driver: PulumiFleetDriver) -> None:
    mock_workspace = MagicMock()
    mock_auto.LocalWorkspace.return_value = mock_workspace

    # 1. Stacks from AWS
    # 2. Stacks from Vast
    stack1 = MagicMock()
    stack1.name = "fleet-worker-1"
    stack2 = MagicMock()
    stack2.name = "other-stack"
    stack3 = MagicMock()
    stack3.name = "fleet-worker-2"

    mock_workspace.list_stacks.side_effect = [[stack1, stack2], [stack3]]

    orphans = await driver.reconcile_state()

    assert orphans == ["fleet-worker-1", "fleet-worker-2"]
    assert mock_auto.LocalWorkspace.call_count == 2
    assert mock_workspace.list_stacks.call_count == 2


@pytest.mark.asyncio
@patch("coreason_ecosystem.fleet.pulumi_actuator.auto")
async def test_reconcile_state_exception(mock_auto: MagicMock, driver: PulumiFleetDriver) -> None:
    # Trigger exception reading workspace
    mock_auto.LocalWorkspace.side_effect = Exception("Workspace fail")

    orphans = await driver.reconcile_state()
    assert orphans == []
