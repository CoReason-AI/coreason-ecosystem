import typing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from coreason_ecosystem.gateway.master_mcp import (
    app,
    list_actuators,
    invoke_actuator,
    registry,
    compute_schema_seal,
)


def _seed_registry() -> None:
    """Seed the registry with test capabilities for the test suite."""
    registry._mock_state = {  # type: ignore[attr-defined]
        "urn:coreason:oracle:clinical_extractor": {
            "endpoint": "http://svc-pubmed-mcp.internal:8000",
            "clearance": "PUBLIC",
        },
        "urn:coreason:oracle:mathematics": {
            "endpoint": "http://svc-math-mcp.internal:8000",
            "clearance": "CONFIDENTIAL",
        },
        "urn:coreason:oracle:milvus": {
            "endpoint": "http://coreason-milvus-mcp:8000",
            "clearance": "CONFIDENTIAL",
        },
        "urn:coreason:oracle:neo4j": {
            "endpoint": "http://coreason-neo4j-mcp:8000",
            "clearance": "CONFIDENTIAL",
        },
    }


@pytest.fixture(autouse=True)
def _hydrate_test_registry() -> typing.Generator[None, None, None]:
    """Auto-seed registry before each test and clear after."""
    _seed_registry()
    yield
    registry._mock_state = {}  # type: ignore[attr-defined]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_compute_schema_seal() -> None:
    """Test that schema sealing produces deterministic SHA-256 hashes."""
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    seal1 = compute_schema_seal(schema)
    seal2 = compute_schema_seal(schema)
    assert seal1 == seal2
    assert len(seal1) == 64  # SHA-256 hex digest


@pytest.mark.asyncio
async def test_sse_endpoint_direct() -> None:
    from coreason_ecosystem.gateway.master_mcp import handle_sse

    request = MagicMock()
    request.scope = {}
    request.receive = AsyncMock()
    request._send = AsyncMock()

    with patch(
        "coreason_ecosystem.gateway.master_mcp.sse_transport.connect_sse"
    ) as mock_connect:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_connect.return_value = mock_ctx

        with patch(
            "coreason_ecosystem.gateway.master_mcp.mcp_server.run",
            new_callable=AsyncMock,
        ) as mock_run:
            await handle_sse(request)
            mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_sse_endpoint_direct_exception() -> None:
    from coreason_ecosystem.gateway.master_mcp import handle_sse

    request = MagicMock()
    request.scope = {}
    request.receive = AsyncMock()
    request._send = AsyncMock()

    with patch(
        "coreason_ecosystem.gateway.master_mcp.sse_transport.connect_sse"
    ) as mock_connect:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_connect.return_value = mock_ctx

        with patch(
            "coreason_ecosystem.gateway.master_mcp.mcp_server.run",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = Exception("test fault")
            await handle_sse(request)
            mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_messages_endpoint_direct() -> None:
    from coreason_ecosystem.gateway.master_mcp import handle_messages

    request = MagicMock()
    request.scope = {}
    request.receive = AsyncMock()
    request._send = AsyncMock()

    with patch(
        "coreason_ecosystem.gateway.master_mcp.sse_transport.handle_post_message",
        new_callable=AsyncMock,
    ) as mock_handle:
        await handle_messages(request)
        mock_handle.assert_called_once()


@pytest.mark.asyncio
async def test_list_actuators() -> None:
    """Test that list_actuators returns the 4 built-in capabilities."""
    tools = await list_actuators()
    assert len(tools) == 4
    names = [t.name for t in tools]
    assert "federated_discovery" in names
    assert "deploy_cognitive_swarm" in names


@pytest.mark.asyncio
async def test_the_guillotine() -> None:
    """Test that unregistered URNs violently sever the connection."""
    unregistered_tool = "urn_coreason_oracle_unregistered_ghost_tool"

    arguments = {"query": "phantom call"}

    with pytest.raises(ValueError, match="Geometrical topology fault"):
        await invoke_actuator(name=unregistered_tool, arguments=arguments)


@pytest.mark.asyncio
async def test_extract_and_verify_identity_missing_header() -> None:
    from coreason_ecosystem.gateway.master_mcp import extract_and_verify_identity
    from fastapi import HTTPException

    request = MagicMock()
    request.headers = {}
    with pytest.raises(HTTPException) as exc:
        await extract_and_verify_identity(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_extract_and_verify_identity_invalid_format() -> None:
    from coreason_ecosystem.gateway.master_mcp import extract_and_verify_identity
    from fastapi import HTTPException

    request = MagicMock()
    request.headers = {"Authorization": "Basic 1234"}
    with pytest.raises(HTTPException) as exc:
        await extract_and_verify_identity(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_extract_and_verify_identity_valid_token() -> None:
    from coreason_ecosystem.gateway.master_mcp import extract_and_verify_identity

    request = MagicMock()
    request.headers = {"Authorization": "Bearer whatever_token"}
    await extract_and_verify_identity(request)
