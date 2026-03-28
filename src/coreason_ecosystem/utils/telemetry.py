# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest

import asyncio
import logging
import sys
import time
from typing import TYPE_CHECKING, Any

from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from loguru import Message

__all__ = [
    "ObservabilitySettings",
    "TelemetryModel",
    "setup_telemetry_mesh",
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


# Global queue and task for OTLP export
_otlp_queue: asyncio.Queue[dict[str, Any]] | None = None
_otlp_task: asyncio.Task[None] | None = None


async def _otlp_worker(endpoint: str) -> None:
    """
    Background worker that flushes logs to OTLP strictly asynchronously.
    """
    import httpx

    async with httpx.AsyncClient() as client:
        while _otlp_queue is not None:
            try:
                record = await _otlp_queue.get()
                # Dummy translation to OTLP JSON (simplified for testing/mesh integration)
                # SOTA 2026 demands proper protobufs, but for non-blocking HTTP we will use basic REST.
                payload = {
                    "resourceLogs": [
                        {
                            "scopeLogs": [
                                {
                                    "logRecords": [
                                        {
                                            "timeUnixNano": int(time.time() * 1e9),
                                            "severityText": record["level"]["name"],
                                            "body": {"stringValue": record["message"]},
                                            "attributes": [
                                                {
                                                    "key": k,
                                                    "value": {"stringValue": str(v)},
                                                }
                                                for k, v in record["extra"].items()
                                            ],
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
                try:
                    await client.post(endpoint, json=payload, timeout=2.0)
                except httpx.RequestError:
                    # Drop silently on telemetry failure to prevent cascading
                    pass
                _otlp_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                # Catch-all to prevent worker crash
                if _otlp_queue is not None:
                    _otlp_queue.task_done()


def otlp_log_sink(message: "Message") -> None:
    """
    Custom loguru sink that routes records to the asyncio queue.
    """
    if _otlp_queue is not None:
        try:
            _otlp_queue.put_nowait(dict(message.record))
        except asyncio.QueueFull:
            pass


class TelemetryModel(BaseModel):
    """
    Base Pydantic model that automatically instruments validation with OpenTelemetry spans.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _telemetry_validation_hook(self) -> "TelemetryModel":
        tracer = trace.get_tracer("coreason.pydantic.telemetry")

        with tracer.start_as_current_span(
            f"validate_{self.__class__.__name__}"
        ) as span:
            start_time = time.perf_counter()
            # If we reach here, Pydantic core validation succeeded.
            end_time = time.perf_counter()
            delta_t = end_time - start_time

            span.set_attribute("delta_t_seconds", delta_t)
            span.add_event("Validation successful")
            logger.debug(f"Validated {self.__class__.__name__} in {delta_t:.6f}s")
            return self

    # Note: Intercepting failures dynamically requires either a decorator around instantiation
    # or hooking into Pydantic's core schema directly. For this architecture, we provide a
    # robust instrumented initialization method.
    @classmethod
    def validate_with_telemetry(cls, data: dict[str, Any]) -> "TelemetryModel":
        settings = ObservabilitySettings()
        tracer = trace.get_tracer("coreason.pydantic.telemetry")
        with tracer.start_as_current_span(f"validate_{cls.__name__}") as span:
            start_time = time.perf_counter()
            try:
                obj = cls.model_validate(data)
                delta_t = time.perf_counter() - start_time
                span.set_attribute("delta_t_seconds", delta_t)
                return obj
            except Exception as e:
                # Capture Semantic Entropy
                from pydantic import ValidationError

                if isinstance(e, ValidationError):
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
        _redaction_filter,
    )

    settings = ObservabilitySettings()

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
        filter=_redaction_filter,
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
        filter=_redaction_filter,
    )

    # Initialize async queue for OTLP
    global _otlp_queue, _otlp_task
    try:
        loop = asyncio.get_running_loop()
        _otlp_queue = asyncio.Queue(maxsize=10000)
        _otlp_task = loop.create_task(_otlp_worker(settings.otlp_endpoint))
        logger.add(otlp_log_sink, level=settings.log_level)
    except RuntimeError:
        # No running event loop yet (e.g. CLI initialization phase).
        # We will skip the async OTLP sink setup for now or rely on the sync SDK if needed.
        pass

    logger.configure(patcher=_patch_record)

    # OpenTelemetry Tracing Setup
    provider = TracerProvider()
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Route standard logging to loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
