# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

from typing import Any
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from coreason_ecosystem.cli import app

runner = CliRunner()


@patch("coreason_ecosystem.orchestration.sync.execute_build", new_callable=AsyncMock)
@patch("coreason_ecosystem.orchestration.sync.Path.exists")
@patch(
    "coreason_ecosystem.orchestration.sync.asyncio.create_subprocess_exec",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.sync.write_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.sync.calculate_epistemic_root",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.sync.Path.open")
def test_sync_command(
    mock_open: Any,
    mock_calc_root: Any,
    mock_write_lock: Any,
    mock_sub_exec: Any,
    mock_exists: Any,
    mock_execute_build: Any,
) -> None:
    """Test the sync command execution logic."""
    import io

    mock_file = io.StringIO()
    mock_open.return_value.__enter__.return_value = mock_file
    mock_calc_root.return_value = "deadbeef"
    mock_exists.return_value = True

    # Mock the returned process
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"", b"")
    mock_sub_exec.return_value = mock_process

    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "Autopoietic Healing Complete" in result.stdout
    mock_execute_build.assert_called_once()
    mock_calc_root.assert_called_once()
    mock_write_lock.assert_called_once()
    mock_sub_exec.assert_called_once()
    mock_process.communicate.assert_called_once()


@patch("coreason_ecosystem.orchestration.sync.execute_build", new_callable=AsyncMock)
@patch("coreason_ecosystem.orchestration.sync.Path.exists")
@patch(
    "coreason_ecosystem.orchestration.sync.asyncio.create_subprocess_exec",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.sync.write_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.sync.calculate_epistemic_root",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.sync.Path.open")
def test_sync_command_compose_fallback(
    mock_open: Any,
    mock_calc_root: Any,
    mock_write_lock: Any,
    mock_sub_exec: Any,
    mock_exists: Any,
    mock_execute_build: Any,
) -> None:
    """Test the sync command execution logic."""
    import io

    mock_file = io.StringIO()
    mock_open.return_value.__enter__.return_value = mock_file
    mock_calc_root.return_value = "deadbeef"
    mock_exists.side_effect = [False, True]

    # Mock the returned process
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"", b"")
    mock_sub_exec.return_value = mock_process

    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "Autopoietic Healing Complete" in result.stdout
    mock_execute_build.assert_called_once()
    mock_sub_exec.assert_called_once()
    mock_process.communicate.assert_called_once()
