import unittest.mock
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from coreason_ecosystem.gateway.master_mcp import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_sybil_rejection(client: TestClient) -> None:
    """A fraudulent payload bearing did:web:hack.com must mathematically fail."""
    payload = {
        "domain_filter": [],
        "receipt": {
            "issuer_did": "did:web:hack.com",
            "authorization_claims": {"clearance": "PUBLIC"},
        },
    }
    response = client.post("/discover", json=payload)

    assert response.status_code == 401
    assert "Invalid issuer_did" in response.json()["detail"]


def test_missing_receipt(client: TestClient) -> None:
    """Test payload lacking cryptographic receipt fails."""
    payload = {"domain_filter": []}
    response = client.post("/discover", json=payload)
    assert response.status_code == 401
    assert "Missing cryptographic receipt" in response.json()["detail"]


def test_missing_clearance(client: TestClient) -> None:
    """Test payload lacking semantic clearance fails."""
    payload = {
        "domain_filter": [],
        "receipt": {"issuer_did": "did:coreason:oracle:empty"},
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 401
    assert "Missing semantic clearance" in response.json()["detail"]


@pytest.mark.asyncio
async def test_lbac_masking(client: TestClient) -> None:
    """An agent possessing PUBLIC clearance only discovers PUBLIC endpoints."""
    mock_response = unittest.mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"name": "fake_tool"}]

    with unittest.mock.patch(
        "httpx.AsyncClient.get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_response

        payload = {
            "domain_filter": [],
            "receipt": {
                "issuer_did": "did:coreason:agent:public1",
                "authorization_claims": {"clearance": "PUBLIC"},
            },
        }
        response = client.post("/discover", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data

        calls = mock_get.call_args_list
        urls = [call[0][0] for call in calls]

        assert "http://svc-pubmed-mcp.internal:8000/tools" in urls
        assert "http://svc-math-mcp.internal:8000/tools" not in urls
        assert "http://svc-weapons-mcp.internal:8000/tools" not in urls
