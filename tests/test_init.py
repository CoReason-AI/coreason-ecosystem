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
async def test_execute_init_scaffolding(
    mock_exec: MagicMock, temp_project_dir: tuple[str, Path]
) -> None:
    project_name, project_path = temp_project_dir
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_exec.return_value = mock_process

    await execute_init(project_name)

    # Verify generic package genesis structure
    package_name = project_name.replace("-", "_")
    package_dir = project_path / "src" / package_name
    assert package_dir.is_dir()
    assert (project_path / ".vscode").is_dir()

    # Verify dependencies
    assert (project_path / "pyproject.toml").is_file()
    assert "coreason-runtime" in (project_path / "pyproject.toml").read_text()

    # Verify Visual Cortex settings without capabilities logic
    vscode_dir = project_path / ".vscode"
    assert (vscode_dir / "settings.json").is_file()
    settings = json.loads((vscode_dir / "settings.json").read_text())
    assert settings["coreason.isEpistemicWorkspace"] is True

    assert (vscode_dir / "tasks.json").is_file()
    tasks = json.loads((vscode_dir / "tasks.json").read_text())
    assert any("Ignite Swarm" in task.get("label", "") for task in tasks["tasks"])

    # Verify Immunological Hooks
    assert (project_path / ".pre-commit-config.yaml").is_file()
    assert (
        "epistemic-seal-check" in (project_path / ".pre-commit-config.yaml").read_text()
    )

    # Verify git init call
    mock_exec.assert_called_once_with("git", "init", cwd=str(project_path))
    mock_process.communicate.assert_called_once()


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
