# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget, PulumiFleetDriver


@pytest.fixture
def tmp_templates_dir(tmp_path: Path) -> Path:
    # Set up dummy directories for aws_spot and vast_ai
    aws_dir = tmp_path / "aws_spot"
    aws_dir.mkdir()
    vast_dir = tmp_path / "vast_ai"
    vast_dir.mkdir()
    return tmp_path


@pytest.fixture
def driver(tmp_templates_dir: Path) -> PulumiFleetDriver:
    return PulumiFleetDriver(tmp_templates_dir)


@pytest.mark.asyncio
async def test_provision_node_aws(driver: PulumiFleetDriver) -> None:
    target = ComputeNodeTarget(
        provider="aws", instance_id="t3.micro", hourly_cost=0.01, vram_gb=0.0
    )

    mock_stack = MagicMock()
    mock_up_res = MagicMock()
    mock_up_res.outputs = {"public_ip": MagicMock(value="1.2.3.4")}
    mock_stack.up.return_value = mock_up_res

    with patch("coreason_ecosystem.fleet.pulumi_actuator.auto.create_stack", return_value=mock_stack) as mock_create_stack:
        res = await driver.provision_node(target)

        assert "stack_name" in res
        assert res["outputs"] == {"public_ip": "1.2.3.4"}

        mock_create_stack.assert_called_once()
        # Verify set_config was called with "instance_type" and some auto.ConfigValue
        called_args = [call_args.args[0] for call_args in mock_stack.set_config.call_args_list]
        assert "instance_type" in called_args
        mock_stack.up.assert_called_once()


@pytest.mark.asyncio
async def test_provision_node_vast(driver: PulumiFleetDriver) -> None:
    target = ComputeNodeTarget(
        provider="vast", instance_id="12345", hourly_cost=0.5, vram_gb=24.0
    )

    mock_stack = MagicMock()
    mock_up_res = MagicMock()
    mock_up_res.outputs = {"ssh_ip": MagicMock(value="192.168.1.100")}
    mock_stack.up.return_value = mock_up_res

    with patch("coreason_ecosystem.fleet.pulumi_actuator.auto.create_stack", return_value=mock_stack) as mock_create_stack:
        res = await driver.provision_node(target)

        assert "stack_name" in res
        assert res["outputs"] == {"ssh_ip": "192.168.1.100"}

        mock_create_stack.assert_called_once()
        # Verify set_config was called with "machine_id" and some auto.ConfigValue
        called_args = [call_args.args[0] for call_args in mock_stack.set_config.call_args_list]
        assert "machine_id" in called_args
        mock_stack.up.assert_called_once()


@pytest.mark.asyncio
async def test_destroy_node_aws(driver: PulumiFleetDriver) -> None:
    mock_stack = MagicMock()
    with patch("coreason_ecosystem.fleet.pulumi_actuator.auto.select_stack", return_value=mock_stack) as mock_select_stack:
        await driver.destroy_node("fleet-worker-123", "aws")

        mock_select_stack.assert_called_once()
        mock_stack.destroy.assert_called_once()
        mock_stack.workspace.remove_stack.assert_called_once_with("fleet-worker-123")


@pytest.mark.asyncio
async def test_reconcile_state(driver: PulumiFleetDriver, tmp_templates_dir: Path) -> None:
    mock_workspace = MagicMock()
    mock_stack1 = MagicMock()
    mock_stack1.name = "fleet-worker-abc"
    mock_stack2 = MagicMock()
    mock_stack2.name = "other-stack"
    mock_stack3 = MagicMock()
    mock_stack3.name = "fleet-worker-def"

    mock_workspace.list_stacks.return_value = [mock_stack1, mock_stack2, mock_stack3]

    with patch("coreason_ecosystem.fleet.pulumi_actuator.auto.LocalWorkspace", return_value=mock_workspace):
        active_stacks = await driver.reconcile_state()
        # We have 2 provider directories (aws_spot, vast_ai) set up in the fixture
        assert "fleet-worker-abc" in active_stacks
        assert "fleet-worker-def" in active_stacks
        # The list might have duplicates if both directories mock the same return,
        # but we just verify it correctly filters.
        assert len(active_stacks) == 4 # 2 from aws_spot, 2 from vast_ai


@pytest.mark.asyncio
async def test_reconcile_state_exception(driver: PulumiFleetDriver, tmp_templates_dir: Path) -> None:
    with patch("coreason_ecosystem.fleet.pulumi_actuator.auto.LocalWorkspace", side_effect=Exception("Failed")):
        active_stacks = await driver.reconcile_state()
        assert active_stacks == []
