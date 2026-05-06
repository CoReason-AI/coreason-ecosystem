import importlib.metadata
from unittest.mock import patch, AsyncMock

import pytest
from typer.testing import CliRunner

from coreason_ecosystem.cli import app, version_callback

runner = CliRunner()

def test_version_callback_success():
    with patch("importlib.metadata.version", return_value="1.2.3"):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "CoReason Ecosystem" in result.stdout
        assert "v1.2.3" in result.stdout

def test_version_callback_fallback():
    with patch("importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "unknown (local development)" in result.stdout

def test_cli_callback():
    result = runner.invoke(app, ["--help"])
    # Shows help
    assert result.exit_code == 0

def test_init_command():
    with (
        patch("coreason_ecosystem.utils.telemetry.start_otlp_background_worker") as mock_start,
        patch("coreason_ecosystem.utils.telemetry.stop_otlp_background_worker", new_callable=AsyncMock) as mock_stop,
        patch("coreason_ecosystem.cli.execute_init", new_callable=AsyncMock) as mock_init
    ):
        result = runner.invoke(app, ["init", "test_project"])
        assert result.exit_code == 0
        mock_start.assert_called_once()
        mock_init.assert_awaited_once_with("test_project", "base", "python")
        mock_stop.assert_awaited_once()

def test_build_command():
    with (
        patch("coreason_ecosystem.utils.telemetry.start_otlp_background_worker") as mock_start,
        patch("coreason_ecosystem.utils.telemetry.stop_otlp_background_worker", new_callable=AsyncMock) as mock_stop,
        patch("coreason_ecosystem.cli.execute_build", new_callable=AsyncMock) as mock_build
    ):
        result = runner.invoke(app, ["build", "target_path"])
        assert result.exit_code == 0
        mock_start.assert_called_once()
        mock_build.assert_awaited_once_with("target_path")
        mock_stop.assert_awaited_once()

def test_up_command():
    with (
        patch("coreason_ecosystem.utils.telemetry.start_otlp_background_worker") as mock_start,
        patch("coreason_ecosystem.utils.telemetry.stop_otlp_background_worker", new_callable=AsyncMock) as mock_stop,
        patch("coreason_ecosystem.cli.execute_up", new_callable=AsyncMock) as mock_up
    ):
        result = runner.invoke(app, ["up"])
        assert result.exit_code == 0
        mock_start.assert_called_once()
        mock_up.assert_awaited_once()
        mock_stop.assert_awaited_once()

def test_doctor_command():
    with (
        patch("coreason_ecosystem.utils.telemetry.start_otlp_background_worker") as mock_start,
        patch("coreason_ecosystem.utils.telemetry.stop_otlp_background_worker", new_callable=AsyncMock) as mock_stop,
        patch("coreason_ecosystem.cli.execute_oracle_diagnostic", new_callable=AsyncMock) as mock_doc
    ):
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        mock_start.assert_called_once()
        mock_doc.assert_awaited_once()
        mock_stop.assert_awaited_once()

def test_sync_command():
    with (
        patch("coreason_ecosystem.utils.telemetry.start_otlp_background_worker") as mock_start,
        patch("coreason_ecosystem.utils.telemetry.stop_otlp_background_worker", new_callable=AsyncMock) as mock_stop,
        patch("coreason_ecosystem.cli.execute_sync", new_callable=AsyncMock) as mock_sync
    ):
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0
        mock_start.assert_called_once()
        mock_sync.assert_awaited_once()
        mock_stop.assert_awaited_once()

def test_docs_build_success():
    with patch("coreason_ecosystem.docs_generator.generate_dynamic_docs") as mock_gen:
        result = runner.invoke(app, ["docs", "build"])
        assert result.exit_code == 0
        mock_gen.assert_called_once()

def test_docs_build_failure():
    with patch("coreason_ecosystem.docs_generator.generate_dynamic_docs", side_effect=Exception("mocked error")):
        result = runner.invoke(app, ["docs", "build"])
        # Should catch Exception and print, but still exit 0 unless we specifically raise typer.Exit
        assert result.exit_code == 0
        assert "Documentation Pipeline Failed" in result.stdout
