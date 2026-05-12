# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

import pytest
from unittest.mock import MagicMock, patch
from coreason_ecosystem.fleet.skypilot_actuator import SkyPilotActuator, SkyPilotTarget
from typing import Any, Generator
from coreason_manifest.spec.ontology import (
    SpatialHardwareProfile as HardwareProfile,
    EpistemicSecurityProfile as SecurityProfile,
)


@pytest.fixture
def mock_sky() -> Generator[Any, None, None]:
    with patch("coreason_ecosystem.fleet.skypilot_actuator.sky") as mock:
        yield mock


@pytest.fixture
def actuator() -> SkyPilotActuator:
    return SkyPilotActuator()


@pytest.mark.asyncio
async def test_provision_node_basic(actuator: SkyPilotActuator, mock_sky: Any) -> None:
    target = SkyPilotTarget(use_spot=True, autostop_idle_minutes=15)

    mock_sky.launch.return_value = "job-123"
    mock_sky.get.return_value = {"status": "SUCCESS"}

    result = await actuator.provision_node(target)

    assert "cluster_name" in result
    assert result["status"] == "provisioned"
    mock_sky.Resources.assert_called_once()
    mock_sky.Task.assert_called_once()
    mock_sky.launch.assert_called_once()


@pytest.mark.asyncio
async def test_provision_node_with_hardware(actuator: SkyPilotActuator, mock_sky: Any) -> None:
    hardware = HardwareProfile(accelerator_type="urn:coreason:accelerator:h100")
    target = SkyPilotTarget(hardware_profile=hardware, use_spot=False)

    mock_sky.launch.return_value = "job-456"
    mock_sky.get.return_value = {"status": "SUCCESS"}

    await actuator.provision_node(target)

    mock_sky.Resources.assert_called_with(accelerators="H100:1", use_spot=False)


@pytest.mark.asyncio
async def test_destroy_node(actuator: SkyPilotActuator, mock_sky: Any) -> None:
    mock_sky.down.return_value = "job-789"
    mock_sky.get.return_value = None

    await actuator.destroy_node("test-cluster")

    mock_sky.down.assert_called_with("test-cluster")
    mock_sky.get.assert_called_with("job-789")


@pytest.mark.asyncio
async def test_reconcile_state(actuator: SkyPilotActuator, mock_sky: Any) -> None:
    mock_sky.status.return_value = "job-status"
    mock_handle = MagicMock()
    mock_handle.cloud.name.return_value = "aws"

    mock_sky.get.return_value = [
        {
            "name": "coreason-sky-123",
            "status": "UP",
            "handle": mock_handle,
            "resources": "A100:1",
        },
        {"name": "other-cluster", "status": "UP"},
    ]

    nodes = await actuator.reconcile_state()

    assert len(nodes) == 1
    assert nodes[0]["cluster_name"] == "coreason-sky-123"
    assert nodes[0]["provider"] == "aws"
    assert nodes[0]["vram_capacity"] == 80.0


@pytest.mark.asyncio
async def test_thermodynamic_guillotine(actuator: SkyPilotActuator, mock_sky: Any) -> None:
    # Setup reconcile_state mock
    mock_sky.status.return_value = "job-status"
    mock_sky.get.side_effect = [
        [{"name": "coreason-sky-123", "status": "UP"}],  # reconcile_state
        None,  # destroy_node (sky.get(rid))
    ]
    mock_sky.down.return_value = "job-down"

    await actuator.execute_thermodynamic_guillotine(True)

    mock_sky.down.assert_called_with("coreason-sky-123")


@pytest.mark.asyncio
async def test_thermodynamic_guillotine_no_breach(actuator: SkyPilotActuator, mock_sky: Any) -> None:
    await actuator.execute_thermodynamic_guillotine(False)
    mock_sky.status.assert_not_called()


@pytest.mark.asyncio
async def test_provision_node_with_mesh_injection(actuator: SkyPilotActuator, mock_sky: Any) -> None:
    hardware = HardwareProfile(accelerator_type="urn:coreason:accelerator:a100")
    security = SecurityProfile()
    target = SkyPilotTarget(
        hardware_profile=hardware,
        security_profile=security,
        mesh_auth_key="test-key",
        temporal_mesh_ip="1.2.3.4",
        use_spot=True,
    )

    # Mock MeshInjector
    with patch.object(actuator.injector, "compile_payload", return_value="payload-b64"):
        mock_sky.launch.return_value = "job-mesh"
        mock_sky.get.return_value = {"status": "SUCCESS"}

        await actuator.provision_node(target)

    # Verify setup commands were generated
    task_call_args = mock_sky.Task.call_args
    setup_cmd = task_call_args.kwargs["setup"]
    assert "mkdir -p /etc/coreason" in setup_cmd
    assert "payload-b64" in setup_cmd
    assert "/opt/coreason/bin/bootstrap.sh" in setup_cmd


@pytest.mark.asyncio
async def test_reconcile_state_handle_exception(actuator: SkyPilotActuator, mock_sky: Any) -> None:
    mock_sky.status.return_value = "job-status"

    # Create a mock cluster where accessing handle.cloud.name raises an exception
    mock_handle = MagicMock()
    mock_handle.cloud.name.side_effect = Exception("Cloud extraction failed")

    mock_sky.get.return_value = [
        {"name": "coreason-sky-error", "status": "UP", "handle": mock_handle}
    ]

    nodes = await actuator.reconcile_state()

    assert len(nodes) == 1
    assert nodes[0]["cluster_name"] == "coreason-sky-error"
    assert nodes[0]["provider"] == "unknown"
