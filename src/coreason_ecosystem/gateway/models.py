from pydantic import BaseModel, Field


class FederatedDiscoveryIntent(BaseModel):
    """
    Simulated pure-math intent to initiate federated capability discovery.
    """

    domain_filter: list[str] = Field(
        ...,
        description="The strict array of strings defining topological limits on the discovered capabilities.",
    )


class OracleExecutionReceipt(BaseModel):
    """
    Cryptographic lineage container for executing an MCP capability.
    """

    topology_class: str = "oracle_execution_receipt"
    executed_urn: str
    action_space_id: str
    event_cid: str
    timestamp: float
    prior_event_hash: str | None = None
