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
import time
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Self

from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    pass

__all__ = [
    "ObservabilitySettings",
    "get_observability_settings",
    "TelemetryModel",
    "setup_telemetry_mesh",
    "emit_span_event",
    "logger",
]

__all__.append("bind_epistemic_context")


class ObservabilitySettings(BaseSettings):
    """
    Dynamic configuration for the Observability Mesh.
    """

    model_config = SettingsConfigDict(
        env_prefix="COREASON_", env_file=".env", extra="ignore"
    )

    log_level: str = "INFO"
    otlp_endpoint: str = "http://localhost:4318/v1/logs"
    enable_diagnostics: bool = False


@lru_cache(maxsize=1)
def get_observability_settings() -> ObservabilitySettings:
    """
    Returns a globally cached instance of ObservabilitySettings to prevent
    synchronous disk I/O and environment parsing on high-frequency paths.
    """
    return ObservabilitySettings()





class TelemetryModel(BaseModel):
    """
    Base Pydantic model that automatically instruments validation with OpenTelemetry spans.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Note: Intercepting failures dynamically requires either a decorator around instantiation
    # or hooking into Pydantic's core schema directly. For this architecture, we provide a
    # robust instrumented initialization method.
    @classmethod
    def validate_with_telemetry(cls, data: dict[str, Any]) -> Self:
        settings = get_observability_settings()
        tracer = trace.get_tracer("coreason.pydantic.telemetry")

        start_time = time.perf_counter()
        try:
            instance = cls.model_validate(data)
            delta_t = time.perf_counter() - start_time

            with tracer.start_as_current_span(f"validate_{cls.__name__}") as span:
                span.set_attribute("delta_t_seconds", delta_t)
                span.add_event("Validation successful")
            return instance
        except Exception as e:
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                # Fallback to create an error span if model_validate fails before the hook
                with tracer.start_as_current_span(
                    f"validate_{cls.__name__}_error"
                ) as span:
                    errors = e.errors()
                    redacted_errors: list[Any] = []
                    for err in errors:
                        if settings.enable_diagnostics:
                            redacted_errors.append(err)
                        else:
                            # Redact inputs in production
                            err_copy = dict(err)
                            err_copy.pop("input", None)
                            redacted_errors.append(err_copy)

                    span.record_exception(e)
                    span.set_attribute("semantic_entropy", str(redacted_errors))
                    logger.error(
                        f"Ontological Drift in {cls.__name__}: {redacted_errors}"
                    )
            raise


def setup_telemetry_mesh() -> None:
    """
    Initializes the ObservabilitySettings, OTel exporters, and Loguru configuration.
    """
    from loguru import logger
    from coreason_ecosystem.utils.logger import (
        InterceptHandler,
        _patch_record,
    )

    settings = get_observability_settings()

    # Configure Loguru
    logger.remove()

    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    from pathlib import Path

    log_path = Path("logs")
    if not log_path.exists():  # pragma: no cover
        log_path.mkdir(parents=True, exist_ok=True)

    logger.add(
        "logs/app.log",
        rotation="500 MB",
        retention="10 days",
        serialize=True,
        enqueue=True,
        level="DEBUG",
        diagnose=settings.enable_diagnostics,
    )

    # OpenTelemetry Tracing Setup
    provider = TracerProvider()

    trace_endpoint = settings.otlp_endpoint.replace("v1/logs", "v1/traces")
    otlp_exporter = OTLPSpanExporter(endpoint=trace_endpoint)

    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    logger.configure(patcher=_patch_record)

    # Setup OpenTelemetry Native Log Exporter
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        
        logger_provider = LoggerProvider()
        set_logger_provider(logger_provider)
        
        otlp_log_exporter = OTLPLogExporter(endpoint=settings.otlp_endpoint)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
        
        otlp_handler = LoggingHandler(level=0, logger_provider=logger_provider)
        logger.add(otlp_handler, level=settings.log_level)
    except ImportError:
        logger.warning("OpenTelemetry log exporter not found. Skipping native OTLP logs setup.")

    # Route standard logging to loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def emit_span_event(name: str, attributes: dict[str, Any]) -> None:
    """Fire a single OpenTelemetry span event for cross-boundary observability.

    Creates a new span under the ``coreason.gateway.telemetry`` tracer,
    attaches all *attributes* as span attributes, and immediately ends
    the span.  This is intentionally fire-and-forget so it never blocks
    the JSON-RPC loop.

    Args:
        name: The semantic name of the event (e.g. ``mcp_tool_execution``).
        attributes: A mapping of key-value pairs to attach to the span.
    """
    tracer = trace.get_tracer("coreason.gateway.telemetry")
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
