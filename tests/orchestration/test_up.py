from typing import Any
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from coreason_ecosystem.orchestration.up import (
    wait_for_postgres,
    wait_for_temporal,
    wait_for_port,
    execute_up,
    provision_swarm_topology,
)


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_wait_for_postgres_success(mock_exec: Any) -> None:
    proc = MagicMock()
    proc.communicate = AsyncMock()
    proc.returncode = 0
    mock_exec.return_value = proc
    await wait_for_postgres("docker-compose.yml", timeout=1.0)
    mock_exec.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_postgres_timeout(mock_sleep: Any, mock_exec: Any) -> None:
    proc = MagicMock()
    proc.communicate = AsyncMock()
    proc.returncode = 1
    mock_exec.return_value = proc

    with pytest.raises(
        TimeoutError, match="PostgreSQL failed to achieve application-layer readiness."
    ):
        await wait_for_postgres("docker-compose.yml", timeout=2.0)


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_temporal_success(mock_sleep: Any) -> None:
    # We can mock Client.connect if we can patch it, but we can also mock asyncio.wait_for directly
    # However, wait_for_temporal uses temporalio.client.Client.connect.
    # We can patch temporalio.client.Client.connect directly or handle import
    with patch("coreason_ecosystem.orchestration.up.asyncio.wait_for") as mock_wait_for:
        mock_wait_for.return_value = True
        await wait_for_temporal(timeout=1.0)
        mock_wait_for.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_temporal_timeout(mock_sleep: Any) -> None:
    with patch(
        "coreason_ecosystem.orchestration.up.asyncio.wait_for",
        side_effect=Exception("Failed"),
    ):
        with pytest.raises(
            TimeoutError,
            match="Temporal failed to achieve application-layer readiness.",
        ):
            await wait_for_temporal(timeout=2.0)


@pytest.mark.asyncio
@patch("asyncio.open_connection")
async def test_wait_for_port_success(mock_open_connection: Any) -> None:
    reader = MagicMock()
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    mock_open_connection.return_value = (reader, writer)

    await wait_for_port(8080, timeout=1.0)
    writer.close.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.open_connection", side_effect=Exception("Connection refused"))
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_port_timeout(
    mock_sleep: Any, mock_open_connection: Any
) -> None:
    with pytest.raises(
        TimeoutError, match="Fallback check failed. Port 8080 never bound."
    ):
        await wait_for_port(8080, timeout=2.0)


@pytest.mark.asyncio
@patch(
    "coreason_ecosystem.orchestration.up.calculate_epistemic_root",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.up.write_registry_lock")
@patch("coreason_ecosystem.orchestration.up.NATSCapabilityRegistry")
async def test_execute_up_success(
    mock_registry_cls: Any, mock_write_lock: Any, mock_calc_root: Any
) -> None:
    mock_calc_root.return_value = "hash"

    registry = MagicMock()
    registry.initialize = AsyncMock()
    registry.hydrate_from_compiled_matrix = AsyncMock()
    mock_registry_cls.return_value = registry

    await execute_up()

    registry.initialize.assert_called_once()


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.up.execute_up", new_callable=AsyncMock)
async def test_provision_swarm_topology(mock_execute_up: Any) -> None:
    manifest = MagicMock()
    manifest.swarm_objective_prompt = "test"
    manifest.agent_node_count = 3

    await provision_swarm_topology(manifest)
    mock_execute_up.assert_called_once()
