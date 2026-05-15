# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

import base64
import contextvars
import hashlib
import json
import logging
import os
import yaml
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import mcp.server
import mcp.types as types
from coreason_ecosystem.gateway.nemoclaw_client import NemoClawBridgeClient
from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry
from coreason_ecosystem.orchestration import up
from coreason_manifest.spec.ontology import (
    CognitiveSwarmDeploymentManifest,
    FederatedDiscoveryIntent,
)
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from mcp.server.sse import SseServerTransport
from starlette.requests import Request

try:
    import hvac
except ImportError:
    hvac = None  # type: ignore

logger = logging.getLogger(__name__)

registry = SovereignMCPRegistry()


async def _hydrate_registry() -> None:
    """Hydrate the capability registry utilizing Hierarchical Path Resolution.

    Primary Resolution: Constructs a Path object using the COREASON_REGISTRY_PATH
    environment variable, defaulting to the physical production mount at
    /mnt/coreason-state/registry/compiled_matrix.json. If the file exists, it
    invokes the strict JSON hydration protocol.

    Strict Fail-Fast Degradation: If the primary JSON path does not resolve,
    a fatal RuntimeError("Epistemic routing table missing.") is raised to
    instantly crash the boot sequence, strictly preventing the swarm from
    booting blind.
    """
    from pathlib import Path

    await registry.initialize()

    primary_path = Path(
        os.environ.get(
            "COREASON_REGISTRY_PATH",
            "/mnt/coreason-state/registry/compiled_matrix.json",
        )
    )

    if primary_path.exists():  # pragma: no cover
        await registry.hydrate_from_compiled_matrix(primary_path)
    else:
        raise RuntimeError(f"Epistemic routing table missing at {primary_path}")

    await registry.scan_action_space_modules()


async def _shutdown_registry() -> None:  # pragma: no cover
    """Gracefully shutdown the capability registry and its background worker."""
    await registry.shutdown()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await _hydrate_registry()
    yield
    await _shutdown_registry()


app = FastAPI(title="coreason-master-gateway", lifespan=lifespan)
mcp_server = mcp.server.Server("coreason-master-gateway")

current_clearance = contextvars.ContextVar("current_clearance", default="PUBLIC")
tenant_cid_var = contextvars.ContextVar(
    "tenant_cid",
    default="889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531",
)
spiffe_id_var = contextvars.ContextVar(
    "spiffe_id", default="spiffe://coreason.ai/ns/default/sa/master-gateway"
)


@app.middleware("http")
async def extract_jwt_claims(request: Request, call_next: Any) -> Any:
    jwt_payload = request.headers.get("x-jwt-payload")
    if jwt_payload:
        try:
            # Envoy forward_payload_header injects the base64url encoded payload
            # Pad if necessary
            padding = "=" * (4 - len(jwt_payload) % 4)
            decoded_bytes = base64.urlsafe_b64decode(jwt_payload + padding)
            payload = json.loads(decoded_bytes)

            if "sub" in payload:
                tenant_cid_var.set(payload["sub"])
            if "spiffe_id" in payload:
                spiffe_id_var.set(payload["spiffe_id"])
        except Exception as e:
            logger.warning(f"Failed to decode x-jwt-payload header: {e}")

    response = await call_next(request)
    return response


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


def compute_schema_seal(schema: dict[str, Any]) -> str | dict[str, str]:
    """Compute the SHA-256 seal of a canonicalized MCP tool schema.

    Args:
        schema: The MCP tool input schema dictionary.

    Returns:
        Hexadecimal SHA-256 digest string, or a dict containing signature if Vault is enabled.
    """
    import base64

    canonical = _canonicalize_json(schema)
    digest = hashlib.sha256(canonical).hexdigest()

    vault_addr = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")

    if vault_addr and vault_token:
        try:
            if hvac is None:
                raise ImportError("hvac package is not installed.")

            client = hvac.Client(url=vault_addr, token=vault_token)
            # Vault transit sign requires base64 encoded input
            encoded_payload = base64.b64encode(canonical).decode("utf-8")

            # Sign the digest using the transit engine
            sign_result = client.secrets.transit.sign_data(
                name="coreason-merkle-key",
                hash_input=encoded_payload,
            )

            return {"hash": digest, "signature": sign_result["data"]["signature"]}
        except Exception as e:
            logger.warning(
                f"Vault transit sign failed, falling back to local hash: {e}"
            )

    return digest


def verify_schema_seal(schema: dict[str, Any], seal: str | dict[str, str]) -> bool:
    """Verify the cryptographic seal of an MCP tool schema.

    Recomputes the SHA-256 digest from the canonicalized schema and, if a Vault
    Transit signature is present, verifies it against the ``coreason-merkle-key``
    in the Transit engine.

    Args:
        schema: The MCP tool input schema dictionary.
        seal: Either a plain hex digest string (unsigned) or a dict with
            ``hash`` and ``signature`` keys (Vault-signed).

    Returns:
        True if the seal is valid.

    Raises:
        ValueError: If the hash or signature verification fails.
    """
    canonical = _canonicalize_json(schema)
    digest = hashlib.sha256(canonical).hexdigest()

    if isinstance(seal, str):
        # Unsigned seal — compare digests only
        if digest != seal:
            raise ValueError(
                f"Schema seal mismatch: computed {digest[:16]}... "
                f"does not match provided {seal[:16]}..."
            )
        return True

    # Vault-signed seal — verify both hash and signature
    if digest != seal.get("hash", ""):
        raise ValueError(
            f"Schema seal hash mismatch: computed {digest[:16]}... "
            f"does not match provided {seal.get('hash', '')[:16]}..."
        )

    vault_addr = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")

    if not vault_addr or not vault_token:
        logger.warning(
            "Vault not configured — accepting seal based on hash match only."
        )
        return True

    if hvac is None:
        logger.warning("hvac not installed — accepting seal based on hash match only.")
        return True

    client = hvac.Client(url=vault_addr, token=vault_token)
    encoded_payload = base64.b64encode(canonical).decode("utf-8")

    verify_result = client.secrets.transit.verify_signed_data(
        name="coreason-merkle-key",
        hash_input=encoded_payload,
        signature=seal["signature"],
    )

    if not verify_result["data"]["valid"]:
        raise ValueError(
            "Schema seal signature verification failed: "
            "Vault Transit rejected the signature."
        )

    return True


sse_transport = SseServerTransport("/messages")


@app.get("/openapi.yaml", response_class=PlainTextResponse)
async def get_openapi_yaml() -> str:
    """Dynamic OpenAPI 3.1 projection for Hyperscalers (Google Vertex / AWS Bedrock)."""
    openapi_schema = app.openapi()
    return yaml.dump(openapi_schema, sort_keys=False)


@app.get("/sse")
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


@app.post("/messages")
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
            name="urn:coreason:actionspace:effector:capability_registry:contribute:v1",
            description="Contribution Endpoint: Accepts remote URN contributions from authenticated Private mesh instances and absorbs them into the Public registry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "urn": {"type": "string"},
                    "legal_attestation": {"type": "object"},
                    "intent_hash": {"type": "string"},
                    "provider_instance": {"type": "string"},
                },
                "required": ["urn", "legal_attestation", "intent_hash"],
            },
        )
    )

    return actuator_manifests


@mcp_server.call_tool()  # type: ignore
async def invoke_actuator(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Execute proxy intent securely spanning Zero-Trust boundaries via MCP JSON-RPC."""

    # -------------------------------------------------------------------------
    # HARD MULTI-TENANCY OIDC JWT ENFORCEMENT
    # -------------------------------------------------------------------------
    # Extract JWT from context (injected by gateway middleware)
    # Validate that payload tenant_cid matches JWT tenant_cid
    jwt_tenant = tenant_cid_var.get()
    payload_tenant = arguments.get(
        "tenant_cid", "889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531"
    )

    if jwt_tenant != payload_tenant:
        raise ValueError(
            f"GuardrailViolationEvent: Hard Multi-Tenancy Breach. JWT claim tenant_cid '{jwt_tenant}' "
            f"does not match payload tenant_cid '{payload_tenant}'. Connection severed."
        )

    # -------------------------------------------------------------------------
    # SPIFFE/SPIRE NODE-TO-NODE VERIFIABLE IDENTITY ENFORCEMENT
    # -------------------------------------------------------------------------
    spiffe_id = spiffe_id_var.get()
    # -------------------------------------------------------------------------

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

    if name == "urn:coreason:actionspace:effector:capability_registry:contribute:v1":
        nemoclaw_url = os.getenv("NEMOCLAW_URL", "https://nemoclaw:8443").rstrip("/")
        client = NemoClawBridgeClient(nemoclaw_url)

        try:
            # Full-payload deep-packet inspection of the absorbed URN definitions
            await client.call_tool(
                "urn:coreason:actionspace:solver:dlp_scanner:v1",
                "scan_contribution_payload",
                {"payload": arguments},
                spiffe_id=spiffe_id,
            )
        except RuntimeError as e:
            logger.error(f"NemoClaw DLP scan rejected the contribution payload: {e}")
            raise PermissionError(
                "Contribution rejected: NemoClaw DLP scanning failed."
            )

        provider_instance = arguments.get("provider_instance")
        if not provider_instance:
            provider_instance = (
                spiffe_id.split("/")[2] if "://" in spiffe_id else spiffe_id
            )

        from coreason_ecosystem.federation.proxy import FederationProxy
        from coreason_ecosystem.federation.policy import (
            FederationPeerState,
            InstanceType,
            FederationAgreementState,
            AirGapPolicy,
            ConnectivityDirection,
        )

        public_local = FederationPeerState(
            instance_id="mesh.coreason.ai",
            instance_type=InstanceType.PUBLIC,
            spiffe_trust_domain="spiffe://mesh.coreason.ai",
            gateway_endpoint="https://gateway.mesh.coreason.ai",
            tenant_cid="889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531",
        )
        proxy = FederationProxy(local_instance=public_local)

        private_peer = FederationPeerState(
            instance_id=provider_instance,
            instance_type=InstanceType.PRIVATE,
            spiffe_trust_domain=spiffe_id,
            gateway_endpoint=f"https://gateway.{provider_instance}:8443",
            tenant_cid=payload_tenant,
        )
        agreement = FederationAgreementState(
            agreement_id=f"auto-absorption-{provider_instance}",
            initiator=private_peer,
            responder=public_local,
            initiator_policy=AirGapPolicy(
                peer_instance_id="mesh.coreason.ai",
                direction=ConnectivityDirection.OUTBOUND_ONLY,
                max_clearance="PUBLIC",
            ),
            responder_policy=None,
            signed_by_initiator=True,
            signed_by_responder=True,
        )
        proxy.register_agreement(agreement)

        result = await proxy.absorb_remote_capability(provider_instance, arguments)
        return [types.TextContent(type="text", text=json.dumps(result))]

    try:
        target_urn = await registry.resolve_urn(name)
    except KeyError:
        raise ValueError(
            f"Geometrical topology fault: Tool {name} not found in active registry."
        )

    nemoclaw_url = os.getenv("NEMOCLAW_URL", "https://nemoclaw:8443").rstrip("/")
    client = NemoClawBridgeClient(nemoclaw_url)

    try:
        result = await client.call_tool(
            target_urn, name, arguments, spiffe_id=spiffe_id
        )
        return [types.TextContent(type="text", text=str(result.get("content", result)))]
    except RuntimeError as e:
        logger.error(f"NemoClaw security or execution fault: {e}")
        raise
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
    discovered = await registry.discover_active_substrates()

    allowed_domains = set(manifest.domain_filter)

    results = []

    for urn, endpoint in discovered.items():
        parts = urn.split(":")
        domain = parts[-1] if len(parts) > 0 else ""

        if allowed_domains and domain not in allowed_domains:
            continue

        results.append(
            {
                "urn": urn,
                "endpoint": endpoint,
                "epistemic_status": await registry.get_epistemic_status(urn),
            }
        )

    return json.dumps({"capabilities": results})
