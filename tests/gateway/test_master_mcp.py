import typing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from coreason_ecosystem.gateway.master_mcp import (
    app,
    list_actuators,
    invoke_actuator,
    current_clearance,
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
        "auth_token": "token",  # nosec B105
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


@pytest.mark.asyncio
async def test_invoke_actuator_federated_discovery() -> None:
    arguments = {"domain_filter": [], "minimum_epistemic_status": "DRAFT"}
    with patch(
        "coreason_ecosystem.gateway.master_mcp.federated_discovery",
        new_callable=AsyncMock,
    ) as mock_fd:
        mock_fd.return_value = "discovery result"
        result = await invoke_actuator(name="federated_discovery", arguments=arguments)
        assert len(result) == 1
        assert result[0].text == "discovery result"
        mock_fd.assert_called_once_with(arguments)


@pytest.mark.asyncio
async def test_invoke_actuator_proxy_http() -> None:
    arguments = {"param": "value"}
    with (
        patch("coreason_ecosystem.gateway.master_mcp.sse_client") as mock_sse_client,
        patch(
            "coreason_ecosystem.gateway.master_mcp.ClientSession"
        ) as mock_session_cls,
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.resolve_urn",
            new_callable=AsyncMock,
        ) as mock_resolve,
    ):
        mock_resolve.return_value = "http://svc-pubmed-mcp.internal:8000"
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_sse_client.return_value = mock_ctx

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = MagicMock(content="http success")
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_cls.return_value = mock_session_ctx

        result = await invoke_actuator(
            name="urn:coreason:oracle:clinical_extractor", arguments=arguments
        )
        assert len(result) == 1
        assert result[0].text == "http success"
        mock_session.initialize.assert_awaited_once()
        mock_session.call_tool.assert_awaited_once_with(
            "urn:coreason:oracle:clinical_extractor", arguments=arguments
        )


@pytest.mark.asyncio
async def test_invoke_actuator_proxy_stdio() -> None:
    arguments = {"param": "value"}
    with (
        patch(
            "coreason_ecosystem.gateway.master_mcp.stdio_client"
        ) as mock_stdio_client,
        patch(
            "coreason_ecosystem.gateway.master_mcp.ClientSession"
        ) as mock_session_cls,
        patch("coreason_ecosystem.gateway.master_mcp.StdioServerParameters"),
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.resolve_urn",
            new_callable=AsyncMock,
        ) as mock_resolve,
    ):
        mock_resolve.return_value = "/usr/bin/local-mcp"
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_stdio_client.return_value = mock_ctx

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = MagicMock(content="stdio success")
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_cls.return_value = mock_session_ctx

        result = await invoke_actuator(name="urn:local:test", arguments=arguments)
        assert len(result) == 1
        assert result[0].text == "stdio success"


@pytest.mark.asyncio
async def test_invoke_actuator_proxy_exception() -> None:
    arguments = {"param": "value"}
    with (
        patch(
            "coreason_ecosystem.gateway.master_mcp.sse_client",
            side_effect=Exception("proxy failure"),
        ),
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.resolve_urn",
            new_callable=AsyncMock,
        ) as mock_resolve,
    ):
        mock_resolve.return_value = "http://svc-pubmed-mcp.internal:8000"
        with pytest.raises(
            RuntimeError, match="Cross-plane capability execution failed: proxy failure"
        ):
            await invoke_actuator(
                name="urn:coreason:oracle:clinical_extractor", arguments=arguments
            )


@pytest.mark.asyncio
async def test_federated_discovery_logic() -> None:
    from coreason_ecosystem.gateway.master_mcp import federated_discovery

    arguments = {"domain_filter": ["internal"], "minimum_epistemic_status": "DRAFT"}
    with patch(
        "coreason_ecosystem.gateway.master_mcp.epistemic_transmuter.project_capabilities",
        new_callable=AsyncMock,
    ) as mock_proj:
        mock_proj.return_value = {
            "urn:coreason:oracle:clinical_extractor:internal": "http://svc-pubmed-mcp.internal:8000"
        }
        with patch(
            "coreason_ecosystem.gateway.master_mcp.registry.get_epistemic_status",
            new_callable=AsyncMock,
        ) as mock_status:
            mock_status.return_value = "PUBLISHED"
            import os

            with patch.dict(os.environ, {"MESH_SECRET": "test_secret"}):  # nosec B105
                res = await federated_discovery(arguments)
                import json

                data = json.loads(res)
                assert len(data["capabilities"]) == 1
                assert (
                    data["capabilities"][0]["urn"]
                    == "urn:coreason:oracle:clinical_extractor:internal"
                )
                assert "token" in data["capabilities"][0]


@pytest.mark.asyncio
async def test_federated_discovery_rejects_domain() -> None:
    from coreason_ecosystem.gateway.master_mcp import federated_discovery

    arguments = {"domain_filter": ["external"], "minimum_epistemic_status": "DRAFT"}
    with patch(
        "coreason_ecosystem.gateway.master_mcp.epistemic_transmuter.project_capabilities",
        new_callable=AsyncMock,
    ) as mock_proj:
        mock_proj.return_value = {
            "urn:coreason:oracle:clinical_extractor:internal": "http://svc-pubmed-mcp.internal:8000"
        }
        with patch(
            "coreason_ecosystem.gateway.master_mcp.registry.get_epistemic_status",
            new_callable=AsyncMock,
        ) as mock_status:
            mock_status.return_value = "PUBLISHED"
            res = await federated_discovery(arguments)
            import json

            data = json.loads(res)
            assert len(data["capabilities"]) == 0


@pytest.mark.asyncio
async def test_federated_discovery_rejects_epistemic_status() -> None:
    from coreason_ecosystem.gateway.master_mcp import federated_discovery

    arguments = {"domain_filter": [], "minimum_epistemic_status": "PUBLISHED"}
    with patch(
        "coreason_ecosystem.gateway.master_mcp.epistemic_transmuter.project_capabilities",
        new_callable=AsyncMock,
    ) as mock_proj:
        mock_proj.return_value = {
            "urn:coreason:oracle:clinical_extractor:internal": "http://svc-pubmed-mcp.internal:8000"
        }
        with patch(
            "coreason_ecosystem.gateway.master_mcp.registry.get_epistemic_status",
            new_callable=AsyncMock,
        ) as mock_status:
            mock_status.return_value = "DRAFT"
            res = await federated_discovery(arguments)
            import json

            data = json.loads(res)
            assert len(data["capabilities"]) == 0


@pytest.mark.asyncio
async def test_hydrate_registry_fallback() -> None:
    from coreason_ecosystem.gateway.master_mcp import _hydrate_registry

    with (
        patch("pathlib.Path") as mock_path,
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.initialize",
            new_callable=AsyncMock,
        ),
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.hydrate_from_matrix",
            new_callable=AsyncMock,
        ) as mock_hydrate,
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.scan_action_space_modules",
            new_callable=AsyncMock,
        ) as mock_scan,
    ):
        primary_mock = MagicMock()
        primary_mock.exists.return_value = False
        fallback_mock = MagicMock()
        fallback_mock.exists.return_value = True
        mock_path.side_effect = [primary_mock, fallback_mock]

        await _hydrate_registry()
        mock_hydrate.assert_awaited_once_with(fallback_mock)
        mock_scan.assert_awaited_once()


@pytest.mark.asyncio
async def test_hydrate_registry_fatal() -> None:
    from coreason_ecosystem.gateway.master_mcp import _hydrate_registry

    with (
        patch("pathlib.Path") as mock_path,
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.initialize",
            new_callable=AsyncMock,
        ),
    ):
        primary_mock = MagicMock()
        primary_mock.exists.return_value = False
        fallback_mock = MagicMock()
        fallback_mock.exists.return_value = False
        mock_path.side_effect = [primary_mock, fallback_mock]

        with pytest.raises(RuntimeError, match="Epistemic routing table missing."):
            await _hydrate_registry()
