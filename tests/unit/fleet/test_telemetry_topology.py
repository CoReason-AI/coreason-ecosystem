# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Unit tests for TelemetryTopologyMonitor — TDA invariant verification."""

from unittest.mock import MagicMock
from typing import Any

import pytest

from coreason_ecosystem.fleet.telemetry_topology import (
    TelemetryTopologyMonitor,
    coreason_active_agents_total,
    coreason_causal_cycles_total,
)


@pytest.fixture
def monitor() -> TelemetryTopologyMonitor:
    return TelemetryTopologyMonitor()


@pytest.mark.asyncio
async def test_poll_workflows_no_client(monitor: TelemetryTopologyMonitor) -> None:
    """Without a Temporal client, polling must be a no-op."""
    assert monitor._client is None
    await monitor._poll_workflows()


@pytest.mark.asyncio
async def test_poll_workflows_computes_betti_0_fragmented(
    monitor: TelemetryTopologyMonitor,
) -> None:
    """Two disconnected workflows → β₀ = 2 (fragmentation detected)."""
    mock_wf_1 = MagicMock()
    mock_wf_1.id = "wf-parent"
    mock_wf_1.parent_id = None
    mock_wf_1.search_attributes = {}

    mock_wf_2 = MagicMock()
    mock_wf_2.id = "wf-orphan"
    mock_wf_2.parent_id = None
    mock_wf_2.search_attributes = {}

    mock_client = MagicMock()

    async def mock_list_workflows(_query: str) -> Any:
        for w in [mock_wf_1, mock_wf_2]:
            yield w

    mock_client.list_workflows = mock_list_workflows
    monitor._client = mock_client

    await monitor._poll_workflows()

    assert coreason_active_agents_total._value.get() == 2


@pytest.mark.asyncio
async def test_poll_workflows_connected_graph(
    monitor: TelemetryTopologyMonitor,
) -> None:
    """A child linked to a parent → β₀ = 1 (cohesive swarm)."""
    mock_parent = MagicMock()
    mock_parent.id = "wf-parent"
    mock_parent.parent_id = None
    mock_parent.search_attributes = {}

    mock_child = MagicMock()
    mock_child.id = "wf-child"
    mock_child.parent_id = "wf-parent"
    mock_child.search_attributes = {}

    mock_client = MagicMock()

    async def mock_list_workflows(_query: str) -> Any:
        for w in [mock_parent, mock_child]:
            yield w

    mock_client.list_workflows = mock_list_workflows
    monitor._client = mock_client

    await monitor._poll_workflows()

    assert coreason_active_agents_total._value.get() == 1


@pytest.mark.asyncio
async def test_poll_workflows_detects_causal_cycles(
    monitor: TelemetryTopologyMonitor,
) -> None:
    """A→B→C→A cycle → β₁ > 0 (causal paradox detected)."""
    mock_a = MagicMock()
    mock_a.id = "wf-a"
    mock_a.parent_id = "wf-c"
    mock_a.search_attributes = {}

    mock_b = MagicMock()
    mock_b.id = "wf-b"
    mock_b.parent_id = "wf-a"
    mock_b.search_attributes = {}

    mock_c = MagicMock()
    mock_c.id = "wf-c"
    mock_c.parent_id = "wf-b"
    mock_c.search_attributes = {}

    mock_client = MagicMock()

    async def mock_list_workflows(_query: str) -> Any:
        for w in [mock_a, mock_b, mock_c]:
            yield w

    mock_client.list_workflows = mock_list_workflows
    monitor._client = mock_client

    await monitor._poll_workflows()

    # β₁ > 0 proves a causal cycle was detected.
    assert coreason_causal_cycles_total._value.get() > 0


@pytest.mark.asyncio
async def test_poll_workflows_vram_demand_exception(
    monitor: TelemetryTopologyMonitor,
) -> None:
    mock_wf = MagicMock()
    mock_wf.id = "wf-test"
    mock_wf.parent_id = None
    mock_wf.search_attributes = {"vram_demand_gb": "invalid_float"}

    mock_client = MagicMock()

    async def mock_list_workflows(_query: str) -> Any:
        yield mock_wf

    mock_client.list_workflows = mock_list_workflows
    monitor._client = mock_client

    await monitor._poll_workflows()
    # Execution completes without raising an error
