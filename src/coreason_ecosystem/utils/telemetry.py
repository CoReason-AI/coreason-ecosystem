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
import queue
import sys
import time
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from loguru import Message

__all__ = [
    "ObservabilitySettings",
    "get_observability_settings",
    "TelemetryModel",
    "setup_telemetry_mesh",
    "start_otlp_background_worker",
    "stop_otlp_background_worker",
    "logger",
]

__all__.append("bind_epistemic_context")


class ObservabilitySettings(BaseSettings):  # type: ignore[misc]
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


# Global queue and task for OTLP export
_otlp_queue: queue.SimpleQueue[dict[str, Any]] | None = None
_otlp_task: asyncio.Task[None] | None = None


async def _otlp_worker(endpoint: str) -> None:
    """
    Background worker that flushes logs to OTLP strictly asynchronously.

    Note: We bypass the official `opentelemetry-sdk` log exporter (which uses standard
    Python `threading.Thread`) in favor of manual REST. Under Python 3.14t (Free-Threading
    / `nogil`), relying on legacy threading models can introduce unpredictable GIL-related
    contention during heavy WASM AOT compilation. Using pure `asyncio.Task` + `httpx`
    bypasses the OS threading layer entirely, ensuring PEP-703 free-threading safety.
    """
    import httpx

    async with httpx.AsyncClient() as client:
        while _otlp_queue is not None:
            try:
                # Poll the lock-free queue (non-blocking in async context using a short sleep)
                try:
                    record = _otlp_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue

                # Use the actual log generation timestamp, not current processing time
                log_time_ns = int(record["time"].timestamp() * 1e9)

                payload = {
                    "resourceLogs": [
                        {
                            "scopeLogs": [
                                {
                                    "logRecords": [
                                        {
                                            "timeUnixNano": log_time_ns,
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
                except httpx.RequestError:  # pragma: no cover
                    pass
            except asyncio.CancelledError:
                break
            except Exception:  # pragma: no cover
                pass


def otlp_log_sink(message: "Message") -> None:
    """
    Custom loguru sink that routes records to the SimpleQueue lock-free queue.
    """
    if _otlp_queue is not None:
        try:
            _otlp_queue.put_nowait(dict(message.record))
        except Exception:  # pragma: no cover
            pass


def start_otlp_background_worker() -> None:
    """
    Initializes the OTLP async worker task. Call this after the event loop starts.
    """
    global _otlp_queue, _otlp_task
    try:
        loop = asyncio.get_running_loop()
        if _otlp_queue is None:
            _otlp_queue = queue.SimpleQueue()
        _otlp_task = loop.create_task(
            _otlp_worker(get_observability_settings().otlp_endpoint)
        )
    except RuntimeError:
        logger.warning("Failed to start OTLP worker: No running event loop.")


async def stop_otlp_background_worker() -> None:
    """Gracefully flush the queue and shut down the OTLP worker with a strict timeout."""
    global _otlp_queue, _otlp_task

    if _otlp_queue is not None:
        try:

            async def _wait_for_queue() -> None:
                while not _otlp_queue.empty():
                    await asyncio.sleep(0.05)

            # Give the worker a maximum of 3 seconds to flush pending telemetry
            await asyncio.wait_for(_wait_for_queue(), timeout=3.0)
        except asyncio.TimeoutError:
            # If the network is degraded, abandon the remaining logs rather than hanging the CLI
            pass

    if _otlp_task is not None:
        _otlp_task.cancel()
        try:
            await _otlp_task
        except asyncio.CancelledError:
            pass


class TelemetryModel(BaseModel):
    """
    Base Pydantic model that automatically instruments validation with OpenTelemetry spans.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Note: Intercepting failures dynamically requires either a decorator around instantiation
    # or hooking into Pydantic's core schema directly. For this architecture, we provide a
    # robust instrumented initialization method.
    @classmethod
    def validate_with_telemetry(cls, data: dict[str, Any]) -> "TelemetryModel":
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

    # Note: the background worker and sink must be started after event loop spins up.
    # However we add the sink now, but wrap in enqueue=True to bridge OS threads
    logger.add(otlp_log_sink, level=settings.log_level, enqueue=True)

    # Route standard logging to loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
