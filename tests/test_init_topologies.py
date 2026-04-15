# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Tests for the init module topology-specific scaffolding."""

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
    project_name = f"test_init_topo_{uuid.uuid4().hex[:8]}"
    path = tmp_path / project_name
    yield project_name, path
    if path.exists():
        shutil.rmtree(path)


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.asyncio.create_subprocess_exec")
async def test_init_medallion_topology(
    mock_exec: MagicMock, temp_project_dir: tuple[str, Path]
) -> None:
    """Test init with medallion topology creates medallion-specific capabilities."""
    project_name, project_path = temp_project_dir
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_exec.return_value = mock_process

    await execute_init(project_name, topology="medallion")

    package_name = project_name.replace("-", "_")
    cap_dir = project_path / "src" / package_name / "capabilities"
    assert (cap_dir / "bronze_ingest.py").exists()
    assert (cap_dir / "silver_cleanse.py").exists()
    assert (cap_dir / "gold_route.py").exists()
    assert not (cap_dir / "example_tool.py").exists()


@pytest.mark.asyncio
@patch("coreason_ecosystem.orchestration.init.asyncio.create_subprocess_exec")
async def test_init_rag_topology(
    mock_exec: MagicMock, temp_project_dir: tuple[str, Path]
) -> None:
    """Test init with RAG topology creates retrieval-specific capabilities."""
    project_name, project_path = temp_project_dir
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_exec.return_value = mock_process

    await execute_init(project_name, topology="rag")

    package_name = project_name.replace("-", "_")
    cap_dir = project_path / "src" / package_name / "capabilities"
    assert (cap_dir / "embed_document.py").exists()
    assert (cap_dir / "retrieve_context.py").exists()
    assert not (cap_dir / "example_tool.py").exists()
