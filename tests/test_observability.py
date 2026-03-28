import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from coreason_ecosystem.utils.logger import (
    InterceptHandler,
    _patch_record,
    _redaction_filter,
    bind_epistemic_context,
)
from coreason_ecosystem.utils.telemetry import (
    TelemetryModel,
    _otlp_worker,
    otlp_log_sink,
    setup_telemetry_mesh,
)


def test_bind_epistemic_context() -> None:
    with bind_epistemic_context("workflow_1", "root_1"):
        import coreason_ecosystem.utils.logger as logger_module

        assert logger_module.epistemic_root.get() == "root_1"
        assert logger_module.workflow_id.get() == "workflow_1"


def test_intercept_handler() -> None:
    handler = InterceptHandler()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    with patch("loguru.logger.opt") as mock_opt:
        mock_log = mock_opt.return_value.log
        handler.emit(record)
        mock_opt.assert_called()
        mock_log.assert_called_with(record.levelname, record.getMessage())

    record_invalid_level = logging.LogRecord(
        name="test",
        level=999,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    with patch("loguru.logger.opt") as mock_opt:
        mock_log = mock_opt.return_value.log
        handler.emit(record_invalid_level)
        mock_opt.assert_called()
        mock_log.assert_called_with(999, record_invalid_level.getMessage())


def test_patch_record() -> None:
    record: dict[str, Any] = {"extra": {}}
    with bind_epistemic_context("test_workflow", "test_root"):
        _patch_record(record)  # type: ignore
    assert record["extra"]["workflow_id"] == "test_workflow"
    assert record["extra"]["epistemic_root"] == "test_root"


@patch("os.getenv")
def test_redaction_filter_dev(mock_getenv: AsyncMock) -> None:
    mock_getenv.return_value = "development"
    record: dict[str, str] = {"message": "Test message with email@example.com and 123-45-6789"}
    assert _redaction_filter(record) is True  # type: ignore
    assert "email@example.com" in record["message"]
    assert "123-45-6789" in record["message"]


@patch("os.getenv")
def test_redaction_filter_prod(mock_getenv: AsyncMock) -> None:
    mock_getenv.return_value = "production"
    record: dict[str, str] = {"message": "Test message with email@example.com and 123-45-6789"}
    assert _redaction_filter(record) is True  # type: ignore
    assert "<REDACTED_EMAIL>" in record["message"]
    assert "<REDACTED_SSN>" in record["message"]


@pytest.mark.asyncio
async def test_otlp_worker() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    queue.put_nowait(
        {
            "level": {"name": "INFO"},
            "message": "test",
            "extra": {"key": "value"},
        }
    )

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", queue),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        worker_task = asyncio.create_task(_otlp_worker("http://test"))
        await asyncio.sleep(0.1)
        worker_task.cancel()
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_otlp_worker_exception() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    queue.put_nowait(
        {
            "level": {"name": "INFO"},
            "message": "test",
            "extra": {"key": "value"},
        }
    )

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", queue),
        patch("httpx.AsyncClient.post", side_effect=Exception("error")) as mock_post,
    ):
        worker_task = asyncio.create_task(_otlp_worker("http://test"))
        await asyncio.sleep(0.1)
        worker_task.cancel()
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_otlp_worker_request_error() -> None:
    import httpx

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    queue.put_nowait(
        {
            "level": {"name": "INFO"},
            "message": "test",
            "extra": {"key": "value"},
        }
    )

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", queue),
        patch(
            "httpx.AsyncClient.post", side_effect=httpx.RequestError("error")
        ) as mock_post,
    ):
        worker_task = asyncio.create_task(_otlp_worker("http://test"))
        await asyncio.sleep(0.1)
        worker_task.cancel()
        mock_post.assert_called_once()


def test_otlp_log_sink() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    class MockMessage:
        record = {"test": "data"}

    with patch("coreason_ecosystem.utils.telemetry._otlp_queue", queue):
        otlp_log_sink(MockMessage())  # type: ignore
    assert queue.get_nowait() == {"test": "data"}


def test_otlp_log_sink_full() -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)
    queue.put_nowait({"fill": "queue"})

    class MockMessage:
        record = {"test": "data"}

    with patch("coreason_ecosystem.utils.telemetry._otlp_queue", queue):
        otlp_log_sink(MockMessage())  # type: ignore
    # Assert queue is still just full with initial element
    assert queue.get_nowait() == {"fill": "queue"}
    assert queue.empty()


def test_telemetry_model_success() -> None:
    class TestModel(TelemetryModel):
        name: str

    with patch("opentelemetry.trace.get_tracer") as mock_get_tracer:
        model = TestModel.validate_with_telemetry({"name": "test"})
        assert isinstance(model, TestModel)
        assert model.name == "test"
        assert mock_get_tracer.return_value.start_as_current_span.call_count == 2 # Called in both validate_with_telemetry and _telemetry_validation_hook

    # Test direct init to trigger `_telemetry_validation_hook`
    with patch("opentelemetry.trace.get_tracer") as mock_get_tracer:
        model = TestModel(name="test2")
        assert getattr(model, "name", None) == "test2"
        mock_get_tracer.return_value.start_as_current_span.assert_called_once()


@patch.dict("os.environ", {"COREASON_ENABLE_DIAGNOSTICS": "1"})
def test_telemetry_model_failure_diagnostics() -> None:
    class TestModel(TelemetryModel):
        name: str

    with pytest.raises(ValidationError), patch("opentelemetry.trace.get_tracer"):
        TestModel.validate_with_telemetry({"name": 123})


@patch.dict("os.environ", {"COREASON_ENABLE_DIAGNOSTICS": "0"})
def test_telemetry_model_failure_no_diagnostics() -> None:
    class TestModel(TelemetryModel):
        name: str

    with pytest.raises(ValidationError), patch("opentelemetry.trace.get_tracer"):
        TestModel.validate_with_telemetry({"name": 123})


@patch("asyncio.get_running_loop")
def test_setup_telemetry_mesh(mock_get_running_loop: AsyncMock) -> None:
    mock_loop = AsyncMock()
    mock_get_running_loop.return_value = mock_loop
    setup_telemetry_mesh()
    mock_loop.create_task.assert_called_once()


@patch("asyncio.get_running_loop", side_effect=RuntimeError)
def test_setup_telemetry_mesh_no_loop(mock_get_running_loop: AsyncMock) -> None:
    setup_telemetry_mesh()

def test_logger_patch_record_none() -> None:
    record: dict[str, Any] = {"extra": {}}
    # Do not bind context to test the path where variables are not set
    _patch_record(record) # type: ignore
    assert "workflow_id" not in record["extra"]
    assert "epistemic_root" not in record["extra"]
