import unittest.mock
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from coreason_ecosystem.gateway.master_mcp import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_federated_discovery(client: TestClient) -> None:
    """Test the Master MCP discovery proxy behavior with mocked sub-MCP."""
    sub_mcp_url = "http://svc-pubmed-mcp.internal:8000/tools"

    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"name": "mock_extract", "description": "Mock clinical task", "inputSchema": {}}
    ]

    with unittest.mock.patch(
        "httpx.AsyncClient.get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_response

        payload = {
            "domain_filter": ["clinical_extractor"],
            "receipt": {
                "issuer_did": "did:coreason:oracle:test",
                "authorization_claims": {"clearance": "RESTRICTED"},
            },
        }
        response = client.post("/discover", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) >= 1
        assert data["tools"][0]["name"] == "mock_extract"
        mock_get.assert_called_with(sub_mcp_url)


@pytest.mark.asyncio
async def test_federated_discovery_empty_filter(client: TestClient) -> None:
    """Test discovery with an empty domain filter."""
    with unittest.mock.patch(
        "httpx.AsyncClient.get", new_callable=AsyncMock
    ) as mock_get:
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        payload = {
            "domain_filter": [],
            "receipt": {
                "issuer_did": "did:coreason:oracle:test",
                "authorization_claims": {"clearance": "RESTRICTED"},
            },
        }
        response = client.post("/discover", json=payload)

        assert response.status_code == 200
        assert "tools" in response.json()


@pytest.mark.asyncio
async def test_federated_discovery_request_error(client: TestClient) -> None:
    """Test discovery fallback to proxy definition when sub-MCP is down."""

    def raise_request_error(*args, **kwargs) -> None:
        raise httpx.RequestError("Connection failed")

    with unittest.mock.patch(
        "httpx.AsyncClient.get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.side_effect = raise_request_error

        payload = {
            "domain_filter": ["clinical_extractor"],
            "receipt": {
                "issuer_did": "did:coreason:oracle:test",
                "authorization_claims": {"clearance": "RESTRICTED"},
            },
        }
        response = client.post("/discover", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["tools"]) == 1
        assert "_proxy_urn" in data["tools"][0]


@pytest.mark.asyncio
async def test_execution_and_receipt(client: TestClient) -> None:
    """Test execution proxying and OracleExecutionReceipt generation."""
    target_urn = "urn:coreason:oracle:clinical_extractor"
    action_space_url = "http://svc-pubmed-mcp.internal:8000/execute"

    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "extracted", "entities": ["aspirin"]}

    with unittest.mock.patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value = mock_response

        payload = {"query": "clinical test"}
        response = client.post(f"/execute/{target_urn}", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["executed_urn"] == target_urn
        assert data["action_space_id"] == "http://svc-pubmed-mcp.internal:8000"
        assert "event_cid" in data
        assert "timestamp" in data
        assert data["result"]["status"] == "extracted"
        mock_post.assert_called_with(action_space_url, json=payload)


@pytest.mark.asyncio
async def test_execution_http_status_error(client: TestClient) -> None:
    """Test execution when sub-MCP returns an HTTP error."""
    target_urn = "urn:coreason:oracle:clinical_extractor"

    def raise_http_status_error(*args, **kwargs) -> None:
        response = httpx.Response(500)
        raise httpx.HTTPStatusError(
            "Server Error", request=unittest.mock.Mock(), response=response
        )

    with unittest.mock.patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.side_effect = raise_http_status_error

        payload = {"query": "fail test"}
        response = client.post(f"/execute/{target_urn}", json=payload)

        assert response.status_code == 500
        assert "Sub-MCP failure" in response.json()["detail"]


@pytest.mark.asyncio
async def test_execution_request_error(client: TestClient) -> None:
    """Test execution fallback status on network request failures."""
    target_urn = "urn:coreason:oracle:clinical_extractor"

    def raise_request_error(*args, **kwargs) -> None:
        raise httpx.RequestError("Network error")

    with unittest.mock.patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.side_effect = raise_request_error

        payload = {"query": "fallback test"}
        response = client.post(f"/execute/{target_urn}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["result"]["status"] == "mock_execution_success"


@pytest.mark.asyncio
async def test_the_guillotine(client: TestClient) -> None:
    """Test that unregistered URNs violently sever the connection with 404."""
    unregistered_urn = "urn:coreason:oracle:unregistered_ghost"

    payload = {"query": "phantom call"}
    response = client.post(f"/execute/{unregistered_urn}", json=payload)

    assert response.status_code == 404
    assert "unregistered URN" in response.json()["detail"]
