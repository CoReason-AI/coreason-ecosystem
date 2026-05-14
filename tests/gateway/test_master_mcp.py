import typing
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from coreason_ecosystem.gateway.master_mcp import (
    app,
    list_actuators,
    invoke_actuator,
    federated_discovery,
    registry,
    compute_schema_seal,
    _hydrate_registry,
)
import respx
import httpx
from hypothesis import given, settings, strategies as st


def _seed_registry() -> None:
    """Seed the registry with test capabilities for the test suite."""
    registry._mock_state = {  # type: ignore[attr-defined]
        "urn:coreason:actionspace:solver:clinical_extractor:v1": {
            "endpoint": "http://svc-pubmed-mcp.internal:8000",
            "clearance": "PUBLIC",
        },
        "urn:coreason:actionspace:solver:mathematics:v1": {
            "endpoint": "http://svc-math-mcp.internal:8000",
            "clearance": "CONFIDENTIAL",
        },
        "urn:coreason:actionspace:oracle:milvus:v1": {
            "endpoint": "http://coreason-milvus-mcp:8000",
            "clearance": "CONFIDENTIAL",
        },
        "urn:coreason:actionspace:oracle:neo4j:v1": {
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
async def test_compute_schema_seal_vault_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that schema sealing integrates with Vault transit engine."""
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}

    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "test-token")

    with patch("hvac.Client") as mock_vault_class:
        mock_client = mock_vault_class.return_value
        mock_client.secrets.transit.sign_data.return_value = {
            "data": {"signature": "vault:v1:test-signature"}
        }

        seal = compute_schema_seal(schema)

        assert isinstance(seal, dict)
        assert "hash" in seal
        assert seal["signature"] == "vault:v1:test-signature"
        mock_client.secrets.transit.sign_data.assert_called_once()


@pytest.mark.asyncio
async def test_compute_schema_seal_vault_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that schema sealing falls back to local hash if Vault fails."""
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}

    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "test-token")

    with patch("hvac.Client") as mock_vault_class:
        mock_client = mock_vault_class.return_value
        mock_client.secrets.transit.sign_data.side_effect = Exception("Vault down")

        seal = compute_schema_seal(schema)

        assert isinstance(seal, str)
        assert len(seal) == 64  # Fell back to SHA-256 hex digest


@pytest.mark.asyncio
async def test_sse_endpoint_direct() -> None:
    from coreason_ecosystem.gateway.master_mcp import handle_sse

    from fastapi import Request

    request = Request({"type": "http"}, receive=AsyncMock(), send=AsyncMock())

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

    from fastapi import Request

    request = Request({"type": "http"}, receive=AsyncMock(), send=AsyncMock())

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

    from fastapi import Request

    request = Request({"type": "http"}, receive=AsyncMock(), send=AsyncMock())

    with patch(
        "coreason_ecosystem.gateway.master_mcp.sse_transport.handle_post_message",
        new_callable=AsyncMock,
    ) as mock_handle:
        await handle_messages(request)
        mock_handle.assert_called_once()


@pytest.mark.asyncio
async def test_openapi_yaml_endpoint(client: TestClient) -> None:
    """Test the dynamic OpenAPI 3.1 YAML projection endpoint."""
    response = client.get("/openapi.yaml")
    assert response.status_code == 200
    assert "openapi:" in response.text
    assert "info:" in response.text


@pytest.mark.asyncio
async def test_list_actuators() -> None:
    """Test that list_actuators returns the built-in capabilities."""
    tools = await list_actuators()
    assert len(tools) == 2
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
async def test_invoke_actuator_tenant_mismatch() -> None:
    """Test that a mismatch between JWT tenant_cid and payload tenant_cid raises a ValueError."""
    from coreason_ecosystem.gateway.master_mcp import invoke_actuator

    # We set the jwt_tenant via ContextVar logic (or rely on default if unchanged)
    # The default is "889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531"
    arguments = {"tenant_cid": "invalid_tenant_12345", "query": "test"}

    with pytest.raises(ValueError, match="Hard Multi-Tenancy Breach"):
        await invoke_actuator(name="deploy_cognitive_swarm", arguments=arguments)


@pytest.mark.asyncio
async def test_invoke_actuator_builtin_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # deploy_cognitive_swarm
    with (
        patch(
            "coreason_ecosystem.orchestration.up.provision_swarm_topology",
            new_callable=AsyncMock,
        ) as mock_up,
        patch(
            "coreason_ecosystem.gateway.master_mcp.CognitiveSwarmDeploymentManifest.model_validate"
        ),
    ):
        args = {"any": "thing"}
        res = await invoke_actuator("deploy_cognitive_swarm", args)
        assert len(res) == 1
        assert "executed successfully" in res[0].text
        mock_up.assert_called_once()


@respx.mock
@pytest.mark.asyncio
async def test_invoke_actuator_nemoclaw_routing() -> None:
    with patch(
        "coreason_ecosystem.gateway.master_mcp.registry.resolve_urn",
        new_callable=AsyncMock,
    ) as mock_res:
        mock_res.return_value = "urn:coreason:oracle:clinical_extractor"
        # It routes through NemoClaw
        respx.post(
            "https://nemoclaw:8443/v1/mcp/urn:coreason:oracle:clinical_extractor/tools/call"
        ).mock(return_value=httpx.Response(200, json={"content": "nemoclaw_success"}))
        res = await invoke_actuator(
            "urn:coreason:oracle:clinical_extractor", {"arg": "val"}
        )
        assert res[0].text == "nemoclaw_success"


@respx.mock
@pytest.mark.asyncio
async def test_invoke_actuator_nemoclaw_exceptions() -> None:
    with patch(
        "coreason_ecosystem.gateway.master_mcp.registry.resolve_urn",
        new_callable=AsyncMock,
    ) as mock_res:
        mock_res.side_effect = lambda urn: urn
        respx.post(
            "https://nemoclaw:8443/v1/mcp/urn:coreason:oracle:clinical_extractor/tools/call"
        ).mock(return_value=httpx.Response(500, json={"error": "internal"}))
        with pytest.raises(
            RuntimeError, match="Cross-plane capability execution failed"
        ):
            await invoke_actuator(
                "urn:coreason:oracle:clinical_extractor", {"arg": "val"}
            )

        respx.post(
            "https://nemoclaw:8443/v1/mcp/urn:coreason:oracle:mathematics/tools/call"
        ).mock(return_value=httpx.Response(400, json={"error": "bad"}))
        with pytest.raises(RuntimeError, match="Security Policy Violation"):
            await invoke_actuator("urn:coreason:oracle:mathematics", {"arg": "val"})

        respx.post(
            "https://nemoclaw:8443/v1/mcp/urn:coreason:oracle:milvus/tools/call"
        ).mock(side_effect=httpx.ConnectError("Network"))
        with pytest.raises(
            RuntimeError, match="Cross-plane capability execution failed"
        ):
            await invoke_actuator("urn:coreason:oracle:milvus", {"arg": "val"})


@pytest.mark.asyncio
async def test_federated_discovery_builtin() -> None:
    with (
        patch(
            "coreason_ecosystem.gateway.master_mcp.FederatedDiscoveryIntent.model_validate"
        ),
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.discover_active_substrates",
            new_callable=AsyncMock,
        ) as mock_disc,
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.get_epistemic_status",
            new_callable=AsyncMock,
        ) as mock_stat,
    ):
        mock_disc.return_value = {
            "urn:coreason:oracle:clinical_extractor": "http://foo"
        }
        mock_stat.return_value = "DRAFT"

        res = await invoke_actuator(
            "federated_discovery",
            {
                "domain_filter": ["clinical_extractor"],
                "minimum_epistemic_status": "DRAFT",
            },
        )
        assert "capabilities" in res[0].text
        assert "clinical_extractor" in res[0].text


@pytest.mark.asyncio
async def test_federated_discovery_filtering() -> None:
    # Test domain filtering directly
    with (
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.discover_active_substrates",
            new_callable=AsyncMock,
        ) as mock_disc,
        patch(
            "coreason_ecosystem.gateway.master_mcp.FederatedDiscoveryIntent.model_validate"
        ) as mock_val,
    ):
        mock_disc.return_value = {
            "urn:coreason:oracle:mathematics": "http://foo",
            "urn:coreason:oracle:physics": "http://bar",
        }
        # physics will be filtered out due to domain filter
        mock_val.return_value.domain_filter = ["mathematics"]
        mock_val.return_value.minimum_epistemic_status = "DRAFT"

        res = await federated_discovery(
            {"domain_filter": ["mathematics"], "minimum_epistemic_status": "DRAFT"}
        )
        import json

        data = json.loads(res)
        assert len(data["capabilities"]) == 1
        assert "mathematics" in data["capabilities"][0]["urn"]

        # Test domain mismatch filter (line 314)
        mock_val.return_value.domain_filter = ["biology"]
        mock_val.return_value.minimum_epistemic_status = "DRAFT"
        res2 = await federated_discovery(
            {"domain_filter": ["biology"], "minimum_epistemic_status": "DRAFT"}
        )
        data2 = json.loads(res2)
        assert len(data2["capabilities"]) == 0


@pytest.mark.asyncio
async def test_hydrate_registry() -> None:
    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.initialize",
            new_callable=AsyncMock,
        ),
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.hydrate_from_compiled_matrix",
            new_callable=AsyncMock,
        ) as mock_hydrate_json,
        patch(
            "coreason_ecosystem.gateway.master_mcp.registry.scan_action_space_modules",
            new_callable=AsyncMock,
        ),
    ):
        # Scenario 1: Primary exists
        mock_exists.return_value = True

        await _hydrate_registry()
        mock_hydrate_json.assert_called_once()

        # Scenario 2: Missing -> Exception
        mock_exists.return_value = False

        with pytest.raises(RuntimeError, match="Epistemic routing table missing."):
            await _hydrate_registry()


@settings(max_examples=10)
@given(domain=st.from_regex(r"^[a-zA-Z0-9_-]+$", fullmatch=True))
@pytest.mark.asyncio
async def test_federated_discovery_hypothesis(domain: str) -> None:
    with patch(
        "coreason_ecosystem.gateway.master_mcp.FederatedDiscoveryIntent.model_validate"
    ) as mock_val:
        mock_val.return_value.domain_filter = [domain]
        mock_val.return_value.minimum_epistemic_status = "DRAFT"
        # A generic test verifying hypothesis fuzzing of domains
        res = await federated_discovery(
            {"domain_filter": [domain], "minimum_epistemic_status": "DRAFT"}
        )
        import json

        data = json.loads(res)
        # The seeded registry has specific domains, so most fuzzed domains will return 0 capabilities unless matched
        assert isinstance(data["capabilities"], list)


@pytest.mark.asyncio
async def test_lifespan() -> None:
    from coreason_ecosystem.gateway.master_mcp import lifespan, app

    with (
        patch(
            "coreason_ecosystem.gateway.master_mcp._hydrate_registry",
            new_callable=AsyncMock,
        ) as mock_hydrate,
        patch(
            "coreason_ecosystem.gateway.master_mcp._shutdown_registry",
            new_callable=AsyncMock,
        ) as mock_shutdown,
    ):
        async with lifespan(app):
            mock_hydrate.assert_awaited_once()
        mock_shutdown.assert_awaited_once()
