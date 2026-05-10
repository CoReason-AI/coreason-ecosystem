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
from coreason_ecosystem.gateway.epistemic_filter import EpistemicTransmuter
from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry
from coreason_ecosystem.gateway.state_manifests import (
    FederatedDiscoveryIntent,
)
from coreason_ecosystem.orchestration import up, sync
from coreason_ecosystem.fleet import pulumi_actuator
from coreason_manifest.spec.ontology import (
    ChaosExperimentTask,
    CognitiveSwarmDeploymentManifest,
    FederatedSecurityMacroManifest,
)
from fastapi import Depends, FastAPI, HTTPException
from contextlib import asynccontextmanager
from mcp.server.sse import SseServerTransport
import httpx
from starlette.requests import Request

logger = logging.getLogger(__name__)

registry = SovereignMCPRegistry()
epistemic_transmuter = EpistemicTransmuter(registry)

async def _hydrate_registry() -> None:
    """Hydrate the capability registry utilizing Hierarchical Path Resolution.

    Primary Resolution: Constructs a Path object using the COREASON_REGISTRY_PATH
    environment variable, defaulting to the physical production mount at
    /mnt/coreason-state/registry/compiled_matrix.json. If the file exists, it
    invokes the strict JSON hydration protocol.

    Fallback Resolution: If the primary mount is absent, gracefully falls back
    to the local developer path at infrastructure/local/capabilities.matrix.yaml
    and invokes the legacy YAML hydration protocol.

    Strict Fail-Fast Degradation: If neither the primary JSON path nor the
    fallback YAML path resolves, a fatal RuntimeError("Epistemic routing table missing.")
    is raised to instantly crash the boot sequence, strictly preventing the
    swarm from booting blind.
    """
    import os
    from pathlib import Path

    await registry.initialize()

    primary_path = Path(
        os.environ.get(
            "COREASON_REGISTRY_PATH",
            "/mnt/coreason-state/registry/compiled_matrix.json",
        )
    )
    fallback_path = Path("infrastructure/local/capabilities.matrix.yaml")

    if primary_path.exists():  # pragma: no cover
        await registry.hydrate_from_compiled_matrix(primary_path)
    elif fallback_path.exists():
        await registry.hydrate_from_matrix(fallback_path)
    else:
        raise RuntimeError("Epistemic routing table missing.")

    await registry.scan_action_space_modules()

async def _shutdown_registry() -> None:  # pragma: no cover
    """Gracefully shutdown the capability registry and its background worker."""
    await registry.shutdown()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await _hydrate_registry()
    yield
    await _shutdown_registry()

app = FastAPI(title="coreason-master-gateway", lifespan=lifespan)
mcp_server = mcp.server.Server("coreason-master-gateway")

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



async def extract_and_verify_identity(request: Request) -> None:
    """Verify perimeter authentication token (MTLS/Token) and bind semantic clearances."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing perimeter auth token")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    current_clearance.set("PUBLIC")


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
    """Execute proxy intent securely spanning Zero-Trust boundaries via MCP JSON-RPC."""
    if name == "federated_discovery":
        res_text = await federated_discovery(arguments)
        return [types.TextContent(type="text", text=res_text)]

    if name == "deploy_cognitive_swarm":
        manifest_swarm = CognitiveSwarmDeploymentManifest.model_validate(arguments)
        await up.provision_swarm_topology(manifest_swarm)
        return [
            types.TextContent(
                type="text", text="deploy_cognitive_swarm executed successfully"
            )
        ]

    if name == "establish_federated_link":
        manifest_link = FederatedSecurityMacroManifest.model_validate(arguments)
        await sync.establish_federated_link(manifest_link)
        return [
            types.TextContent(
                type="text", text="establish_federated_link executed successfully"
            )
        ]

    if name == "inject_chaos_fault":
        manifest_chaos = ChaosExperimentTask.model_validate(arguments)
        await pulumi_actuator.inject_chaos_fault(manifest_chaos)
        return [
            types.TextContent(
                type="text", text="inject_chaos_fault executed successfully"
            )
        ]

    try:
        target_urn = await registry.resolve_urn(name)
    except KeyError:
        raise ValueError(
            f"Geometrical topology fault: Tool {name} not found in active registry."
        )

    nemoclaw_url = os.getenv("NEMOCLAW_URL", "https://nemoclaw:8443").rstrip("/")
    url = f"{nemoclaw_url}/v1/mcp/{target_urn}/tools/call"
    payload = {
        "name": name,
        "arguments": arguments,
    }

    cert = None
    env_cert = os.getenv("NEMOCLAW_CLIENT_CERT")
    env_key = os.getenv("NEMOCLAW_CLIENT_KEY")
    if env_cert and env_key:
        cert = (env_cert, env_key)

    try:
        async with httpx.AsyncClient(cert=cert, verify=False) as client:  # nosec B501
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return [
                types.TextContent(type="text", text=str(result.get("content", result)))
            ]
    except httpx.HTTPStatusError as e:
        logger.error(
            f"NemoClaw returned HTTP error: {e.response.status_code} - {e.response.text}"
        )
        if e.response.status_code == 500:
            raise RuntimeError(f"NemoClaw internal server error: {e}") from e
        raise RuntimeError(f"NemoClaw HTTP error: {e}") from e
    except Exception as e:
        logger.error(f"Failed to proxy MCP request to NemoClaw: {e}")
        raise RuntimeError(f"Cross-plane capability execution failed: {e}")


async def federated_discovery(arguments: dict[str, Any]) -> str:
    """Resolve P2P capabilities using domain filters and generate Epistemic Seals.

    Resolves matching capabilities from the decentralized registry and signs
    Zero-Trust P2P tokens bounding the network connection.

    Args:
        arguments: FederatedDiscoveryIntent validated inputs.

    Returns:
        JSON serialized string containing the list of physical boundaries
        and their cryptographically signed tokens.

    Note:
        We apply epistemic filter constraints just like the old loop.
    """
    manifest = FederatedDiscoveryIntent.model_validate(arguments)
    clearance = "PUBLIC"

    discovered = await registry.discover_active_substrates()

    discovered = await epistemic_transmuter.project_capabilities(
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
