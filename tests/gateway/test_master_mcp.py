import unittest.mock
import typing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import Tool, TextContent
from fastapi.testclient import TestClient

from coreason_ecosystem.gateway.master_mcp import (
    app,
    list_actuators,
    invoke_actuator,
    current_clearance,
    registry,
    compute_schema_seal,
)
from mcp.shared.exceptions import McpError


def _seed_registry() -> None:
    """Seed the registry with test capabilities for the test suite."""
    registry._cache = {
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
    registry._cache = {}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_compute_schema_seal() -> None:
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
    """Test the Master MCP discovery proxy behavior with mocked SSE sub-MCP."""
    sub_mcp_url = "http://svc-pubmed-mcp.internal:8000/sse"

    with unittest.mock.patch(
        "coreason_ecosystem.gateway.master_mcp.sse_client",
    ) as mock_sse_client:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_sse_client.return_value = mock_ctx

        with unittest.mock.patch(
            "coreason_ecosystem.gateway.master_mcp.ClientSession"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.initialize = AsyncMock()

            # mock response tooling
            mock_tool = unittest.mock.Mock()
            mock_tool.name = "extract"
            mock_tool.description = "Mock clinical task"
            mock_tool.inputSchema = {"type": "object", "properties": {}}

            mock_response = unittest.mock.Mock()
            mock_response.tools = [mock_tool]
            mock_session.list_tools.return_value = mock_response

            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__.return_value = mock_session
            mock_session_cls.return_value = mock_session_ctx

            current_clearance.set("PUBLIC")
            tools = await list_actuators()

            assert len(tools) >= 1
            assert isinstance(tools[0], Tool)

            names = [tool.name for tool in tools]
            assert "urn_coreason_oracle_clinical_extractor_extract" in names

            mock_sse_client.assert_any_call(sub_mcp_url)


@pytest.mark.asyncio
async def test_list_actuators_request_error() -> None:
    """Test that offline substrates are dropped from the projection (Zero-Trust)."""
    with unittest.mock.patch(
        "coreason_ecosystem.gateway.master_mcp.sse_client"
    ) as mock_sse_client:
        mock_sse_client.side_effect = Exception("Connection failed")

        current_clearance.set("PUBLIC")
        tools = await list_actuators()

        # Unreachable substrates must not be projected — they do not exist
        # in the active topology. (Only the 3 internal hollow plane proxy tools remain)
        assert len(tools) == 3


@pytest.mark.asyncio
async def test_invoke_actuator_and_receipt() -> None:
    """Test execution proxying and OracleExecutionReceipt generation."""
    tool_name = "urn_coreason_oracle_clinical_extractor_extract"
    action_space_url = "http://svc-pubmed-mcp.internal:8000/sse"

    with unittest.mock.patch(
        "coreason_ecosystem.gateway.master_mcp.sse_client",
    ) as mock_sse_client:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_sse_client.return_value = mock_ctx

        with unittest.mock.patch(
            "coreason_ecosystem.gateway.master_mcp.ClientSession"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.initialize = AsyncMock()

            # Constructing a generic text return simulation
            mock_content = unittest.mock.Mock()
            mock_content.model_dump.return_value = {
                "status": "extracted",
                "entities": ["data"],
            }
            mock_response = unittest.mock.Mock()
            mock_response.content = [mock_content]

            mock_session.call_tool = AsyncMock()
            mock_session.call_tool.return_value = mock_response

            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__.return_value = mock_session
            mock_session_cls.return_value = mock_session_ctx

            with unittest.mock.patch(
                "coreason_ecosystem.gateway.master_mcp.emit_span_event"
            ) as mock_telemetry:
                arguments = {"query": "clinical test"}
                result = await invoke_actuator(name=tool_name, arguments=arguments)

                assert isinstance(result, list)
                assert len(result) == 1
                assert isinstance(result[0], TextContent)

                mock_session.call_tool.assert_called_with(
                    "extract", arguments=arguments
                )
                mock_sse_client.assert_called_with(action_space_url)

                # Telemetry bounding proof: emit_span_event must fire exactly once.
                mock_telemetry.assert_called_once()
                call_args = mock_telemetry.call_args
                assert (
                    call_args.kwargs.get("name")
                    or call_args.args[0] == "mcp_tool_execution"
                )
                attrs = call_args.kwargs.get("attributes") or call_args.args[1]
                assert attrs["executed_urn"] == "urn:coreason:oracle:clinical_extractor"
                assert (
                    attrs["action_space_id"] == "urn_coreason_oracle_clinical_extractor"
                )
                assert "execution_time_ms" in attrs
                assert isinstance(attrs["execution_time_ms"], float)


@pytest.mark.asyncio
async def test_invoke_actuator_http_status_error() -> None:
    """Test execution when sub-MCP returns an McpError."""
    tool_name = "urn_coreason_oracle_clinical_extractor_fail"

    with unittest.mock.patch(
        "coreason_ecosystem.gateway.master_mcp.sse_client"
    ) as mock_sse_client:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_sse_client.return_value = mock_ctx

        with unittest.mock.patch(
            "coreason_ecosystem.gateway.master_mcp.ClientSession"
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.initialize = AsyncMock()

            # Build a mock payload
            error_data = unittest.mock.Mock()
            error_data.message = "internal server error JSON-RPC"
            mock_session.call_tool = AsyncMock()
            mock_session.call_tool.side_effect = McpError(error=error_data)

            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__.return_value = mock_session
            mock_session_cls.return_value = mock_session_ctx

            arguments = {"query": "fail test"}
            result = await invoke_actuator(name=tool_name, arguments=arguments)

            assert "Sub-MCP failure: internal server error JSON-RPC" in result[0].text


@pytest.mark.asyncio
async def test_invoke_actuator_request_error() -> None:
    """Test execution fallback status on network request failures."""
    tool_name = "urn_coreason_oracle_clinical_extractor_fail"

    with unittest.mock.patch(
        "coreason_ecosystem.gateway.master_mcp.sse_client"
    ) as mock_sse_client:
        mock_sse_client.side_effect = Exception("Network error")

        arguments = {"query": "fallback test"}
        with pytest.raises(RuntimeError, match="Topological Severance Event"):
            await invoke_actuator(name=tool_name, arguments=arguments)


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

    request = MagicMock()
    request.headers = {}
    await extract_and_verify_identity(request)
    assert current_clearance.get() == "PUBLIC"


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
async def test_extract_and_verify_identity_invalid_json() -> None:
    from coreason_ecosystem.gateway.master_mcp import extract_and_verify_identity
    from fastapi import HTTPException

    request = MagicMock()
    request.headers = {"Authorization": "Bearer not-base64!"}

    with pytest.raises(HTTPException) as exc:
        await extract_and_verify_identity(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_extract_and_verify_identity_valid_token() -> None:
    from coreason_ecosystem.gateway.master_mcp import extract_and_verify_identity

    request = MagicMock()
    import base64
    import json

    payload = {"user": "test"}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    request.headers = {"Authorization": f"Bearer {encoded}"}

    with patch(
        "coreason_ecosystem.gateway.master_mcp.identity_router.authorize_coordinate",
        new_callable=AsyncMock,
    ) as mock_verify:
        mock_verify.return_value = {"clearance": "SECRET"}
        await extract_and_verify_identity(request)
        assert current_clearance.get() == "SECRET"
        mock_verify.assert_called_once_with(payload)


@pytest.mark.asyncio
async def test_invoke_actuator_deploy_cognitive_swarm() -> None:
    arguments = {
        "swarm_size": 3,
        "swarm_name": "test_swarm",
        "agent_urn": "urn:coreason:archetype:ai",
    }
    with (
        patch(
            "coreason_ecosystem.gateway.master_mcp.CognitiveSwarmDeploymentManifest.model_validate"
        ),
        patch(
            "coreason_ecosystem.gateway.master_mcp.up.provision_swarm_topology",
            new_callable=AsyncMock,
            create=True,
        ) as mock_up,
    ):
        result = await invoke_actuator(
            name="deploy_cognitive_swarm", arguments=arguments
        )
        assert len(result) == 1
        assert "deploy_cognitive_swarm" in result[0].text
        mock_up.assert_called_once()


@pytest.mark.asyncio
async def test_invoke_actuator_establish_federated_link() -> None:
    arguments = {
        "target_mesh_id": "mesh_123",
        "auth_token": "token",
    }
    with (
        patch(
            "coreason_ecosystem.gateway.master_mcp.FederatedSecurityMacroManifest.model_validate"
        ),
        patch(
            "coreason_ecosystem.gateway.master_mcp.sync.establish_federated_link",
            new_callable=AsyncMock,
            create=True,
        ) as mock_sync,
    ):
        result = await invoke_actuator(
            name="establish_federated_link", arguments=arguments
        )
        assert len(result) == 1
        assert "establish_federated_link" in result[0].text
        mock_sync.assert_called_once()


@pytest.mark.asyncio
async def test_invoke_actuator_inject_chaos_fault() -> None:
    arguments = {
        "fault_type": "network_partition",
        "duration_seconds": 60,
    }
    with (
        patch(
            "coreason_ecosystem.gateway.master_mcp.ChaosExperimentTask.model_validate"
        ),
        patch(
            "coreason_ecosystem.gateway.master_mcp.pulumi_actuator.inject_chaos_fault",
            new_callable=AsyncMock,
            create=True,
        ) as mock_chaos,
    ):
        result = await invoke_actuator(name="inject_chaos_fault", arguments=arguments)
        assert len(result) == 1
        assert "inject_chaos_fault" in result[0].text
        mock_chaos.assert_called_once()
