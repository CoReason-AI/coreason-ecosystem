"""
ETL Actuator — Physical bridge to external data normalization pipelines.

Intercepts an OntologicalNormalizationIntent, triggers an external
orchestrator webhook (e.g., Dagster / Airflow), and yields an
OracleExecutionReceipt with cryptographic lineage watermarks.
"""

import hashlib
import time

import httpx

from coreason_ecosystem.gateway.models import (
    OntologicalNormalizationIntent,
    OracleExecutionReceipt,
)

# External orchestrator webhook — configurable per deployment topology.
_DAGSTER_WEBHOOK_URL = "http://dagster-daemon.internal/api/v1/run"


class ETLActuator:
    """
    Actuator that triggers external ETL/normalization pipelines and
    returns immutable cryptographic execution receipts.
    """

    def __init__(
        self,
        webhook_url: str = _DAGSTER_WEBHOOK_URL,
    ) -> None:
        self._webhook_url = webhook_url

    async def trigger_normalization(
        self,
        intent: OntologicalNormalizationIntent,
    ) -> OracleExecutionReceipt:
        """
        Trigger an external normalization pipeline for the given intent.

        Args:
            intent: The normalization intent containing the source artifact
                    CID and target ontology URN.

        Returns:
            An OracleExecutionReceipt with deterministic cryptographic
            lineage watermarks.

        Raises:
            httpx.HTTPStatusError: If the external orchestrator returns a
                                   non-2xx status code.
        """
        payload = {
            "source_artifact_cid": intent.source_artifact_cid,
            "target_ontology_urn": intent.target_ontology_urn,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self._webhook_url, json=payload)
            response.raise_for_status()

        # Deterministic cryptographic lineage watermarks.
        timestamp = time.time()
        raw = f"{intent.source_artifact_cid}:{intent.target_ontology_urn}:{timestamp}"
        event_cid = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        return OracleExecutionReceipt(
            executed_urn=intent.target_ontology_urn.replace(
                "urn:coreason:ontology:", "urn:coreason:oracle:"
            ),
            action_space_id="dagster-etl-cluster",
            event_cid=event_cid,
            timestamp=timestamp,
        )
