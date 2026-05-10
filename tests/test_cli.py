from typing import Any
import pytest
from typer.testing import CliRunner
import importlib.metadata
from unittest.mock import patch, AsyncMock

from coreason_ecosystem.cli import app, version_callback
import typer

runner = CliRunner()


def test_version_callback_true() -> None:
    with patch("importlib.metadata.version", return_value="1.0.0"):
        with pytest.raises(typer.Exit):
            version_callback(True)


def test_version_callback_package_not_found() -> None:
    with patch(
        "importlib.metadata.version",
        side_effect=importlib.metadata.PackageNotFoundError,
    ):
        with pytest.raises(typer.Exit):
            version_callback(True)


def test_version_callback_false() -> None:
    # Should do nothing
    version_callback(False)


@patch("coreason_ecosystem.cli.execute_up", new_callable=AsyncMock)
@patch("coreason_ecosystem.utils.telemetry.start_otlp_background_worker")
@patch(
    "coreason_ecosystem.utils.telemetry.stop_otlp_background_worker",
    new_callable=AsyncMock,
)
def test_cli_up(mock_stop: Any, mock_start: Any, mock_execute_up: Any) -> None:
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    mock_start.assert_called_once()
    mock_execute_up.assert_called_once()
    mock_stop.assert_called_once()


@patch("coreason_ecosystem.cli.execute_oracle_diagnostic", new_callable=AsyncMock)
@patch("coreason_ecosystem.utils.telemetry.start_otlp_background_worker")
@patch(
    "coreason_ecosystem.utils.telemetry.stop_otlp_background_worker",
    new_callable=AsyncMock,
)
def test_cli_doctor(mock_stop: Any, mock_start: Any, mock_execute_oracle: Any) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    mock_start.assert_called_once()
    mock_execute_oracle.assert_called_once()
    mock_stop.assert_called_once()


@patch("coreason_ecosystem.cli.execute_sync", new_callable=AsyncMock)
@patch("coreason_ecosystem.utils.telemetry.start_otlp_background_worker")
@patch(
    "coreason_ecosystem.utils.telemetry.stop_otlp_background_worker",
    new_callable=AsyncMock,
)
def test_cli_sync(mock_stop: Any, mock_start: Any, mock_execute_sync: Any) -> None:
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    mock_start.assert_called_once()
    mock_execute_sync.assert_called_once()
    mock_stop.assert_called_once()


@patch("coreason_ecosystem.docs_generator.generate_dynamic_docs")
def test_cli_build_docs(mock_generate: Any) -> None:
    result = runner.invoke(app, ["docs", "build"])
    assert result.exit_code == 0
    mock_generate.assert_called_once()


@patch(
    "coreason_ecosystem.docs_generator.generate_dynamic_docs",
    side_effect=Exception("Docs failed"),
)
def test_cli_build_docs_failure(mock_generate: Any) -> None:
    result = runner.invoke(app, ["docs", "build"])
    assert (
        result.exit_code == 0
    )  # It catches the exception and prints it, does not exit with code 1
    mock_generate.assert_called_once()
