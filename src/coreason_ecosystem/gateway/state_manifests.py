# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


class SubstrateCapabilityProfile(BaseModel):
    """Typed representation of Substrate physical capability metadata.

    Captures the hardware and protocol properties that a registered
    Substrate URN self-reports via its ``manifest.yaml``.  Used by the
    ``SovereignMCPRegistry`` two-stage resolution pipeline to hard-filter
    candidates against an ``EpistemicRigidityPolicy`` and Pareto-optimize
    survivors via a ``RoutingFrontierPolicy``.
    """

    default_minimum_rigidity_tier: int = Field(
        default=0,
        ge=0,
        le=255,
        description=(
            "The mathematical scalar representing the minimum hardware "
            "execution rigor this Substrate provides (0=CPU, 255=Max GPU)."
        ),
    )
    provided_epistemic_security: Literal["PUBLIC", "CONFIDENTIAL", "RESTRICTED"] = (
        Field(
            default="PUBLIC",
            description=(
                "The LBAC network perimeter that this Substrate physically "
                "guarantees for tenant data isolation."
            ),
        )
    )
    provided_vram_gb: int = Field(
        default=0,
        ge=0,
        description=(
            "The available GPU VRAM (in gigabytes) on the physical hardware "
            "backing this Substrate."
        ),
    )
    supported_remote_decoding_protocols: list[str] = Field(
        default_factory=lambda: ["NONE"],
        description=(
            "The structured output protocols this Substrate supports for "
            "constrained decoding offload."
        ),
    )


class CapabilityEntry(BaseModel):
    """
    State Space Formalization: Strict capability graph mapping.
    """

    urn: Annotated[
        str,
        StringConstraints(
            max_length=2000,
            pattern=r"^urn:[a-z0-9_]+:(actionspace|archetype_[a-d]|oracle|state):.*$",
        ),
    ] = Field(description="The unique semantic identifier for the node.")
    endpoint: str = Field(description="The physical routing URI endpoint.")
    clearance: Literal["PUBLIC", "CONFIDENTIAL", "RESTRICTED"] = Field(
        default="RESTRICTED", description="The required security clearance."
    )
    epistemic_status: Literal[
        "DRAFT", "SRB_APPROVED", "CLIENT_APPROVED", "PUBLISHED"
    ] = Field(default="DRAFT", description="The node's SRB governance lifecycle phase.")


class CapabilityMatrix(BaseModel):
    """
    Memory Substrate Instantiation mapping for the Registry.
    """

    capabilities: list[CapabilityEntry] = Field(
        default_factory=list, description="List of initialized capability bounds."
    )
