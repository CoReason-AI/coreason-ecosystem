# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from coreason_ecosystem.cli import app, main

runner = CliRunner()


def test_cli_main_entry() -> None:
    """Test the main entry point via CLI runner."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CoReason Meta-Orchestrator Control Plane" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.read_bytes")
@patch("coreason_ecosystem.orchestration.build.Path.open")
def test_build_command(mock_open, mock_read_bytes, mock_exists, tmp_path) -> None:
    """Test the build command execution logic."""
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"print('hello')"

    import io
    # We need to simulate the file open for both reading and writing the JSON
    # For writing, mock the open context manager
    mock_file = io.StringIO(json.dumps({"test": "hash"}))
    mock_open.return_value.__enter__.return_value = mock_file

    result = runner.invoke(app, ["build", "dummy_script.py"])
    assert result.exit_code == 0
    assert "Capability Crystallized" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.read_bytes")
@patch("coreason_ecosystem.orchestration.build.Path.open")
def test_build_command_no_json(mock_open, mock_read_bytes, mock_exists, tmp_path) -> None:
    """Test the build command execution logic when JSON is invalid."""
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"print('hello')"

    import io
    # Simulate invalid JSON
    mock_file = io.StringIO("invalid json")
    mock_open.return_value.__enter__.return_value = mock_file

    result = runner.invoke(app, ["build", "dummy_script.py"])
    assert result.exit_code == 0
    assert "Capability Crystallized" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
def test_build_command_file_not_found(mock_exists) -> None:
    """Test the build command when file doesn't exist."""
    mock_exists.return_value = False
    result = runner.invoke(app, ["build", "nonexistent.py"])
    assert result.exit_code == 0
    assert "Error:" in result.stdout
    assert "does not exist" in result.stdout


@patch("coreason_ecosystem.orchestration.up.asyncio.create_subprocess_exec")
@patch("coreason_ecosystem.orchestration.up.is_port_bound")
def test_up_command(mock_is_port_bound, mock_exec) -> None:
    """Test the up command execution logic."""
    mock_is_port_bound.side_effect = [False, False, False]

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_exec.return_value = mock_proc

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert mock_exec.call_count == 3  # postgres, temporal, daemon


@patch("coreason_ecosystem.orchestration.up.asyncio.create_subprocess_exec")
@patch("coreason_ecosystem.orchestration.up.is_port_bound")
def test_up_command_all_bound(mock_is_port_bound, mock_exec) -> None:
    """Test the up command execution logic when all bound."""
    mock_is_port_bound.side_effect = [True, True, True]

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert mock_exec.call_count == 0


@patch("coreason_ecosystem.orchestration.up.asyncio.wait_for")
def test_up_is_port_bound_true(mock_wait_for) -> None:
    """Test port bound check function."""
    import asyncio
    from coreason_ecosystem.orchestration.up import is_port_bound

    mock_reader = AsyncMock()
    mock_writer = AsyncMock()
    # Ensure wait_closed is an async mock so await works
    mock_writer.wait_closed = AsyncMock()
    mock_wait_for.return_value = (mock_reader, mock_writer)

    result = asyncio.run(is_port_bound(1234))
    assert result is True


@patch("coreason_ecosystem.orchestration.up.asyncio.wait_for")
def test_up_is_port_bound_false(mock_wait_for) -> None:
    """Test port bound check function on failure."""
    import asyncio
    from coreason_ecosystem.orchestration.up import is_port_bound

    mock_wait_for.side_effect = ConnectionRefusedError()

    result = asyncio.run(is_port_bound(1234))
    assert result is False


class MockResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.elapsed = type("obj", (object,), {"total_seconds": lambda self: 0.1})()


class MockStreamResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url, timeout=None):
        return MockResponse(200)

    def stream(self, method, url, timeout=None):
        return MockStreamResponse(200)


@patch("coreason_ecosystem.orchestration.doctor.httpx.AsyncClient", return_value=MockAsyncClient())
@patch("coreason_ecosystem.orchestration.doctor.Path.exists")
@patch("coreason_ecosystem.orchestration.doctor.Path.read_bytes")
def test_doctor_command(mock_read_bytes, mock_exists, mock_client) -> None:
    """Test the doctor command execution logic."""
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"{}"

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Ontological Isomorphism Diagnostic" in result.stdout


class MockAsyncClientErrorCodes:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url, timeout=None):
        return MockResponse(500)

    def stream(self, method, url, timeout=None):
        return MockStreamResponse(500)


@patch("coreason_ecosystem.orchestration.doctor.httpx.AsyncClient", return_value=MockAsyncClientErrorCodes())
@patch("coreason_ecosystem.orchestration.doctor.Path.exists")
@patch("coreason_ecosystem.orchestration.doctor.Path.read_bytes")
def test_doctor_command_error_codes(mock_read_bytes, mock_exists, mock_client) -> None:
    """Test the doctor command error logic."""
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"{}"

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Ontological Isomorphism Diagnostic" in result.stdout
    assert "ERROR 500" in result.stdout


class MockAsyncClientFail:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url, timeout=None):
        import httpx
        raise httpx.RequestError("Mocked failure")

    def stream(self, method, url, timeout=None):
        import httpx
        raise httpx.RequestError("Mocked stream failure")


@patch("coreason_ecosystem.orchestration.doctor.httpx.AsyncClient", return_value=MockAsyncClientFail())
@patch("coreason_ecosystem.orchestration.doctor.Path.exists")
def test_doctor_command_failures(mock_exists, mock_client) -> None:
    """Test the doctor command failure logic."""
    mock_exists.return_value = False

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Ontological Isomorphism Diagnostic" in result.stdout
    assert "OFFLINE" in result.stdout
    assert "MISSING" in result.stdout
