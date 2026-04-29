from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


class FederatedDiscoveryIntent(BaseModel):
    """
    Simulated pure-math intent to initiate federated capability discovery.
    """

    domain_filter: list[str] = Field(
        ...,
        description="The strict array of strings defining topological limits on the discovered capabilities.",
    )
    minimum_epistemic_status: str = Field(
        default="DRAFT",
        description=(
            "The minimum SRB governance lifecycle phase required for "
            "projected capabilities "
            "(DRAFT / SRB_APPROVED / CLIENT_APPROVED / PUBLISHED)."
        ),
    )


class OracleExecutionReceipt(BaseModel):
    """
    Cryptographic lineage container for executing an MCP capability.
    Temporary Isomorphic Shim: will be replaced by coreason_manifest.spec.ontology
    once the manifest exports this schema.
    """

    topology_class: Literal["oracle_execution_receipt"] = "oracle_execution_receipt"
    executed_urn: Annotated[
        str,
        StringConstraints(max_length=2000, pattern=r"^urn:coreason:oracle:.*$"),
    ]
    action_space_id: Annotated[
        str,
        StringConstraints(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_-]+$"),
    ]
    event_cid: Annotated[
        str,
        StringConstraints(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$"),
    ]
    prior_event_hash: (
        Annotated[
            str,
            StringConstraints(min_length=1, max_length=128, pattern=r"^[a-f0-9]{64}$"),
        ]
        | None
    ) = None
    timestamp: float


class OntologicalNormalizationIntent(BaseModel):
    """
    Intent to trigger an external ETL/normalization pipeline against a
    specific ontology target.
    Temporary Isomorphic Shim: will be replaced by coreason_manifest.spec.ontology
    once the manifest exports this schema.
    """

    topology_class: Literal["ontological_normalization"] = "ontological_normalization"
    source_artifact_cid: Annotated[
        str,
        StringConstraints(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$"),
    ]
    target_ontology_urn: Annotated[
        str,
        StringConstraints(max_length=2000, pattern=r"^urn:coreason:ontology:.*$"),
    ]


class CapabilityEntry(BaseModel):
    """
    State Space Formalization: Strict capability graph mapping.
    """

    urn: Annotated[
        str,
        StringConstraints(
            max_length=2000,
            pattern=r"^urn:coreason:(actionspace|archetype_[a-d]|oracle|state):.*$",
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
