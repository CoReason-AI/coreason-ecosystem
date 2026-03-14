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

__all__ = ["EpistemicLedgerState", "ObservationEvent", "ToolInvocationEvent", "WorkflowManifest"]
