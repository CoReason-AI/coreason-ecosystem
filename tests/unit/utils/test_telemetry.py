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
import sys
from typing import Any, Generator

import pytest
from pydantic import ValidationError

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
import loguru

import coreason_ecosystem.utils.logger as logger_module
from coreason_ecosystem.utils.logger import (
    InterceptHandler,
    _patch_record,
    bind_epistemic_context,
)
from coreason_ecosystem.utils.telemetry import TelemetryModel


_CACHED_PROVIDER = None
_CACHED_EXPORTER = None

@pytest.fixture(scope="session", autouse=True)
def init_global_telemetry() -> Generator[None, None, None]:
    """Initialize a single physical tracer provider for the entire test session."""
    global _CACHED_PROVIDER, _CACHED_EXPORTER
    
    if _CACHED_PROVIDER is None:
        _CACHED_PROVIDER = TracerProvider()
        _CACHED_EXPORTER = InMemorySpanExporter()
        processor = SimpleSpanProcessor(_CACHED_EXPORTER)
        _CACHED_PROVIDER.add_span_processor(processor)

        # Clear any existing global provider to allow overriding it for tests
        trace._TRACER_PROVIDER = None 
        
        # OpenTelemetry uses a Once object to prevent overriding. Reset it.
        if hasattr(trace, "_TRACER_PROVIDER_SET_ONCE"):
            import opentelemetry.util._once
            trace._TRACER_PROVIDER_SET_ONCE = opentelemetry.util._once.Once()

        trace.set_tracer_provider(_CACHED_PROVIDER)

    yield

    if _CACHED_PROVIDER is not None:
        _CACHED_PROVIDER.shutdown()
        
    try:
        from opentelemetry._logs import get_logger_provider
        provider = get_logger_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def setup_telemetry() -> Generator[InMemorySpanExporter, None, None]:
    global _CACHED_EXPORTER
    assert _CACHED_EXPORTER is not None
    _CACHED_EXPORTER.clear()
    
    import os
    original_log_json = os.environ.get("COREASON_LOG_JSON")
    os.environ["COREASON_LOG_JSON"] = "true"
    
    yield _CACHED_EXPORTER
    
    _CACHED_EXPORTER.clear()
    if original_log_json is not None:
        os.environ["COREASON_LOG_JSON"] = original_log_json
    else:
        del os.environ["COREASON_LOG_JSON"]


def test_bind_epistemic_context() -> None:
    with bind_epistemic_context("workflow_1", "root_1"):
        assert logger_module.epistemic_root.get() == "root_1"
        assert logger_module.workflow_id.get() == "workflow_1"


def test_intercept_handler(capsys: pytest.CaptureFixture[str]) -> None:
    handler = InterceptHandler()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message physical",
        args=(),
        exc_info=None,
    )

    logger_id = loguru.logger.add(sys.stderr, format="{level} | {message}")
    try:
        handler.emit(record)
        captured = capsys.readouterr()
        assert "INFO" in captured.err
        assert "test message physical" in captured.err

        record_invalid_level = logging.LogRecord(
            name="test",
            level=999,
            pathname="test.py",
            lineno=1,
            msg="invalid level physical",
            args=(),
            exc_info=None,
        )
        handler.emit(record_invalid_level)
        captured = capsys.readouterr()
        assert "invalid level physical" in captured.err
    finally:
        loguru.logger.remove(logger_id)


def test_patch_record() -> None:
    record: dict[str, Any] = {"extra": {}}
    with bind_epistemic_context("test_workflow", "test_root"):
        _patch_record(record)  # type: ignore[arg-type]
    assert record["extra"]["workflow_id"] == "test_workflow"
    assert record["extra"]["epistemic_root"] == "test_root"


def test_redaction_filter_dev() -> None:
    record: dict[str, Any] = {
        "message": "Test message with email@example.com and 123-45-6789",
        "extra": {},
    }
    
    orig_is_production = logger_module._IS_PRODUCTION
    logger_module._IS_PRODUCTION = False
    try:
        with bind_epistemic_context("", ""):
            _patch_record(record)  # type: ignore[arg-type]
        assert "email@example.com" in record["message"]
        assert "123-45-6789" in record["message"]
    finally:
        logger_module._IS_PRODUCTION = orig_is_production


def test_redaction_filter_prod() -> None:
    record: dict[str, Any] = {
        "message": "Test message with email@example.com and 123-45-6789",
        "extra": {},
    }
    
    orig_is_production = logger_module._IS_PRODUCTION
    logger_module._IS_PRODUCTION = True
    try:
        with bind_epistemic_context("", ""):
            _patch_record(record)  # type: ignore[arg-type]
        assert "<REDACTED_EMAIL>" in record["message"]
        assert "<REDACTED_SSN>" in record["message"]
    finally:
        logger_module._IS_PRODUCTION = orig_is_production


def test_telemetry_model_success(setup_telemetry: InMemorySpanExporter) -> None:
    class TestModel(TelemetryModel):
        name: str

    model = TestModel.validate_with_telemetry({"name": "test"})
    assert isinstance(model, TestModel)
    assert model.name == "test"
    
    spans = setup_telemetry.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "validate_TestModel"


def test_telemetry_model_failure_diagnostics(setup_telemetry: InMemorySpanExporter) -> None:
    import coreason_ecosystem.utils.telemetry as telemetry_module
    
    class MockSettings:
        enable_diagnostics = True

    orig_get_settings = telemetry_module.get_observability_settings
    telemetry_module.get_observability_settings = lambda: MockSettings()  # type: ignore[assignment,return-value]
    
    try:
        class TestModel(TelemetryModel):
            name: str

        with pytest.raises(ValidationError):
            TestModel.validate_with_telemetry({"name": 123})
            
        spans = setup_telemetry.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "validate_TestModel_error"
        assert len(spans[0].events) == 1
        assert spans[0].events[0].name == "exception"
    finally:
        telemetry_module.get_observability_settings = orig_get_settings


def test_telemetry_model_failure_no_diagnostics(setup_telemetry: InMemorySpanExporter) -> None:
    import coreason_ecosystem.utils.telemetry as telemetry_module
    
    class MockSettings:
        enable_diagnostics = False

    orig_get_settings = telemetry_module.get_observability_settings
    telemetry_module.get_observability_settings = lambda: MockSettings()  # type: ignore[assignment,return-value]
    
    try:
        class TestModel(TelemetryModel):
            name: str

        with pytest.raises(ValidationError):
            TestModel.validate_with_telemetry({"name": 123})
            
        spans = setup_telemetry.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "validate_TestModel_error"
        assert len(spans[0].events) == 1
        assert spans[0].events[0].name == "exception"
    finally:
        telemetry_module.get_observability_settings = orig_get_settings


def test_logger_patch_record_none() -> None:
    record: dict[str, Any] = {"message": "Test message", "extra": {}}
    _patch_record(record)  # type: ignore[arg-type]
    assert "workflow_id" not in record["extra"]
    assert "epistemic_root" not in record["extra"]


def test_emit_span_event(setup_telemetry: InMemorySpanExporter) -> None:
    from coreason_ecosystem.utils.telemetry import emit_span_event

    emit_span_event("test_event", {"key": "value"})
    
    spans = setup_telemetry.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test_event"
    assert spans[0].attributes is not None
    assert spans[0].attributes.get("key") == "value"
