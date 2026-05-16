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
from coreason_ecosystem.fleet.skypilot_actuator import SkyPilotActuator, SkyPilotTarget
from typing import Any, Dict, List
from coreason_manifest.spec.ontology import (
    SpatialHardwareProfile as HardwareProfile,
    EpistemicSecurityProfile as SecurityProfile,
)

class FakeTask:
    def __init__(self, setup=None, run=None):
        self.setup = setup
        self.run = run
        self.resources = None
    
    def set_resources(self, resources):
        self.resources = resources

class FakeSky:
    """Fake SkyPilot module for physical substrate testing."""
    def __init__(self):
        self.launch_called = False
        self.down_called = False
        self.resources_called = False
        self.task_called = False
        self.status_data = []
        self.last_resources = None
        self.last_task = None
        self.results = {}

    def Resources(self, cloud=None, accelerators=None, use_spot=True):
        self.resources_called = True
        self.last_resources = {"cloud": cloud, "accelerators": accelerators, "use_spot": use_spot}
        return self.last_resources

    def Task(self, setup=None, run=None):
        self.task_called = True
        self.last_task = FakeTask(setup=setup, run=run)
        return self.last_task

    def launch(self, task, cluster_name, idle_minutes_to_autostop):
        self.launch_called = True
        rid = f"rid-launch-{cluster_name}"
        self.results[rid] = {"status": "SUCCESS"}
        return rid

    def status(self, cluster_names=None, refresh=True):
        rid = "rid-status"
        self.results[rid] = self.status_data
        return rid

    def down(self, cluster_name):
        self.down_called = True
        rid = f"rid-down-{cluster_name}"
        self.results[rid] = {"status": "DOWN"}
        return rid
    
    def get(self, rid):
        return self.results.get(rid)

    class AWS:
        def name(self): return "aws"
    class GCP:
        def name(self): return "gcp"

@pytest.fixture
def fake_sky():
    return FakeSky()

@pytest.fixture
def actuator(monkeypatch, fake_sky):
    import coreason_ecosystem.fleet.skypilot_actuator as sp_module
    monkeypatch.setattr(sp_module, "sky", fake_sky)
    return SkyPilotActuator()

@pytest.mark.asyncio
async def test_provision_node_basic(actuator: SkyPilotActuator, fake_sky: FakeSky) -> None:
    target = SkyPilotTarget(use_spot=True, autostop_idle_minutes=15)
    result = await actuator.provision_node(target)

    assert "cluster_name" in result
    assert result["status"] == "provisioned"
    assert fake_sky.resources_called
    assert fake_sky.task_called
    assert fake_sky.launch_called

@pytest.mark.asyncio
async def test_provision_node_with_hardware(
    actuator: SkyPilotActuator, fake_sky: FakeSky
) -> None:
    hardware = HardwareProfile(accelerator_type="urn:coreason:accelerator:h100")
    target = SkyPilotTarget(hardware_profile=hardware, use_spot=False)

    await actuator.provision_node(target)

    assert fake_sky.last_task.resources["accelerators"] == "H100:1"
    assert fake_sky.last_task.resources["use_spot"] is False

@pytest.mark.asyncio
async def test_destroy_node(actuator: SkyPilotActuator, fake_sky: FakeSky) -> None:
    await actuator.destroy_node("test-cluster")
    assert fake_sky.down_called

@pytest.mark.asyncio
async def test_reconcile_state(actuator: SkyPilotActuator, fake_sky: FakeSky) -> None:
    class MockHandle:
        def __init__(self):
            self.cloud = FakeSky.AWS()

    fake_sky.status_data = [
        {
            "name": "coreason-sky-123",
            "status": "UP",
            "handle": MockHandle(),
            "resources": "A100:1",
        }
    ]

    nodes = await actuator.reconcile_state()

    assert len(nodes) == 1
    assert nodes[0]["cluster_name"] == "coreason-sky-123"
    assert nodes[0]["provider"] == "aws"
    assert nodes[0]["vram_capacity"] == 80.0

@pytest.mark.asyncio
async def test_thermodynamic_guillotine(
    actuator: SkyPilotActuator, fake_sky: FakeSky
) -> None:
    fake_sky.status_data = [{"name": "coreason-sky-123", "status": "UP"}]
    await actuator.execute_thermodynamic_guillotine(True)
    assert fake_sky.down_called

@pytest.mark.asyncio
async def test_thermodynamic_guillotine_no_breach(
    actuator: SkyPilotActuator, fake_sky: FakeSky
) -> None:
    await actuator.execute_thermodynamic_guillotine(False)
    assert not fake_sky.down_called

@pytest.mark.asyncio
async def test_provision_node_with_mesh_injection(
    actuator: SkyPilotActuator, fake_sky: FakeSky
) -> None:
    hardware = HardwareProfile(accelerator_type="urn:coreason:accelerator:a100")
    security = SecurityProfile()
    target = SkyPilotTarget(
        hardware_profile=hardware,
        security_profile=security,
        use_spot=True,
    )

    await actuator.provision_node(target)

    setup_cmd = fake_sky.last_task.setup
    assert "mkdir -p /etc/coreason" in setup_cmd
    assert "/opt/coreason/bin/bootstrap.sh" in setup_cmd
    assert "base64 -d" in setup_cmd

@pytest.mark.asyncio
async def test_reconcile_state_handle_exception(
    actuator: SkyPilotActuator, fake_sky: FakeSky
) -> None:
    class ErrorHandle:
        @property
        def cloud(self):
            raise Exception("Cloud extraction failed")

    fake_sky.status_data = [
        {"name": "coreason-sky-error", "status": "UP", "handle": ErrorHandle()}
    ]

    nodes = await actuator.reconcile_state()

    assert len(nodes) == 1
    assert nodes[0]["cluster_name"] == "coreason-sky-error"
    assert nodes[0]["provider"] == "unknown"
