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
    coreason_betti_0,
    coreason_active_agents_total,
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
async def test_poll_workflows_computes_betti_0(
    monitor: TelemetryTopologyMonitor,
) -> None:
    """With two disconnected workflows, β₀ must equal 2 (fragmentation)."""
    mock_wf_1 = MagicMock()
    mock_wf_1.id = "wf-parent"
    mock_wf_1.parent_execution = None
    mock_wf_1.search_attributes = {}

    mock_wf_2 = MagicMock()
    mock_wf_2.id = "wf-orphan"
    mock_wf_2.parent_execution = None
    mock_wf_2.search_attributes = {}

    mock_client = MagicMock()

    async def mock_list_workflows(_query: str) -> Any:
        for w in [mock_wf_1, mock_wf_2]:
            yield w

    mock_client.list_workflows = mock_list_workflows
    monitor._client = mock_client

    await monitor._poll_workflows()

    assert coreason_active_agents_total._value.get() == 2  # type: ignore[union-attr]
    assert coreason_betti_0._value.get() == 2  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_poll_workflows_connected_graph(
    monitor: TelemetryTopologyMonitor,
) -> None:
    """A child linked to a parent forms 1 connected component (β₀ = 1)."""
    mock_parent = MagicMock()
    mock_parent.id = "wf-parent"
    mock_parent.parent_execution = None
    mock_parent.search_attributes = {}

    mock_child = MagicMock()
    mock_child.id = "wf-child"
    mock_child_parent = MagicMock()
    mock_child_parent.workflow_id = "wf-parent"
    mock_child.parent_execution = mock_child_parent
    mock_child.search_attributes = {}

    mock_client = MagicMock()

    async def mock_list_workflows(_query: str) -> Any:
        for w in [mock_parent, mock_child]:
            yield w

    mock_client.list_workflows = mock_list_workflows
    monitor._client = mock_client

    await monitor._poll_workflows()

    assert coreason_active_agents_total._value.get() == 2  # type: ignore[union-attr]
    assert coreason_betti_0._value.get() == 1  # type: ignore[union-attr]
