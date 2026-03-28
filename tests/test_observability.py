import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from coreason_ecosystem.utils.logger import (
    InterceptHandler,
    _patch_record,
    bind_epistemic_context,
)
from coreason_ecosystem.utils.telemetry import (
    TelemetryModel,
    _otlp_worker,
    otlp_log_sink,
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


@patch.dict("os.environ", {"ENV": "development"})
def test_redaction_filter_dev() -> None:
    record: dict[str, Any] = {
        "message": "Test message with email@example.com and 123-45-6789",
        "extra": {},
    }
    with bind_epistemic_context("", ""):
        _patch_record(record)  # type: ignore
    assert "email@example.com" in record["message"]
    assert "123-45-6789" in record["message"]


@patch("coreason_ecosystem.utils.logger._IS_PRODUCTION", True)
def test_redaction_filter_prod() -> None:
    record: dict[str, Any] = {
        "message": "Test message with email@example.com and 123-45-6789",
        "extra": {},
    }
    with bind_epistemic_context("", ""):
        _patch_record(record)  # type: ignore
    assert "<REDACTED_EMAIL>" in record["message"]
    assert "<REDACTED_SSN>" in record["message"]


@pytest.mark.asyncio
async def test_otlp_worker() -> None:
    import queue
    from datetime import datetime

    q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
    q.put_nowait(
        {
            "level": {"name": "INFO"},
            "message": "test",
            "extra": {"key": "value"},
            "time": datetime.now(),
        }
    )

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", q),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        worker_task = asyncio.create_task(_otlp_worker("http://test"))
        await asyncio.sleep(0.1)
        worker_task.cancel()
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_otlp_worker_exception() -> None:
    import queue
    from datetime import datetime

    q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
    q.put_nowait(
        {
            "level": {"name": "INFO"},
            "message": "test",
            "extra": {"key": "value"},
            "time": datetime.now(),
        }
    )

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", q),
        patch("httpx.AsyncClient.post", side_effect=Exception("error")) as mock_post,
    ):
        worker_task = asyncio.create_task(_otlp_worker("http://test"))
        await asyncio.sleep(0.1)
        worker_task.cancel()
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_otlp_worker_request_error() -> None:
    import httpx
    import queue
    from datetime import datetime

    q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
    q.put_nowait(
        {
            "level": {"name": "INFO"},
            "message": "test",
            "extra": {"key": "value"},
            "time": datetime.now(),
        }
    )

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", q),
        patch(
            "httpx.AsyncClient.post", side_effect=httpx.RequestError("error")
        ) as mock_post,
    ):
        worker_task = asyncio.create_task(_otlp_worker("http://test"))
        await asyncio.sleep(0.1)
        worker_task.cancel()
        mock_post.assert_called_once()


def test_otlp_log_sink() -> None:
    import queue

    q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()

    class MockMessage:
        record = {"test": "data"}

    with patch("coreason_ecosystem.utils.telemetry._otlp_queue", q):
        otlp_log_sink(MockMessage())  # type: ignore

    assert q.get_nowait() == {"test": "data"}


def test_otlp_log_sink_exception() -> None:
    import queue

    q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()

    class MockMessage:
        @property
        def record(self) -> Any:
            raise Exception("error")

    with patch("coreason_ecosystem.utils.telemetry._otlp_queue", q):
        otlp_log_sink(MockMessage())  # type: ignore

    assert q.empty()


def test_telemetry_model_success() -> None:
    class TestModel(TelemetryModel):
        name: str

    with patch("opentelemetry.trace.get_tracer") as mock_get_tracer:
        model = TestModel.validate_with_telemetry({"name": "test"})
        assert isinstance(model, TestModel)
        assert model.name == "test"
        assert (
            mock_get_tracer.return_value.start_as_current_span.call_count == 1
        )  # Called in validate_with_telemetry


@pytest.mark.asyncio
async def test_stop_otlp_background_worker() -> None:
    import queue

    q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
    loop = asyncio.get_running_loop()

    async def mock_coro() -> None:
        pass

    mock_task = loop.create_task(mock_coro())

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", q),
        patch("coreason_ecosystem.utils.telemetry._otlp_task", mock_task),
    ):
        from coreason_ecosystem.utils.telemetry import stop_otlp_background_worker

        await stop_otlp_background_worker()
        assert mock_task.cancelled()


@pytest.mark.asyncio
async def test_stop_otlp_background_worker_cancelled() -> None:
    import queue

    q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
    loop = asyncio.get_running_loop()

    async def mock_coro() -> None:
        await asyncio.sleep(1)

    mock_task = loop.create_task(mock_coro())
    mock_task.cancel()

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", q),
        patch("coreason_ecosystem.utils.telemetry._otlp_task", mock_task),
    ):
        from coreason_ecosystem.utils.telemetry import stop_otlp_background_worker

        # It shouldn't raise CancelledError because we catch it in stop_otlp_background_worker
        await stop_otlp_background_worker()


@pytest.mark.asyncio
async def test_stop_otlp_background_worker_timeout() -> None:
    import queue

    q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
    q.put_nowait({"level": {"name": "INFO"}, "message": "test", "extra": {}})
    loop = asyncio.get_running_loop()

    async def mock_coro() -> None:
        await asyncio.sleep(1)

    mock_task = loop.create_task(mock_coro())

    with (
        patch("coreason_ecosystem.utils.telemetry._otlp_queue", q),
        patch("coreason_ecosystem.utils.telemetry._otlp_task", mock_task),
        patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
    ):
        from coreason_ecosystem.utils.telemetry import stop_otlp_background_worker

        # It shouldn't raise TimeoutError because we catch it in stop_otlp_background_worker
        await stop_otlp_background_worker()
        assert mock_task.cancelled()


@patch("coreason_ecosystem.utils.telemetry.get_observability_settings")
def test_telemetry_model_failure_diagnostics(mock_get_settings: Any) -> None:
    mock_get_settings.return_value.enable_diagnostics = True
    class TestModel(TelemetryModel):
        name: str

    with pytest.raises(ValidationError), patch("opentelemetry.trace.get_tracer"):
        TestModel.validate_with_telemetry({"name": 123})


@patch("coreason_ecosystem.utils.telemetry.get_observability_settings")
def test_telemetry_model_failure_no_diagnostics(mock_get_settings: Any) -> None:
    mock_get_settings.return_value.enable_diagnostics = False
    class TestModel(TelemetryModel):
        name: str

    with pytest.raises(ValidationError), patch("opentelemetry.trace.get_tracer"):
        TestModel.validate_with_telemetry({"name": 123})


@patch("asyncio.get_running_loop")
def test_start_otlp_background_worker(mock_get_running_loop: Any) -> None:
    from unittest.mock import MagicMock

    mock_loop = MagicMock()
    mock_get_running_loop.return_value = mock_loop

    # We must patch _otlp_worker to prevent it from returning an unawaited coroutine in the test
    with patch(
        "coreason_ecosystem.utils.telemetry._otlp_worker",
        new=MagicMock(return_value="dummy_coro"),
    ):
        from coreason_ecosystem.utils.telemetry import start_otlp_background_worker

        start_otlp_background_worker()
        mock_loop.create_task.assert_called_once_with("dummy_coro")


@patch("asyncio.get_running_loop", side_effect=RuntimeError)
def test_start_otlp_background_worker_no_loop(mock_get_running_loop: Any) -> None:
    from coreason_ecosystem.utils.telemetry import start_otlp_background_worker

    start_otlp_background_worker()


def test_logger_patch_record_none() -> None:
    record: dict[str, Any] = {"message": "Test message", "extra": {}}
    # Do not bind context to test the path where variables are not set
    _patch_record(record)  # type: ignore
    assert "workflow_id" not in record["extra"]
    assert "epistemic_root" not in record["extra"]
