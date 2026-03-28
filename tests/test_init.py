# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import json
import shutil
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coreason_ecosystem.orchestration.init import execute_init


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Generator[Path]:
    import uuid

    project_name = f"test_swarm_workspace_{uuid.uuid4().hex}"
    path = Path.cwd() / project_name
    yield path
    if path.exists():
        shutil.rmtree(path)


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.subprocess.run")
async def test_execute_init_base_topology(
    mock_run: MagicMock, temp_project_dir: Path
) -> None:
    await execute_init(temp_project_dir.name, topology="base")

    # Verify directories
    assert (temp_project_dir / "src" / "agents").is_dir()
    assert (temp_project_dir / "src" / "capabilities").is_dir()
    assert (temp_project_dir / "src" / "intents").is_dir()
    assert (temp_project_dir / ".vscode").is_dir()

    # Verify files
    assert (temp_project_dir / "pyproject.toml").is_file()
    assert "coreason-runtime" in (temp_project_dir / "pyproject.toml").read_text()

    assert (temp_project_dir / "coreason_ontology.schema.json").is_file()
    schema = json.loads(
        (temp_project_dir / "coreason_ontology.schema.json").read_text()
    )
    assert schema["title"] == "Swarm Ontology"

    # Verify Base topology capabilities
    cap_dir = temp_project_dir / "src" / "capabilities"
    assert (cap_dir / "example_tool.py").is_file()

    # Verify Visual Cortex
    vscode_dir = temp_project_dir / ".vscode"
    assert (vscode_dir / "settings.json").is_file()
    settings = json.loads((vscode_dir / "settings.json").read_text())
    assert settings["coreason.isEpistemicWorkspace"] is True

    assert (vscode_dir / "tasks.json").is_file()
    tasks = json.loads((vscode_dir / "tasks.json").read_text())
    assert any(
        "Crystallize Capabilities" in task.get("label", "") for task in tasks["tasks"]
    )

    # Verify Immunological Hooks
    assert (temp_project_dir / ".pre-commit-config.yaml").is_file()
    assert (
        "epistemic-seal-check"
        in (temp_project_dir / ".pre-commit-config.yaml").read_text()
    )

    # Verify git init call
    mock_run.assert_called_once_with(
        ["git", "init"], cwd=temp_project_dir.name, check=False
    )


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.subprocess.run")
async def test_execute_init_medallion_topology(
    mock_run: MagicMock, temp_project_dir: Path
) -> None:
    _ = mock_run
    await execute_init(temp_project_dir.name, topology="medallion")
    cap_dir = temp_project_dir / "src" / "capabilities"
    assert (cap_dir / "bronze_ingest.py").is_file()
    assert (cap_dir / "silver_cleanse.py").is_file()
    assert (cap_dir / "gold_route.py").is_file()


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.subprocess.run")
async def test_execute_init_rag_topology(
    mock_run: MagicMock, temp_project_dir: Path
) -> None:
    _ = mock_run
    await execute_init(temp_project_dir.name, topology="rag")
    cap_dir = temp_project_dir / "src" / "capabilities"
    assert (cap_dir / "embed_document.py").is_file()
    assert (cap_dir / "retrieve_context.py").is_file()


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.subprocess.run")
@patch("importlib.metadata.version")
async def test_execute_init_package_not_found(
    mock_version: MagicMock, mock_run: MagicMock, temp_project_dir: Path
) -> None:
    import importlib.metadata

    mock_version.side_effect = importlib.metadata.PackageNotFoundError
    await execute_init(temp_project_dir.name, topology="base")

    assert (Path.cwd() / temp_project_dir.name / "pyproject.toml").is_file()
    toml_content = (Path.cwd() / temp_project_dir.name / "pyproject.toml").read_text()
    assert "coreason-runtime==0.1.0" in toml_content
    assert "coreason-manifest==0.1.0" in toml_content


@pytest.mark.asyncio
async def test_execute_init_path_traversal() -> None:
    with pytest.raises(ValueError, match="path separators are not allowed"):
        await execute_init("../malicious_dir", topology="base")

    with pytest.raises(ValueError, match="path separators are not allowed"):
        await execute_init("some/dir", topology="base")

    with pytest.raises(ValueError, match="path separators are not allowed"):
        await execute_init("some\\dir", topology="base")

    with pytest.raises(
        ValueError,
        match="must resolve to a subdirectory of the current working directory",
    ):
        await execute_init(".", topology="base")
