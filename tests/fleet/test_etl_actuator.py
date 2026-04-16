"""Tests for the ETLActuator — Semantic Crosswalk bounding proofs."""

import unittest.mock
from unittest.mock import AsyncMock

import httpx
import pytest

from coreason_ecosystem.fleet.etl_actuator import ETLActuator
from coreason_ecosystem.gateway.models import (
    OntologicalNormalizationIntent,
    OracleExecutionReceipt,
)


@pytest.mark.asyncio
async def test_trigger_normalization_success() -> None:
    """Prove that a successful pipeline trigger yields a valid receipt."""
    intent = OntologicalNormalizationIntent(
        source_artifact_cid="bafybeigdyrzt5sfp7udm",
        target_ontology_urn="urn:coreason:ontology:fda_labels",
    )

    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = unittest.mock.Mock()
    mock_response.json.return_value = {"run_id": "run-12345"}

    with unittest.mock.patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = mock_response

        actuator = ETLActuator()
        receipt = await actuator.trigger_normalization(intent)

        # Structural assertions on the receipt.
        assert isinstance(receipt, OracleExecutionReceipt)
        assert receipt.executed_urn == "urn:coreason:oracle:fda_labels"
        assert receipt.action_space_id == "dagster-etl-cluster"
        assert receipt.topology_class == "oracle_execution_receipt"
        assert len(receipt.event_cid) == 64  # SHA-256 hex digest
        assert receipt.timestamp > 0
        assert receipt.prior_event_hash is None

        # Verify the webhook was called with the correct payload.
        mock_post.assert_called_once_with(
            "http://dagster-daemon.internal/api/v1/run",
            json={
                "source_artifact_cid": "bafybeigdyrzt5sfp7udm",
                "target_ontology_urn": "urn:coreason:ontology:fda_labels",
            },
        )


@pytest.mark.asyncio
async def test_trigger_normalization_pipeline_failure() -> None:
    """Prove that a pipeline failure propagates and does NOT emit a receipt."""
    intent = OntologicalNormalizationIntent(
        source_artifact_cid="bafybeigdyrzt5sfp7udm",
        target_ontology_urn="urn:coreason:ontology:fda_labels",
    )

    mock_response = httpx.Response(500)

    def raise_for_status() -> None:
        raise httpx.HTTPStatusError(
            "Internal Server Error",
            request=unittest.mock.Mock(),
            response=mock_response,
        )

    mock_response.raise_for_status = raise_for_status  # type: ignore[assignment,method-assign]

    with unittest.mock.patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = mock_response

        actuator = ETLActuator()

        with pytest.raises(httpx.HTTPStatusError):
            await actuator.trigger_normalization(intent)
