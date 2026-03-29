# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import contextvars
import logging
import os
import re
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Record

from loguru import logger

__all__ = ["logger", "bind_epistemic_context"]

# Define context variables for OTLP readiness
epistemic_root: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "epistemic_root", default=None
)
workflow_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "workflow_id", default=None
)

# Precompiled, combined regex for single-pass execution
_REDACTION_PATTERN = re.compile(
    r"(?P<ssn>\b\d{3}-\d{2}-\d{4}\b)|(?P<email>\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b)"
)


def _redact_match(match: re.Match[str]) -> str:
    return "<REDACTED_SSN>" if match.group("ssn") else "<REDACTED_EMAIL>"


# Evaluate once at module load to avoid redundant os.environ lookups on every log
_IS_PRODUCTION = os.environ.get("ENV", "development") == "production"


@contextmanager
def bind_epistemic_context(
    current_workflow_id: str, current_root: str
) -> Generator[None, None, None]:
    """
    Binds the epistemic context to the current execution block.

    Args:
        current_workflow_id (str): The Temporal workflow ID.
        current_root (str): The Epistemic Merkle Root.

    Yields:
        None
    """
    token_root = epistemic_root.set(current_root)
    token_workflow = workflow_id.set(current_workflow_id)
    try:
        yield
    finally:
        epistemic_root.reset(token_root)
        workflow_id.reset(token_workflow)


class InterceptHandler(logging.Handler):
    """
    Intercepts standard library logs and routes them to loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emits the log record.

        Args:
            record (logging.LogRecord): The log record from the standard library.
        """
        # Get corresponding Loguru level if it exists.
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:  # pragma: no cover
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6
        while (
            frame and frame.f_code.co_filename == logging.__file__
        ):  # pragma: no cover
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _patch_record(record: "Record") -> None:
    """
    Patches the log record with epistemic context and applies redaction.

    Args:
        record (Record): The log record dictionary.
    """
    current_root = epistemic_root.get()
    current_workflow_id = workflow_id.get()

    if current_root:
        record["extra"]["epistemic_root"] = current_root
    if current_workflow_id:
        record["extra"]["workflow_id"] = current_workflow_id

    if _IS_PRODUCTION:
        # Execute the precompiled regex in a single highly-optimized pass
        record["message"] = _REDACTION_PATTERN.sub(_redact_match, record["message"])


# Defer telemetry mesh setup
def init_logger() -> None:
    from coreason_ecosystem.utils.telemetry import setup_telemetry_mesh

    setup_telemetry_mesh()


init_logger()
