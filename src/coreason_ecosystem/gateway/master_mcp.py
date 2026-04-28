import base64
import contextvars
import hashlib
import hmac
import json
import logging
import os
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
    FederatedDiscoveryIntent,
)
from coreason_ecosystem.orchestration import sync, up
from coreason_manifest.spec.ontology import (
    ChaosExperimentTask,
    CognitiveSwarmDeploymentManifest,
    FederatedSecurityMacroManifest,
)
from fastapi import Depends, FastAPI, HTTPException
from mcp.server.sse import SseServerTransport
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

    await registry.initialize()
    matrix_path = Path.cwd() / "capabilities.matrix.yaml"
    await registry.hydrate_from_matrix(matrix_path)
    await registry.scan_action_space_modules()


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
    """Federated actuator/oracle discovery projection without topological proxy coupling.

    Exposes the FederatedDiscoveryIntent capability enabling Peer-to-Peer (P2P) agent runtime
    connections to strict Zero-Trust boundaries alongside core macro-manifest deployment tools.
    """
    actuator_manifests: list[types.Tool] = []

    actuator_manifests.append(
        types.Tool(
            name="federated_discovery",
            description="Discovery-Only Endpoint: Resolves capabilities matching a domain filter and returns P2P routing boundaries.",
            inputSchema=FederatedDiscoveryIntent.model_json_schema(),
        )
    )

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
    """Execute proxy intent securely spanning Zero-Trust boundaries or resolve P2P topologies.

    Execution strictly enforces logical isolation boundaries. For federated discovery, returns
    physical network bounds and Epistemic Seals for direct P2P connections.
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
    if name == "federated_discovery":
        res_text = await federated_discovery(arguments)
        return [types.TextContent(type="text", text=res_text)]

    raise ValueError(
        f"Geometrical topology fault: unregistered tool {name} or direct proxy strictly forbidden under Hollow Plane architecture."
    )


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


async def federated_discovery(arguments: dict[str, Any]) -> str:
    """Resolve P2P capabilities using domain filters and generate Epistemic Seals.

    Resolves matching capabilities from the decentralized registry and signs
    Zero-Trust P2P tokens bounding the network connection.

    Args:
        arguments: FederatedDiscoveryIntent validated inputs.

    Returns:
        JSON serialized string containing the list of physical boundaries
        and their cryptographically signed tokens.
    """
    manifest = FederatedDiscoveryIntent.model_validate(arguments)
    clearance = current_clearance.get()

    discovered = await registry.discover_active_substrates(agent_clearance=clearance)

    # We apply epistemic filter constraints just like the old loop
    discovered = epistemic_transmuter.project_capabilities(
        available_urns=discovered,
    )

    allowed_domains = set(manifest.domain_filter)

    results = []
    secret = os.environ.get("MESH_SECRET", "coreason_mesh_secret").encode("utf-8")

    status_ranks = {"DRAFT": 0, "SRB_APPROVED": 1, "CLIENT_APPROVED": 2, "PUBLISHED": 3}
    min_rank = status_ranks.get(manifest.minimum_epistemic_status, 0)

    for urn, endpoint in discovered.items():
        epistemic_status = await registry.get_epistemic_status(urn)
        current_rank = status_ranks.get(epistemic_status, 0)

        if current_rank < min_rank:
            continue

        parts = urn.split(":")
        domain = parts[-1] if len(parts) > 0 else ""

        if allowed_domains and domain not in allowed_domains:
            continue

        payload = f"{urn}:{endpoint}:{clearance}:{int(time.time())}"
        signature = hmac.new(
            secret, payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        seal = f"{payload}:{signature}"

        results.append(
            {
                "urn": urn,
                "endpoint": endpoint,
                "token": seal,
                "epistemic_status": epistemic_status,
            }
        )

    return json.dumps({"capabilities": results})
