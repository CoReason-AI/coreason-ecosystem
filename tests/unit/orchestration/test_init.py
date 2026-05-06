import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from typing import Any

from coreason_ecosystem.orchestration.init import execute_init


@pytest.mark.asyncio
async def test_execute_init_validation_path_separator(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Project name cannot contain path separators"):
        await execute_init("invalid/path")


@pytest.mark.asyncio
async def test_execute_init_validation_outside_cwd(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Project path must be a subdirectory"):
        await execute_init("..")


@pytest.mark.asyncio
async def test_execute_init_rust_topology(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_exec.return_value = mock_process

        await execute_init("my_rust_project", lang="rust")

    project_dir = tmp_path / "my_rust_project"
    assert project_dir.exists()
    assert (project_dir / ".vscode" / "settings.json").exists()
    assert (project_dir / ".vscode" / "tasks.json").exists()
    assert (project_dir / "Cargo.toml").exists()
    assert (project_dir / "src" / "lib.rs").exists()
    mock_exec.assert_called_once_with("git", "init", cwd=str(project_dir))
    mock_process.communicate.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_init_go_topology(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_exec.return_value = mock_process

        await execute_init("my_go_project", lang="go")

    project_dir = tmp_path / "my_go_project"
    assert project_dir.exists()
    assert (project_dir / ".vscode" / "settings.json").exists()
    assert (project_dir / ".vscode" / "tasks.json").exists()
    assert (project_dir / "go.mod").exists()
    assert (project_dir / "main.go").exists()


@pytest.mark.asyncio
async def test_execute_init_python_base_topology(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_exec.return_value = mock_process

        await execute_init("my_python_project", lang="python", topology="base")

    project_dir = tmp_path / "my_python_project"
    cap_dir = project_dir / "src" / "my_python_project" / "capabilities"
    assert cap_dir.exists()
    assert (cap_dir / "example_tool.py").exists()
    assert (project_dir / "pyproject.toml").exists()
    assert (project_dir / ".pre-commit-config.yaml").exists()


@pytest.mark.asyncio
async def test_execute_init_python_medallion_topology(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_exec.return_value = mock_process

        await execute_init("my_python_project", lang="python", topology="medallion")

    cap_dir = (
        tmp_path / "my_python_project" / "src" / "my_python_project" / "capabilities"
    )
    assert (cap_dir / "bronze_ingest.py").exists()
    assert (cap_dir / "silver_cleanse.py").exists()
    assert (cap_dir / "gold_route.py").exists()


@pytest.mark.asyncio
async def test_execute_init_python_rag_topology(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_exec.return_value = mock_process

        await execute_init("my_python_project", lang="python", topology="rag")

    cap_dir = (
        tmp_path / "my_python_project" / "src" / "my_python_project" / "capabilities"
    )
    assert (cap_dir / "embed_document.py").exists()
    assert (cap_dir / "retrieve_context.py").exists()


@pytest.mark.asyncio
async def test_execute_init_python_version_fallback(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Cover get_version() fallback when package is not installed."""
    import importlib.metadata

    monkeypatch.chdir(tmp_path)

    def _raise(*args: Any, **kwargs: Any) -> Any:
        raise importlib.metadata.PackageNotFoundError()

    with (
        patch("importlib.metadata.version", side_effect=_raise),
        patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_process = AsyncMock()
        mock_exec.return_value = mock_process
        await execute_init("fallback_project", lang="python", topology="base")

    pyproject = (tmp_path / "fallback_project" / "pyproject.toml").read_text()
    assert "coreason-runtime>=0.1.0" in pyproject
