# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import json
import shutil
import uuid
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coreason_ecosystem.orchestration.init import execute_init


@pytest.fixture
def temp_project_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[str, Path]]:
    monkeypatch.chdir(tmp_path)
    project_name = f"test_swarm_workspace_{uuid.uuid4().hex}"
    path = tmp_path / project_name
    yield project_name, path
    if path.exists():
        shutil.rmtree(path)


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.asyncio.create_subprocess_exec")
async def test_execute_init_base_topology(
    mock_exec: MagicMock, temp_project_dir: tuple[str, Path]
) -> None:
    project_name, project_path = temp_project_dir
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_exec.return_value = mock_process

    await execute_init(project_name, topology="base")

    # Verify directories
    package_name = project_name.replace("-", "_")
    package_dir = project_path / "src" / package_name
    assert (package_dir / "agents").is_dir()
    assert (package_dir / "capabilities").is_dir()
    assert (package_dir / "intents").is_dir()
    assert (project_path / ".vscode").is_dir()

    # Verify files
    assert (project_path / "pyproject.toml").is_file()
    assert "coreason-runtime" in (project_path / "pyproject.toml").read_text()

    assert (project_path / "coreason_ontology.schema.json").is_file()
    schema = json.loads((project_path / "coreason_ontology.schema.json").read_text())
    assert schema["title"] == "Swarm Ontology"

    # Verify Base topology capabilities
    cap_dir = package_dir / "capabilities"
    assert (cap_dir / "example_tool.py").is_file()

    # Verify Visual Cortex
    vscode_dir = project_path / ".vscode"
    assert (vscode_dir / "settings.json").is_file()
    settings = json.loads((vscode_dir / "settings.json").read_text())
    assert settings["coreason.isEpistemicWorkspace"] is True

    assert (vscode_dir / "tasks.json").is_file()
    tasks = json.loads((vscode_dir / "tasks.json").read_text())
    assert any(
        "Crystallize Capabilities" in task.get("label", "") for task in tasks["tasks"]
    )

    # Verify Immunological Hooks
    assert (project_path / ".pre-commit-config.yaml").is_file()
    assert (
        "epistemic-seal-check" in (project_path / ".pre-commit-config.yaml").read_text()
    )

    # Verify git init call
    mock_exec.assert_called_once_with("git", "init", cwd=str(project_path))
    mock_process.communicate.assert_called_once()


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.asyncio.create_subprocess_exec")
async def test_execute_init_medallion_topology(
    mock_exec: MagicMock, temp_project_dir: tuple[str, Path]
) -> None:
    project_name, project_path = temp_project_dir
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_exec.return_value = mock_process

    await execute_init(project_name, topology="medallion")
    package_name = project_name.replace("-", "_")
    cap_dir = project_path / "src" / package_name / "capabilities"
    assert (cap_dir / "bronze_ingest.py").is_file()
    assert (cap_dir / "silver_cleanse.py").is_file()
    assert (cap_dir / "gold_route.py").is_file()


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.asyncio.create_subprocess_exec")
async def test_execute_init_rag_topology(
    mock_exec: MagicMock, temp_project_dir: tuple[str, Path]
) -> None:
    project_name, project_path = temp_project_dir
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_exec.return_value = mock_process

    await execute_init(project_name, topology="rag")
    package_name = project_name.replace("-", "_")
    cap_dir = project_path / "src" / package_name / "capabilities"
    assert (cap_dir / "embed_document.py").is_file()
    assert (cap_dir / "retrieve_context.py").is_file()


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.asyncio.create_subprocess_exec")
@patch("importlib.metadata.version")
async def test_execute_init_package_not_found(
    mock_version: MagicMock, mock_exec: MagicMock, temp_project_dir: tuple[str, Path]
) -> None:
    import importlib.metadata

    project_name, project_path = temp_project_dir
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_exec.return_value = mock_process

    mock_version.side_effect = importlib.metadata.PackageNotFoundError
    await execute_init(project_name, topology="base")

    assert (project_path / "pyproject.toml").is_file()
    toml_content = (project_path / "pyproject.toml").read_text()
    assert "coreason-runtime>=0.1.0" in toml_content
    assert "coreason-manifest>=0.1.0" in toml_content
    assert "coreason-ecosystem>=0.1.0" in toml_content
    assert "componentize-py" in toml_content
    assert "extism-pdk" in toml_content


@pytest.mark.asyncio
async def test_execute_init_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="Project name cannot contain path separators"):
        await execute_init("nested/path")

    with pytest.raises(ValueError, match="Project name cannot contain path separators"):
        await execute_init("nested\\path")

    with pytest.raises(
        ValueError,
        match="Project path must be a subdirectory of the current working directory",
    ):
        await execute_init("..")

    with pytest.raises(
        ValueError,
        match="Project path must be a subdirectory of the current working directory",
    ):
        await execute_init(".")
