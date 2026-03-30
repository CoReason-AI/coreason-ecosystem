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
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from coreason_ecosystem.cli import app

runner = CliRunner()


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.read_bytes")
@patch("coreason_ecosystem.orchestration.build.Path.open")
@patch("coreason_ecosystem.orchestration.build.Path.mkdir")
@patch("coreason_ecosystem.orchestration.build.FileLock")
@patch("coreason_ecosystem.orchestration.build.Path.is_dir")
@patch("coreason_ecosystem.orchestration.build.Path.rglob")
@patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec")
def test_build_command_dir(
    mock_create_subprocess_exec: Any,
    mock_rglob: Any,
    mock_is_dir: Any,
    mock_filelock: Any,
    mock_mkdir: Any,
    mock_open: Any,
    mock_read_bytes: Any,
    mock_exists: Any,
) -> None:
    """Test the build command execution logic."""
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"test bytes"
    mock_is_dir.return_value = True
    mock_rglob.side_effect = [
        [Path.cwd() / "test1.py", Path.cwd() / "test2.py"],  # .py
        [],  # .rs
        [],  # .go
    ]

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"", b"")
    mock_create_subprocess_exec.return_value = mock_process

    import io

    # We need to simulate the file open for both reading and writing the JSON
    # For writing, mock the open context manager
    mock_file = io.StringIO(json.dumps({"test": "hash"}))
    mock_open.return_value.__enter__.return_value = mock_file

    with patch(
        "coreason_ecosystem.orchestration.build.Path.cwd", return_value=Path.cwd()
    ):
        result = runner.invoke(app, ["build", str(Path.cwd() / "dummy_dir")])
        assert result.exit_code == 0
        assert "Capability Crystallized" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.open")
@patch("coreason_ecosystem.orchestration.build.Path.mkdir")
@patch("coreason_ecosystem.orchestration.build.FileLock")
@patch("coreason_ecosystem.orchestration.build.Path.is_dir")
@patch("coreason_ecosystem.orchestration.build.Path.rglob")
def test_build_command_dir_no_files(
    mock_rglob: Any,
    mock_is_dir: Any,
    mock_filelock: Any,
    mock_mkdir: Any,
    mock_open: Any,
    mock_exists: Any,
) -> None:
    """Test the build command execution logic."""
    mock_exists.return_value = True
    mock_is_dir.return_value = True
    mock_rglob.return_value = []

    result = runner.invoke(app, ["build", "dummy_dir"])
    assert result.exit_code == 0
    assert "Warning" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.open")
@patch("coreason_ecosystem.orchestration.build.Path.mkdir")
@patch("coreason_ecosystem.orchestration.build.FileLock")
@patch("coreason_ecosystem.orchestration.build.Path.is_dir")
@patch("coreason_ecosystem.orchestration.build.Path.rglob")
@patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec")
def test_build_compiler_not_found(
    mock_create_subprocess_exec: Any,
    mock_rglob: Any,
    mock_is_dir: Any,
    mock_filelock: Any,
    mock_mkdir: Any,
    mock_open: Any,
    mock_exists: Any,
) -> None:
    """Test the build command when componentize-py is not found."""
    mock_exists.return_value = True
    mock_is_dir.return_value = False  # Target is a file
    mock_create_subprocess_exec.side_effect = FileNotFoundError

    import io

    # Mock open for ledger reading
    mock_open.return_value.__enter__.return_value = io.StringIO("{}")

    with patch(
        "coreason_ecosystem.orchestration.build.Path.cwd", return_value=Path.cwd()
    ):
        result = runner.invoke(app, ["build", str(Path.cwd() / "test.py")])

        assert result.exit_code == 1
        assert "Missing compiler for toolchain" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.open")
@patch("coreason_ecosystem.orchestration.build.Path.mkdir")
@patch("coreason_ecosystem.orchestration.build.FileLock")
@patch("coreason_ecosystem.orchestration.build.Path.is_dir")
def test_build_command_dir_no_cap_dir(
    mock_is_dir: Any,
    mock_filelock: Any,
    mock_mkdir: Any,
    mock_open: Any,
    mock_exists: Any,
) -> None:
    """Test the build command execution logic when capabilities dir does not exist."""
    mock_exists.side_effect = [True, False, False, False]
    mock_is_dir.return_value = True

    result = runner.invoke(app, ["build", "dummy_dir"])
    assert result.exit_code == 0
    assert "Warning" in result.stdout
