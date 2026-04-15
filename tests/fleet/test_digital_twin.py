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

from coreason_ecosystem.fleet.digital_twin import CyberPhysicalDigitalTwin
from coreason_manifest.spec.ontology import DigitalTwinTopologyManifest


@pytest.mark.asyncio
async def test_synchronize_topology() -> None:
    """Test topology synchronization ingests telemetry into cache."""
    twin = CyberPhysicalDigitalTwin(enforce_no_side_effects=True)
    manifest = DigitalTwinTopologyManifest(target_topology_cid="test-cid-123")

    await twin.synchronize_topology(manifest)

    assert "test-cid-123" in twin.iot_telemetry_cache
    cached = twin.iot_telemetry_cache["test-cid-123"]
    assert cached["temperature_celsius"] == 42.5
    assert cached["vibration_hz"] == 120.0
    assert cached["energy_draw_kw"] == 1.2


@pytest.mark.asyncio
async def test_dispatch_actuation_blocked() -> None:
    """Test that actuation is blocked when enforce_no_side_effects is True."""
    twin = CyberPhysicalDigitalTwin(enforce_no_side_effects=True)

    with pytest.raises(PermissionError, match="Volumetric Guillotine"):
        await twin.dispatch_actuation_command(
            "target-cid-456", {"command": "activate_motor"}
        )


@pytest.mark.asyncio
async def test_dispatch_actuation_allowed() -> None:
    """Test that actuation proceeds when enforce_no_side_effects is False."""
    twin = CyberPhysicalDigitalTwin(enforce_no_side_effects=False)

    # Should not raise
    await twin.dispatch_actuation_command(
        "target-cid-789", {"command": "activate_motor"}
    )


def test_default_enforce_no_side_effects() -> None:
    """Test that default enforce_no_side_effects is True."""
    twin = CyberPhysicalDigitalTwin()
    assert twin.enforce_no_side_effects is True
    assert twin.iot_telemetry_cache == {}
