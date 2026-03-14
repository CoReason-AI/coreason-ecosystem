# Copyright (c) 2024-2025 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0.0 (PPL 3.0.0).

"""
CoReason Ecosystem - SOTA Neurosymbolic Execution Plane
"""

__version__ = "0.1.0"

# Re-export the Hollow Data Plane for developer ergonomics
from coreason_manifest.spec.ontology import (
    EpistemicLedgerState,
    ObservationEvent,
    ToolInvocationEvent,
    WorkflowManifest,
)

__all__ = [
    "EpistemicLedgerState",
    "ObservationEvent",
    "ToolInvocationEvent",
    "WorkflowManifest",
]
