import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from coreason_ecosystem.orchestration.up import (
    wait_for_postgres,
    wait_for_temporal,
    wait_for_port,
    execute_up,
    provision_swarm_topology,
)
import typer

@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_wait_for_postgres_success(mock_exec):
    proc = MagicMock()
    proc.communicate = AsyncMock()
    proc.returncode = 0
    mock_exec.return_value = proc
    await wait_for_postgres("docker-compose.yml", timeout=1.0)
    mock_exec.assert_called_once()

@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_postgres_timeout(mock_sleep, mock_exec):
    proc = MagicMock()
    proc.communicate = AsyncMock()
    proc.returncode = 1
    mock_exec.return_value = proc
    
    with pytest.raises(TimeoutError, match="PostgreSQL failed to achieve application-layer readiness."):
        await wait_for_postgres("docker-compose.yml", timeout=2.0)

@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_temporal_success(mock_sleep):
    # We can mock Client.connect if we can patch it, but we can also mock asyncio.wait_for directly
    # However, wait_for_temporal uses temporalio.client.Client.connect.
    # We can patch temporalio.client.Client.connect directly or handle import
    with patch("coreason_ecosystem.orchestration.up.asyncio.wait_for") as mock_wait_for:
        mock_wait_for.return_value = True
        await wait_for_temporal(timeout=1.0)
        mock_wait_for.assert_called_once()

@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_temporal_timeout(mock_sleep):
    with patch("coreason_ecosystem.orchestration.up.asyncio.wait_for", side_effect=Exception("Failed")):
        with pytest.raises(TimeoutError, match="Temporal failed to achieve application-layer readiness."):
            await wait_for_temporal(timeout=2.0)

@pytest.mark.asyncio
@patch("asyncio.open_connection")
async def test_wait_for_port_success(mock_open_connection):
    reader = MagicMock()
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    mock_open_connection.return_value = (reader, writer)
    
    await wait_for_port(8080, timeout=1.0)
    writer.close.assert_called_once()

@pytest.mark.asyncio
@patch("asyncio.open_connection", side_effect=Exception("Connection refused"))
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_port_timeout(mock_sleep, mock_open_connection):
    with pytest.raises(TimeoutError, match="Fallback check failed. Port 8080 never bound."):
        await wait_for_port(8080, timeout=2.0)

@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.up.calculate_epistemic_root", new_callable=AsyncMock)
@patch("coreason_ecosystem.orchestration.up.write_registry_lock")
@patch("asyncio.create_subprocess_exec")
@patch("coreason_ecosystem.orchestration.up.SovereignMCPRegistry")
async def test_execute_up_success(mock_registry_cls, mock_exec, mock_write_lock, mock_calc_root):
    mock_calc_root.return_value = "hash"
    
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"out", b"err"))
    proc.returncode = 0
    mock_exec.return_value = proc
    
    registry = MagicMock()
    registry.initialize = AsyncMock()
    registry.scan_action_space_modules = AsyncMock()
    mock_registry_cls.return_value = registry
    
    await execute_up()
    
    mock_exec.assert_called_once_with(
        "nemoclaw", "sandbox", "start", "--empty",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    registry.initialize.assert_called_once()
    registry.scan_action_space_modules.assert_called_once()

@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.up.calculate_epistemic_root", new_callable=AsyncMock)
@patch("coreason_ecosystem.orchestration.up.write_registry_lock")
@patch("asyncio.create_subprocess_exec")
async def test_execute_up_failure(mock_exec, mock_write_lock, mock_calc_root):
    mock_calc_root.return_value = "hash"
    
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"out", b"err"))
    proc.returncode = 1
    mock_exec.return_value = proc
    
    with pytest.raises(typer.Exit) as exc_info:
        await execute_up()
    
    assert exc_info.value.exit_code == 1

@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.up.execute_up", new_callable=AsyncMock)
async def test_provision_swarm_topology(mock_execute_up):
    from coreason_manifest.spec.ontology import CognitiveSwarmDeploymentManifest
    
    manifest = MagicMock()
    manifest.swarm_objective_prompt = "test"
    manifest.agent_node_count = 3
    
    await provision_swarm_topology(manifest)
    mock_execute_up.assert_called_once()
