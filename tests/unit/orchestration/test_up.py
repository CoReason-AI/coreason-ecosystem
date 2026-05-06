import asyncio
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, Generator, Tuple

import pytest
import typer

from coreason_ecosystem.orchestration.up import (
    wait_for_postgres,
    wait_for_temporal,
    wait_for_port,
    execute_up,
    provision_swarm_topology,
)
from coreason_manifest.spec.ontology import CognitiveSwarmDeploymentManifest

@pytest.mark.asyncio
async def test_wait_for_postgres_success() -> None:
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_exec.return_value = proc
        await wait_for_postgres("dummy_path", timeout=2.0)
        mock_exec.assert_awaited_once()

@pytest.mark.asyncio
async def test_wait_for_postgres_timeout() -> None:
    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch("asyncio.sleep", new_callable=AsyncMock)
    ):
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 1
        mock_exec.return_value = proc
        with pytest.raises(TimeoutError, match="PostgreSQL failed to achieve application-layer readiness."):
            await wait_for_postgres("dummy_path", timeout=1.0)

@pytest.mark.asyncio
async def test_wait_for_temporal_success() -> None:
    with (
        patch("temporalio.client.Client.connect", new_callable=AsyncMock) as mock_connect,
        patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait
    ):
        mock_wait.return_value = MagicMock()
        await wait_for_temporal(timeout=2.0)
        mock_wait.assert_awaited_once()

@pytest.mark.asyncio
async def test_wait_for_temporal_timeout() -> None:
    with (
        patch("asyncio.wait_for", side_effect=Exception("Connection refused")),
        patch("asyncio.sleep", new_callable=AsyncMock)
    ):
        with pytest.raises(TimeoutError, match="Temporal failed to achieve application-layer readiness."):
            await wait_for_temporal(timeout=1.0)

@pytest.mark.asyncio
async def test_wait_for_port_success() -> None:
    with (
        patch("asyncio.open_connection", new_callable=AsyncMock) as mock_open,
        patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait
    ):
        reader = AsyncMock()
        writer = AsyncMock()
        mock_wait.return_value = (reader, writer)
        await wait_for_port(8000, timeout=2.0)
        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()

@pytest.mark.asyncio
async def test_wait_for_port_timeout() -> None:
    with (
        patch("asyncio.wait_for", side_effect=Exception("Connection refused")),
        patch("asyncio.sleep", new_callable=AsyncMock)
    ):
        with pytest.raises(TimeoutError, match="Fallback check failed. Port 8000 never bound."):
            await wait_for_port(8000, timeout=1.0)

@pytest.fixture
def mock_up_dependencies() -> Generator[tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock, MagicMock], None, None]:
    with (
        patch("coreason_ecosystem.orchestration.up.Path.cwd") as mock_cwd,
        patch("shutil.copy2") as mock_copy,
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch("coreason_ecosystem.orchestration.up.wait_for_postgres", new_callable=AsyncMock) as mock_wp,
        patch("coreason_ecosystem.orchestration.up.wait_for_temporal", new_callable=AsyncMock) as mock_wt,
        patch("coreason_ecosystem.orchestration.up.wait_for_port", new_callable=AsyncMock) as mock_port,
        patch("coreason_ecosystem.orchestration.up.calculate_epistemic_root", new_callable=AsyncMock) as mock_calc,
        patch("coreason_ecosystem.orchestration.up.write_registry_lock") as mock_write
    ):
        mock_calc.return_value = "fake_root"
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_exec.return_value = proc
        
        # Setup paths to mock a missing file requiring copy
        tmp_path = Path("/tmp/mock_cwd")
        mock_cwd.return_value = tmp_path
        
        with patch.object(Path, "exists", return_value=False):
            yield mock_exec, mock_wp, mock_wt, mock_port, mock_copy

@pytest.mark.asyncio
async def test_execute_up_success(mock_up_dependencies: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock, MagicMock]) -> None:
    mock_exec, mock_wp, mock_wt, mock_port, mock_copy = mock_up_dependencies
    
    await execute_up()
    
    assert mock_exec.call_count == 5  # teardown, postgres, temporal, runtime, observability
    mock_copy.assert_called_once()
    mock_wp.assert_awaited_once()
    mock_wt.assert_awaited_once()
    mock_port.assert_awaited_once()

@pytest.mark.asyncio
async def test_execute_up_teardown_error(mock_up_dependencies: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock, MagicMock]) -> None:
    mock_exec, _, _, _, _ = mock_up_dependencies
    proc_err = AsyncMock()
    proc_err.communicate.return_value = (b"", b"error")
    proc_err.returncode = 1
    mock_exec.return_value = proc_err
    
    with pytest.raises(typer.Exit) as exc:
        await execute_up()
    assert exc.value.exit_code == 1
    assert mock_exec.call_count == 1

@pytest.mark.asyncio
async def test_execute_up_postgres_error(mock_up_dependencies: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock, MagicMock]) -> None:
    mock_exec, _, _, _, _ = mock_up_dependencies
    proc_ok = AsyncMock()
    proc_ok.communicate.return_value = (b"", b"")
    proc_ok.returncode = 0
    
    proc_err = AsyncMock()
    proc_err.communicate.return_value = (b"", b"error")
    proc_err.returncode = 1
    
    mock_exec.side_effect = [proc_ok, proc_err]
    
    with pytest.raises(typer.Exit) as exc:
        await execute_up()
    assert exc.value.exit_code == 1
    assert mock_exec.call_count == 2

@pytest.mark.asyncio
async def test_execute_up_postgres_timeout(mock_up_dependencies: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock, MagicMock]) -> None:
    mock_exec, mock_wp, _, _, _ = mock_up_dependencies
    mock_wp.side_effect = TimeoutError("PG timeout")
    
    with pytest.raises(typer.Exit) as exc:
        await execute_up()
    assert exc.value.exit_code == 1

@pytest.mark.asyncio
async def test_execute_up_temporal_timeout(mock_up_dependencies: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock, MagicMock]) -> None:
    mock_exec, mock_wp, mock_wt, _, _ = mock_up_dependencies
    mock_wt.side_effect = TimeoutError("Temporal timeout")
    
    with pytest.raises(typer.Exit) as exc:
        await execute_up()
    assert exc.value.exit_code == 1

@pytest.mark.asyncio
async def test_execute_up_daemon_timeout(mock_up_dependencies: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock, MagicMock]) -> None:
    mock_exec, mock_wp, mock_wt, mock_port, _ = mock_up_dependencies
    mock_port.side_effect = TimeoutError("Daemon timeout")
    
    with pytest.raises(typer.Exit) as exc:
        await execute_up()
    assert exc.value.exit_code == 1

@pytest.mark.asyncio
async def test_provision_swarm_topology() -> None:
    manifest = CognitiveSwarmDeploymentManifest.model_construct(  # type: ignore[call-arg]
        swarm_objective_prompt="test",
        agent_node_count=3,
    )
    with patch("coreason_ecosystem.orchestration.up.execute_up", new_callable=AsyncMock) as mock_up:
        await provision_swarm_topology(manifest)
        mock_up.assert_awaited_once()
