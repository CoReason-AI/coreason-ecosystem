import base64
import contextvars
import hashlib
import json
import logging
import time
from typing import Any

import mcp.server
import mcp.types as types
from coreason_ecosystem.fleet import pulumi_actuator
from coreason_ecosystem.gateway.epistemic_filter import EpistemicTransmuter
from coreason_ecosystem.gateway.ontological_identity_router import (
    OntologicalIdentityRouter,
)
from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry
from coreason_ecosystem.gateway.state_manifests import (
    OracleExecutionReceipt,
)
from coreason_ecosystem.orchestration import sync, up
from coreason_ecosystem.utils.telemetry import emit_span_event
from coreason_manifest.spec.ontology import (
    ChaosExperimentTask,
    CognitiveSwarmDeploymentManifest,
    FederatedSecurityMacroManifest,
)
from fastapi import Depends, FastAPI, HTTPException
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.server.sse import SseServerTransport
from mcp.shared.exceptions import McpError
from starlette.requests import Request

logger = logging.getLogger(__name__)

app = FastAPI(title="coreason-master-gateway")
mcp_server = mcp.server.Server("coreason-master-gateway")

registry = SovereignMCPRegistry()
epistemic_transmuter = EpistemicTransmuter(registry)
identity_router = OntologicalIdentityRouter()

current_clearance = contextvars.ContextVar("current_clearance", default="PUBLIC")


def _canonicalize_json(obj: Any) -> bytes:
    """Produce RFC 8785 (JCS) canonical JSON serialization.

    Sorts keys recursively and uses compact separators with no trailing
    whitespace, which is the subset of JCS achievable via Python's stdlib.

    Args:
        obj: The object to canonicalize.

    Returns:
        UTF-8 encoded canonical JSON bytes.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_schema_seal(schema: dict[str, Any]) -> str:
    """Compute the SHA-256 seal of a canonicalized MCP tool schema.

    Args:
        schema: The MCP tool input schema dictionary.

    Returns:
        Hexadecimal SHA-256 digest string.
    """
    canonical = _canonicalize_json(schema)
    return hashlib.sha256(canonical).hexdigest()


@app.on_event("startup")
async def _hydrate_registry() -> None:
    """Hydrate the capability registry from the matrix file and passive discovery on startup."""
    from pathlib import Path

    matrix_path = Path.cwd() / "capabilities.matrix.yaml"
    registry.hydrate_from_matrix(matrix_path)
    registry.scan_action_space_modules()


async def extract_and_verify_identity(request: Request) -> None:
    """Verify cryptographic semantic clearances binding identity envelopes bounds."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        current_clearance.set("PUBLIC")
        return

    try:
        if not auth_header.startswith("Bearer "):
            raise ValueError("Invalid format")

        encoded_payload = auth_header[7:]
        decoded_bytes = base64.b64decode(encoded_payload)
        payload = json.loads(decoded_bytes.decode("utf-8"))

        profile = await identity_router.authorize_coordinate(payload)
        current_clearance.set(profile["clearance"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid identity sequence")


sse_transport = SseServerTransport("/messages")


@app.get("/sse", dependencies=[Depends(extract_and_verify_identity)])
async def handle_sse(request: Request) -> None:
    """Bootstrap proxy tunneling SSE execution projection capabilities bounds."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        try:
            await mcp_server.run(
                read_stream, write_stream, mcp_server.create_initialization_options()
            )
        except Exception:
            logger.debug("SSE client disconnected")


@app.post("/messages", dependencies=[Depends(extract_and_verify_identity)])
async def handle_messages(request: Request) -> None:
    """Route asynchronous inbound message payload boundaries mapping."""
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )


@mcp_server.list_tools()  # type: ignore
async def list_actuators() -> list[types.Tool]:
    """Federated actuator/oracle discovery from registry via strict SSE encapsulation limits.

    Each actuator schema is queried dynamically via the official JSON-RPC SSE protocol, bypassing old HTTP
    constraints. Latency generated here enforces stateless Zero-Trust boundary decoupling without shared topology states.
    Discovered endpoints failing initial JSON-RPC communication arrays are explicitly dropped.
    """
    clearance = current_clearance.get()
    discovered_capabilities = await registry.discover_active_substrates(
        agent_clearance=clearance
    )

    discovered_capabilities = epistemic_transmuter.project_capabilities(
        available_urns=discovered_capabilities,
    )

    actuator_manifests: list[types.Tool] = []

    for urn, endpoint in discovered_capabilities.items():
        sanitized_name = urn.replace(":", "_")
        try:
            async with sse_client(f"{endpoint}/sse") as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    response = await session.list_tools()

                    for tool in response.tools:
                        tool_name_str = f"{sanitized_name}_{tool.name}"

                        input_schema = (
                            tool.inputSchema
                            if tool.inputSchema
                            else {"type": "object", "properties": {}}
                        )
                        schema_seal = compute_schema_seal(input_schema)

                        actuator_manifests.append(
                            types.Tool(
                                name=tool_name_str[:64],
                                description=(
                                    f"{tool.description or 'A proxied actuator'} "
                                    f"[seal:{schema_seal[:16]}]"
                                ),
                                inputSchema=input_schema,
                            )
                        )
        except Exception as e:
            logger.warning(
                f"Topological absence: {urn} JSON-RPC linkage failed and will not be projected: {e}"
            )
            continue

    actuator_manifests.append(
        types.Tool(
            name="deploy_cognitive_swarm",
            description="Macro-Manifest Deployment: Deploy a cognitive swarm. Hollow Plane proxy endpoint.",
            inputSchema=CognitiveSwarmDeploymentManifest.model_json_schema(),
        )
    )
    actuator_manifests.append(
        types.Tool(
            name="establish_federated_link",
            description="Macro-Manifest Deployment: Establish federated link. Hollow Plane proxy endpoint.",
            inputSchema=FederatedSecurityMacroManifest.model_json_schema(),
        )
    )
    actuator_manifests.append(
        types.Tool(
            name="inject_chaos_fault",
            description="Macro-Manifest Deployment: Inject chaos fault. Hollow Plane proxy endpoint.",
            inputSchema=ChaosExperimentTask.model_json_schema(),
        )
    )

    return actuator_manifests


@mcp_server.call_tool()  # type: ignore
async def invoke_actuator(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Execute proxy intent securely spanning Zero-Trust boundaries converting payloads directly via SSE JSON-RPC.

    Execution strictly utilizes fresh `ClientSession` structures for independent transactions guaranteeing
    no persistent token cross-contamination and enforcing logical isolation boundaries at the cost of
    a small connection handshake latency.
    """
    if name == "deploy_cognitive_swarm":
        res = await deploy_cognitive_swarm(arguments)
        return [types.TextContent(type="text", text=res)]
    if name == "establish_federated_link":
        res = await establish_federated_link(arguments)
        return [types.TextContent(type="text", text=res)]
    if name == "inject_chaos_fault":
        res = await inject_chaos_fault(arguments)
        return [types.TextContent(type="text", text=res)]

    discovered = await registry.discover_active_substrates()
    endpoint_url: str | None = None
    real_urn: str | None = None
    for urn in discovered.keys():
        sanitized = urn.replace(":", "_")
        if name.startswith(sanitized):
            endpoint_url = discovered[urn]
            real_urn = urn
            break

    if not endpoint_url or not real_urn:
        raise ValueError(
            f"Geometrical topology fault: unregistered URN for tool {name}"
        )

    sanitized_name = real_urn.replace(":", "_")
    original_tool_name = (
        name[len(sanitized_name) + 1 :]
        if name.startswith(sanitized_name + "_")
        else name
    )

    payload = arguments
    execution_start = time.time()
    result_data: Any = None

    try:
        async with sse_client(f"{endpoint_url}/sse") as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.call_tool(
                    original_tool_name, arguments=payload
                )
                result_data = [c.model_dump() for c in response.content]
    except McpError as e:
        # e.error.message contains JSON-RPC error mapping
        result_data = {"error": f"Sub-MCP failure: {e.error.message if e.error else e}"}
    except Exception as e:
        raise RuntimeError(
            f"Topological Severance Event: Sub-MCP unreachable - {e}"
        ) from e

    execution_end = time.time()
    execution_time_ms = (execution_end - execution_start) * 1000

    timestamp = time.time()
    canonical_payload = _canonicalize_json({"payload": payload, "timestamp": timestamp})
    event_cid = hashlib.sha256(canonical_payload).hexdigest()

    receipt_action_space_id = real_urn.replace(":", "_")

    OracleExecutionReceipt(
        executed_urn=real_urn,
        action_space_id=receipt_action_space_id,
        event_cid=event_cid,
        timestamp=timestamp,
        prior_event_hash=None,
    )

    emit_span_event(
        name="mcp_tool_execution",
        attributes={
            "executed_urn": real_urn,
            "action_space_id": receipt_action_space_id,
            "execution_time_ms": execution_time_ms,
        },
    )

    return [types.TextContent(type="text", text=str(result_data))]


async def deploy_cognitive_swarm(arguments: dict[str, Any]) -> str:
    """Macro-Manifest Deployment: Deploy a cognitive swarm. Hollow Plane proxy endpoint."""
    logger.info("Proxying deploy_cognitive_swarm intent to fleet module.")
    manifest = CognitiveSwarmDeploymentManifest.model_validate(arguments)
    await up.provision_swarm_topology(manifest)  # type: ignore[attr-defined]
    return "Intent proxied to fleet: deploy_cognitive_swarm"


async def establish_federated_link(arguments: dict[str, Any]) -> str:
    """Macro-Manifest Deployment: Establish federated link. Hollow Plane proxy endpoint."""
    logger.info("Proxying establish_federated_link intent to orchestration module.")
    manifest = FederatedSecurityMacroManifest.model_validate(arguments)
    await sync.establish_federated_link(manifest)  # type: ignore[attr-defined]
    return "Intent proxied to orchestration: establish_federated_link"


async def inject_chaos_fault(arguments: dict[str, Any]) -> str:
    """Macro-Manifest Deployment: Inject chaos fault. Hollow Plane proxy endpoint."""
    logger.info("Proxying inject_chaos_fault intent to fleet module.")
    manifest = ChaosExperimentTask.model_validate(arguments)
    await pulumi_actuator.inject_chaos_fault(manifest)  # type: ignore[attr-defined]
    return "Intent proxied to fleet: inject_chaos_fault"
