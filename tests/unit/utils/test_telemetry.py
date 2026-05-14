# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import logging
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from coreason_ecosystem.utils.logger import (
    InterceptHandler,
    _patch_record,
    bind_epistemic_context,
)
from coreason_ecosystem.utils.telemetry import TelemetryModel


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
        _patch_record(record)  # type: ignore[arg-type]
    assert record["extra"]["workflow_id"] == "test_workflow"
    assert record["extra"]["epistemic_root"] == "test_root"


@patch.dict("os.environ", {"ENV": "development"})
def test_redaction_filter_dev() -> None:
    record: dict[str, Any] = {
        "message": "Test message with email@example.com and 123-45-6789",
        "extra": {},
    }
    with bind_epistemic_context("", ""):
        _patch_record(record)  # type: ignore[arg-type]
    assert "email@example.com" in record["message"]
    assert "123-45-6789" in record["message"]


@patch("coreason_ecosystem.utils.logger._IS_PRODUCTION", True)
def test_redaction_filter_prod() -> None:
    record: dict[str, Any] = {
        "message": "Test message with email@example.com and 123-45-6789",
        "extra": {},
    }
    with bind_epistemic_context("", ""):
        _patch_record(record)  # type: ignore[arg-type]
    assert "<REDACTED_EMAIL>" in record["message"]
    assert "<REDACTED_SSN>" in record["message"]












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






def test_logger_patch_record_none() -> None:
    record: dict[str, Any] = {"message": "Test message", "extra": {}}
    # Do not bind context to test the path where variables are not set
    _patch_record(record)  # type: ignore[arg-type]
    assert "workflow_id" not in record["extra"]
    assert "epistemic_root" not in record["extra"]


def test_emit_span_event() -> None:
    from coreason_ecosystem.utils.telemetry import emit_span_event

    with patch("opentelemetry.trace.get_tracer") as mock_get_tracer:
        emit_span_event("test_event", {"key": "value"})
        mock_get_tracer.assert_called_once_with("coreason.gateway.telemetry")
        mock_span = mock_get_tracer.return_value.start_as_current_span.return_value.__enter__.return_value
        mock_span.set_attribute.assert_called_once_with("key", "value")
