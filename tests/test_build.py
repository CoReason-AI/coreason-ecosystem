# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from coreason_ecosystem.cli import app

runner = CliRunner()


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.read_bytes")
@patch("coreason_ecosystem.orchestration.build.Path.open")
@patch("coreason_ecosystem.orchestration.build.Path.is_dir")
@patch("coreason_ecosystem.orchestration.build.Path.rglob")
@patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec")
def test_build_command_dir(
    mock_run: Any,
    mock_rglob: Any,
    mock_is_dir: Any,
    mock_open: Any,
    mock_read_bytes: Any,
    mock_exists: Any,
) -> None:
    """Test the build command execution logic."""
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"print('hello')"
    mock_is_dir.return_value = True
    mock_rglob.return_value = [Path("test1.py"), Path("test2.py")]
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")
    mock_run.return_value = mock_proc

    import io

    # We need to simulate the file open for both reading and writing the JSON
    # For writing, mock the open context manager
    mock_file = io.StringIO(json.dumps({"test": "hash"}))
    mock_open.return_value.__enter__.return_value = mock_file

    result = runner.invoke(app, ["build", "dummy_dir"])
    assert result.exit_code == 0
    assert "Capability Crystallized" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.is_dir")
@patch("coreason_ecosystem.orchestration.build.Path.rglob")
def test_build_command_dir_no_files(
    mock_rglob: Any, mock_is_dir: Any, mock_exists: Any
) -> None:
    """Test the build command execution logic."""
    mock_exists.return_value = True
    mock_is_dir.return_value = True
    mock_rglob.return_value = []

    result = runner.invoke(app, ["build", "dummy_dir"])
    assert result.exit_code == 0
    assert "Warning" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.is_dir")
def test_build_command_dir_no_cap_dir(mock_is_dir: Any, mock_exists: Any) -> None:
    """Test the build command execution logic when capabilities dir does not exist."""
    mock_exists.side_effect = [True, False, False, False]
    mock_is_dir.return_value = True

    result = runner.invoke(app, ["build", "dummy_dir"])
    assert result.exit_code == 0
    assert "Warning" in result.stdout
