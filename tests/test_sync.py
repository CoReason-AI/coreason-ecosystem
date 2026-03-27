# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from coreason_ecosystem.cli import app

runner = CliRunner()

@patch("coreason_ecosystem.orchestration.sync.Path.exists")
@patch("coreason_ecosystem.orchestration.sync.subprocess.run")
@patch("coreason_ecosystem.orchestration.sync.write_registry_lock")
@patch("coreason_ecosystem.orchestration.sync.calculate_epistemic_root", new_callable=AsyncMock)
@patch("coreason_ecosystem.orchestration.sync.execute_build", new_callable=AsyncMock)
@patch("coreason_ecosystem.orchestration.sync.Path.open")
def test_sync_command(mock_open: Any, mock_execute_build: Any, mock_calc_root: Any, mock_write_lock: Any, mock_sub_run: Any, mock_exists: Any) -> None:
    """Test the sync command execution logic."""
    import io
    mock_file = io.StringIO()
    mock_open.return_value.__enter__.return_value = mock_file
    mock_calc_root.return_value = "deadbeef"
    mock_exists.return_value = True

    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "Autopoietic Healing Complete" in result.stdout
    mock_execute_build.assert_called_once()
    mock_calc_root.assert_called_once()
    mock_write_lock.assert_called_once()
    mock_sub_run.assert_called_once()

@patch("coreason_ecosystem.orchestration.sync.Path.exists")
@patch("coreason_ecosystem.orchestration.sync.subprocess.run")
@patch("coreason_ecosystem.orchestration.sync.write_registry_lock")
@patch("coreason_ecosystem.orchestration.sync.calculate_epistemic_root", new_callable=AsyncMock)
@patch("coreason_ecosystem.orchestration.sync.execute_build", new_callable=AsyncMock)
@patch("coreason_ecosystem.orchestration.sync.Path.open")
def test_sync_command_compose_fallback(mock_open: Any, mock_execute_build: Any, mock_calc_root: Any, mock_write_lock: Any, mock_sub_run: Any, mock_exists: Any) -> None:
    """Test the sync command execution logic."""
    import io
    mock_file = io.StringIO()
    mock_open.return_value.__enter__.return_value = mock_file
    mock_calc_root.return_value = "deadbeef"
    mock_exists.return_value = False

    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "Autopoietic Healing Complete" in result.stdout
    mock_sub_run.assert_called_once()
