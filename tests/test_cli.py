# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import asyncio
import json
import runpy
from typing import Any
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from coreason_ecosystem.cli import app

runner = CliRunner()


def test_cli_main_entry() -> None:
    """Test the main entry point via CLI runner."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CoReason Meta-Orchestrator Control Plane" in result.stdout


def test_main_module_execution() -> None:
    """Test that the __main__ module starts the CLI application."""
    with patch("coreason_ecosystem.cli.app") as mock_app:
        runpy.run_module("coreason_ecosystem.__main__", run_name="__main__")
        mock_app.assert_called_once_with(prog_name="coreason")


@patch("coreason_ecosystem.cli.execute_init")
def test_init_command(mock_execute_init: Any) -> None:
    """Test the init command execution logic."""
    mock_execute_init.return_value = None
    result = runner.invoke(app, ["init", "my_new_swarm", "--topology", "medallion"])
    assert result.exit_code == 0
    assert "Workspace 'my_new_swarm' mathematically sealed and ready." in result.stdout
    mock_execute_init.assert_called_once_with("my_new_swarm", "medallion")


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.read_bytes")
@patch("coreason_ecosystem.orchestration.build.Path.open")
@patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec")
def test_build_command(
    mock_create_subprocess_exec: Any, mock_open: Any, mock_read_bytes: Any, mock_exists: Any
) -> None:
    """Test the build command execution logic."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")
    mock_create_subprocess_exec.return_value = mock_proc
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
@patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec")
def test_build_command_no_json(
    mock_create_subprocess_exec: Any, mock_open: Any, mock_read_bytes: Any, mock_exists: Any
) -> None:
    """Test the build command execution logic when JSON is invalid."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")
    mock_create_subprocess_exec.return_value = mock_proc
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
def test_build_command_file_not_found(mock_exists: Any) -> None:
    """Test the build command when file doesn't exist."""
    mock_exists.return_value = False
    result = runner.invoke(app, ["build", "nonexistent.py"])
    assert result.exit_code == 0
    assert "Error:" in result.stdout
    assert "does not exist" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.open")
@patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec")
def test_build_command_compiler_not_found(
    mock_create_subprocess_exec: Any, mock_open: Any, mock_exists: Any
) -> None:
    """Test the build command when componentize-py is not installed."""
    mock_exists.return_value = True
    mock_create_subprocess_exec.side_effect = FileNotFoundError()

    import io

    mock_open.return_value.__enter__.return_value = io.StringIO("{}")

    result = runner.invoke(app, ["build", "dummy_script.py"])
    assert result.exit_code == 1
    assert "Fatal Error: 'componentize-py' compiler not found" in result.stdout


@patch("coreason_ecosystem.orchestration.build.Path.exists")
@patch("coreason_ecosystem.orchestration.build.Path.open")
@patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec")
def test_build_command_compile_error(
    mock_create_subprocess_exec: Any, mock_open: Any, mock_exists: Any
) -> None:
    """Test the build command when compilation fails."""
    mock_exists.return_value = True
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"syntax error")
    mock_create_subprocess_exec.return_value = mock_proc

    import io

    mock_open.return_value.__enter__.return_value = io.StringIO("{}")

    result = runner.invoke(app, ["build", "dummy_script.py"])
    assert result.exit_code == 1
    assert "Error compiling" in result.stdout
    assert "syntax error" in result.stdout


@patch(
    "coreason_ecosystem.orchestration.up.calculate_epistemic_root",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.up.write_registry_lock")
@patch("coreason_ecosystem.orchestration.up.Path.exists")
@patch("coreason_ecosystem.orchestration.up.asyncio.create_subprocess_exec")
@patch("coreason_ecosystem.orchestration.up.is_port_bound")
def test_up_command(
    mock_is_port_bound: Any,
    mock_exec: Any,
    mock_exists: Any,
    mock_write_lock: Any,
    mock_calc_root: Any,
) -> None:
    """Test the up command execution logic."""
    mock_calc_root.return_value = "deadbeef"
    mock_exists.return_value = False
    mock_is_port_bound.side_effect = [False, False, False, False]

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_exec.return_value = mock_proc

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert (
        mock_exec.call_count == 4
    )  # postgres, temporal, coreason-runtime, observability


@patch(
    "coreason_ecosystem.orchestration.up.calculate_epistemic_root",
    new_callable=AsyncMock,
)
@patch("coreason_ecosystem.orchestration.up.write_registry_lock")
@patch("coreason_ecosystem.orchestration.up.asyncio.create_subprocess_exec")
@patch("coreason_ecosystem.orchestration.up.is_port_bound")
def test_up_command_all_bound(
    mock_is_port_bound: Any, mock_exec: Any, mock_write_lock: Any, mock_calc_root: Any
) -> None:
    """Test the up command execution logic when all bound."""
    mock_calc_root.return_value = "deadbeef"
    mock_is_port_bound.side_effect = [True, True, True, True]

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert mock_exec.call_count == 0


@patch("coreason_ecosystem.orchestration.up.asyncio.wait_for")
def test_up_is_port_bound_true(mock_wait_for: Any) -> None:
    """Test port bound check function."""
    from coreason_ecosystem.orchestration.up import is_port_bound

    mock_reader = AsyncMock()
    mock_writer = AsyncMock()
    # Ensure wait_closed is an async mock so await works
    mock_writer.wait_closed = AsyncMock()
    mock_wait_for.return_value = (mock_reader, mock_writer)

    result = asyncio.run(is_port_bound(1234))
    assert result is True


@patch("coreason_ecosystem.orchestration.up.asyncio.wait_for")
def test_up_is_port_bound_false(mock_wait_for: Any) -> None:
    """Test port bound check function on failure."""
    from coreason_ecosystem.orchestration.up import is_port_bound

    mock_wait_for.side_effect = ConnectionRefusedError()

    result = asyncio.run(is_port_bound(1234))
    assert result is False


class MockResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.elapsed = type("obj", (object,), {"total_seconds": lambda _self: 0.1})()


class MockStreamResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    async def __aenter__(self) -> "MockStreamResponse":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


class MockAsyncClient:
    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def get(
        self, _url: str, timeout: float | None = None, headers: Any = None
    ) -> MockResponse:
        return MockResponse(200)

    def stream(
        self, _method: str, _url: str, timeout: float | None = None
    ) -> MockStreamResponse:
        return MockStreamResponse(200)


@patch("coreason_ecosystem.orchestration.doctor.read_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.doctor.httpx.AsyncClient",
    return_value=MockAsyncClient(),
)
@patch("coreason_ecosystem.orchestration.doctor.Path.exists")
@patch("coreason_ecosystem.orchestration.doctor.Path.read_bytes")
def test_doctor_command(
    mock_read_bytes: Any,
    mock_exists: Any,
    mock_client: Any,
    mock_read_registry_lock: Any,
) -> None:
    """Test the doctor command execution logic."""
    _ = mock_client
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"{}"
    mock_read_registry_lock.return_value = "deadbeefdeadbeefdeadbeef"

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Ontological Isomorphism Diagnostic" in result.stdout


class MockAsyncClientErrorCodes:
    async def __aenter__(self) -> "MockAsyncClientErrorCodes":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def get(
        self, _url: str, timeout: float | None = None, headers: Any = None
    ) -> MockResponse:
        return MockResponse(500)

    def stream(
        self, _method: str, _url: str, timeout: float | None = None
    ) -> MockStreamResponse:
        return MockStreamResponse(500)


@patch("coreason_ecosystem.orchestration.doctor.read_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.doctor.httpx.AsyncClient",
    return_value=MockAsyncClientErrorCodes(),
)
@patch("coreason_ecosystem.orchestration.doctor.Path.exists")
@patch("coreason_ecosystem.orchestration.doctor.Path.read_bytes")
def test_doctor_command_error_codes(
    mock_read_bytes: Any,
    mock_exists: Any,
    mock_client: Any,
    mock_read_registry_lock: Any,
) -> None:
    """Test the doctor command error logic."""
    _ = mock_client
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"{}"
    mock_read_registry_lock.return_value = None

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Ontological Isomorphism Diagnostic" in result.stdout
    assert "ERROR 500" in result.stdout


class MockAsyncClientFail:
    async def __aenter__(self) -> "MockAsyncClientFail":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def get(
        self, _url: str, timeout: float | None = None, headers: Any = None
    ) -> MockResponse:
        import httpx

        raise httpx.RequestError("Mocked failure")

    def stream(
        self, _method: str, _url: str, timeout: float | None = None
    ) -> MockStreamResponse:
        import httpx

        raise httpx.RequestError("Mocked stream failure")


@patch("coreason_ecosystem.orchestration.doctor.read_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.doctor.httpx.AsyncClient",
    return_value=MockAsyncClientFail(),
)
@patch("coreason_ecosystem.orchestration.doctor.Path.exists")
def test_doctor_command_failures(
    mock_exists: Any, mock_client: Any, mock_read_registry_lock: Any
) -> None:
    """Test the doctor command failure logic."""
    _ = mock_client
    mock_exists.return_value = False
    mock_read_registry_lock.return_value = "deadbeef"

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Ontological Isomorphism Diagnostic" in result.stdout
    assert "OFFLINE" in result.stdout
    assert "MISSING" in result.stdout


class MockAsyncClientHTTP:
    async def __aenter__(self) -> "MockAsyncClientHTTP":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def get(
        self, _url: str, timeout: float | None = None, headers: Any = None
    ) -> MockResponse:
        return MockResponse(404)

    def stream(
        self, _method: str, _url: str, timeout: float | None = None
    ) -> MockStreamResponse:
        return MockStreamResponse(404)


@patch("coreason_ecosystem.orchestration.doctor.read_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.doctor.httpx.AsyncClient",
    return_value=MockAsyncClientHTTP(),
)
@patch("coreason_ecosystem.orchestration.doctor.Path.exists")
@patch("coreason_ecosystem.orchestration.doctor.Path.read_bytes")
def test_doctor_command_http_error(
    mock_read_bytes: Any,
    mock_exists: Any,
    mock_client: Any,
    mock_read_registry_lock: Any,
) -> None:
    _ = mock_client
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"{}"
    mock_read_registry_lock.return_value = "deadbeef"

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "⚠ HTTP 404" in result.stdout


class MockAsyncClientHTTP409:
    async def __aenter__(self) -> "MockAsyncClientHTTP409":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def get(
        self, _url: str, timeout: float | None = None, headers: Any = None
    ) -> MockResponse:
        return MockResponse(409)

    def stream(
        self, _method: str, _url: str, timeout: float | None = None
    ) -> MockStreamResponse:
        return MockStreamResponse(409)


@patch("coreason_ecosystem.orchestration.doctor.read_registry_lock")
@patch(
    "coreason_ecosystem.orchestration.doctor.httpx.AsyncClient",
    return_value=MockAsyncClientHTTP409(),
)
@patch("coreason_ecosystem.orchestration.doctor.Path.exists")
@patch("coreason_ecosystem.orchestration.doctor.Path.read_bytes")
def test_doctor_command_http_error_409(
    mock_read_bytes: Any,
    mock_exists: Any,
    mock_client: Any,
    mock_read_registry_lock: Any,
) -> None:
    _ = mock_client
    mock_exists.return_value = True
    mock_read_bytes.return_value = b"{}"
    mock_read_registry_lock.return_value = "deadbeef"

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "DRIFT DETECTED" in result.stdout
