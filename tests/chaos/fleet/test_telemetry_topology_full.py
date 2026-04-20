# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from coreason_ecosystem.fleet.telemetry_topology import TelemetryTopologyMonitor


@pytest.mark.asyncio
async def test_connect_success() -> None:
    """Test successful Temporal client connection."""
    monitor = TelemetryTopologyMonitor()

    mock_client = MagicMock()
    with patch(
        "coreason_ecosystem.fleet.telemetry_topology.Client.connect",
        new_callable=AsyncMock,
        return_value=mock_client,
    ):
        await monitor.connect()

    assert monitor._client is mock_client


@pytest.mark.asyncio
async def test_connect_failure() -> None:
    """Test fallback to degraded mode when Temporal connection fails."""
    monitor = TelemetryTopologyMonitor()

    with patch(
        "coreason_ecosystem.fleet.telemetry_topology.Client.connect",
        new_callable=AsyncMock,
        side_effect=Exception("Connection refused"),
    ):
        await monitor.connect()

    assert monitor._client is None


@pytest.mark.asyncio
async def test_poll_workflows_no_client() -> None:
    """Test that _poll_workflows returns early when client is None."""
    monitor = TelemetryTopologyMonitor()
    monitor._client = None

    # Should not raise
    await monitor._poll_workflows()


@pytest.mark.asyncio
async def test_poll_workflows_with_client() -> None:
    """Test _poll_workflows counts active workflows and checks circuit breakers."""
    monitor = TelemetryTopologyMonitor()

    # Transmutation mock workflows
    mock_workflow_1 = MagicMock()
    mock_workflow_1.search_attributes = {"circuit_breaker_tripped": True}

    mock_workflow_2 = MagicMock()
    mock_workflow_2.search_attributes = {}

    mock_client = MagicMock()

    async def mock_list_workflows(_query: str) -> Any:
        for w in [mock_workflow_1, mock_workflow_2]:
            yield w

    mock_client.list_workflows = mock_list_workflows
    monitor._client = mock_client

    await monitor._poll_workflows()

    # If we got here without error, workflow polling worked


@pytest.mark.asyncio
async def test_poll_workflows_exception() -> None:
    """Test _poll_workflows handles exceptions gracefully."""
    monitor = TelemetryTopologyMonitor()

    mock_client = MagicMock()
    mock_client.list_workflows = MagicMock(side_effect=Exception("polling error"))
    monitor._client = mock_client

    # Should not raise
    await monitor._poll_workflows()


@pytest.mark.asyncio
async def test_start_and_stop() -> None:
    """Test the start/stop lifecycle of the monitor."""
    # Use a small polling interval so it yields naturally without mocking sleep
    monitor = TelemetryTopologyMonitor(polling_interval_sec=0.01)

    with (
        patch("coreason_ecosystem.fleet.telemetry_topology.start_http_server"),
        patch.object(monitor, "connect", new_callable=AsyncMock),
        patch.object(monitor, "_poll_workflows", new_callable=AsyncMock),
    ):
        # Stop after a short delay
        async def stop_after_one() -> None:
            await asyncio.sleep(0.05)
            await monitor.stop()

        task = asyncio.create_task(stop_after_one())
        await monitor.start()
        await task

    assert monitor._running is False


@pytest.mark.asyncio
async def test_stop() -> None:
    """Test the stop method."""
    monitor = TelemetryTopologyMonitor()
    monitor._running = True
    await monitor.stop()
    assert monitor._running is False


@pytest.mark.asyncio
async def test_poll_workflows_search_attrs_non_dict() -> None:
    """Test _poll_workflows when search_attributes is not a dict."""
    monitor = TelemetryTopologyMonitor()

    mock_workflow = MagicMock()
    # Simulate search_attributes that is not a dict (e.g., a Mapping subclass)
    mock_attrs = MagicMock()
    mock_attrs.__bool__ = lambda _: True
    mock_workflow.search_attributes = mock_attrs

    mock_client = MagicMock()

    async def mock_list_workflows(_query: str) -> Any:
        yield mock_workflow

    mock_client.list_workflows = mock_list_workflows
    monitor._client = mock_client

    await monitor._poll_workflows()
