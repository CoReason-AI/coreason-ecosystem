from typing import Any
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import typer

from coreason_ecosystem.orchestration.sync import (
    detect_and_heal_drift,
    execute_sync,
)


@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_detect_and_heal_drift(mock_exec: Any) -> None:
    proc = MagicMock()
    # first proc for prune
    # second proc for ls (returns b"coreason-test\ncoreason-default\nother")
    # third proc for rm "coreason-test"
    proc.communicate = AsyncMock(
        side_effect=[
            (b"", b""),
            (b"coreason-test\ncoreason-default\nother\n", b""),
            (b"", b""),
        ]
    )
    mock_exec.return_value = proc

    await detect_and_heal_drift("docker")
    assert mock_exec.call_count == 3


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.sync.Path.cwd")
@patch(
    "coreason_ecosystem.orchestration.sync.calculate_epistemic_root",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.sync.write_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.sync.detect_and_heal_drift",
    new_callable=AsyncMock,
)
@patch("asyncio.create_subprocess_exec")
async def test_execute_sync_success(
    mock_exec: Any,
    mock_drift: Any,
    mock_lock: Any,
    mock_root: Any,
    mock_cwd: Any,
    tmp_path: Any,
) -> None:
    # Setup mock cwd to tmp_path
    mock_cwd.return_value = tmp_path
    mock_root.return_value = "hash"

    # Create fake compose.yaml
    compose_path = tmp_path / "infrastructure" / "local"
    compose_path.mkdir(parents=True)
    (compose_path / "compose.yaml").write_text("version: '3'")

    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"out", b"err"))
    proc.returncode = 0
    mock_exec.return_value = proc

    await execute_sync()

    mock_drift.assert_called_once()
    mock_exec.assert_called_once()
    assert (tmp_path / "coreason_ontology.schema.json").exists()


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.sync.Path.cwd")
@patch(
    "coreason_ecosystem.orchestration.sync.calculate_epistemic_root",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.sync.write_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.sync.detect_and_heal_drift",
    new_callable=AsyncMock,
)
@patch("asyncio.create_subprocess_exec")
async def test_execute_sync_no_compose(
    mock_exec: Any,
    mock_drift: Any,
    mock_lock: Any,
    mock_root: Any,
    mock_cwd: Any,
    tmp_path: Any,
) -> None:
    mock_cwd.return_value = tmp_path
    # compose.yaml does not exist

    with patch("coreason_ecosystem.orchestration.sync.Path.exists", return_value=False):
        with pytest.raises(typer.Exit) as exc:
            await execute_sync()

    assert exc.value.exit_code == 1


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.sync.Path.cwd")
@patch(
    "coreason_ecosystem.orchestration.sync.calculate_epistemic_root",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.sync.write_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.sync.detect_and_heal_drift",
    new_callable=AsyncMock,
)
@patch("asyncio.create_subprocess_exec")
async def test_execute_sync_docker_compose_fails(
    mock_exec: Any,
    mock_drift: Any,
    mock_lock: Any,
    mock_root: Any,
    mock_cwd: Any,
    tmp_path: Any,
) -> None:
    mock_cwd.return_value = tmp_path
    compose_path = tmp_path / "infrastructure" / "local"
    compose_path.mkdir(parents=True)
    (compose_path / "compose.yaml").write_text("version: '3'")

    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"out", b"error output"))
    proc.returncode = 1
    mock_exec.return_value = proc

    with pytest.raises(typer.Exit) as exc:
        await execute_sync()

    assert exc.value.exit_code == 1
