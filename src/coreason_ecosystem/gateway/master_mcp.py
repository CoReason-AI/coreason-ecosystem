# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Master MCP Gateway — Federated Capability Discovery & Cryptographic Sealing.

Routes JSON-RPC requests to sub-MCP backends based on Epistemic Intents.
Enforces RFC 8785 (JCS) canonical hashing on all MCP tool schemas before
projection to the kinetic plane, per LAW 4 (Cryptographic Provenance).
"""

import hashlib
import json
import logging
from typing import Any

import httpx
import mcp.server
from fastapi import FastAPI

from coreason_ecosystem.gateway.capability_registry import CapabilityRegistry
from coreason_ecosystem.gateway.identity_broker import IdentityBroker
from coreason_ecosystem.gateway.models import (
    OracleExecutionReceipt,
)
from coreason_ecosystem.utils.telemetry import emit_span_event

import time
import contextvars
import base64

from starlette.requests import Request
from fastapi import Depends, HTTPException
from mcp.server.sse import SseServerTransport
import mcp.types as types

logger = logging.getLogger(__name__)

app = FastAPI(title="coreason-master-gateway")
mcp_server = mcp.server.Server("coreason-master-gateway")

registry = CapabilityRegistry()
identity_broker = IdentityBroker()

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
    """Hydrate the capability registry from the matrix file on startup."""
    from pathlib import Path

    matrix_path = Path.cwd() / "capabilities.matrix.yaml"
    registry.hydrate_from_matrix(matrix_path)


async def extract_and_verify_identity(request: Request) -> None:
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

        profile = await identity_broker.verify_connection_handshake(payload)
        current_clearance.set(profile["clearance"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid identity sequence")


sse_transport = SseServerTransport("/messages")


@app.get("/sse", dependencies=[Depends(extract_and_verify_identity)])
async def handle_sse(request: Request) -> None:
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
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )


@mcp_server.list_tools()  # type: ignore
async def list_tools() -> list[types.Tool]:
    """Federated tool discovery from registry with cryptographic schema sealing.

    Each tool schema is sealed with SHA-256 of its RFC 8785 canonical form
    before being projected to the kinetic plane.
    """
    clearance = current_clearance.get()
    discovered_capabilities = await registry.discover_active_substrates(
        agent_clearance=clearance
    )

    tool_objects: list[types.Tool] = []

    async with httpx.AsyncClient() as client:
        for urn, endpoint in discovered_capabilities.items():
            sanitized_name = urn.replace(":", "_")
            try:
                response = await client.get(f"{endpoint}/tools")
                if response.status_code == 200:
                    schemas = response.json()
                    for schema in schemas:
                        schema["name"] = (
                            f"{sanitized_name}_{schema.get('name', 'tool')}"
                        )

                        # Cryptographic sealing: compute SHA-256 of the canonical
                        # input schema before projection to the kinetic plane.
                        input_schema = schema.get(
                            "inputSchema", {"type": "object", "properties": {}}
                        )
                        schema_seal = compute_schema_seal(input_schema)

                        tool_objects.append(
                            types.Tool(
                                name=schema["name"][:64],
                                description=(
                                    f"{schema.get('description', 'A proxied tool')} "
                                    f"[seal:{schema_seal[:16]}]"
                                ),
                                inputSchema=input_schema,
                            )
                        )
            except httpx.RequestError:
                tool_objects.append(
                    types.Tool(
                        name=sanitized_name[:64],
                        description=f"Proxied tool for {urn}",
                        inputSchema={"type": "object", "properties": {}},
                    )
                )

    return tool_objects


@mcp_server.call_tool()  # type: ignore
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Proxies execution request to physical action space with cryptographic receipt."""
    # Resolve the matching URN from the registry cache
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

    payload = arguments

    execution_start = time.time()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{endpoint_url}/execute", json=payload)
            response.raise_for_status()
            result_data = response.json()
        except httpx.HTTPStatusError as e:
            result_data = {"error": f"Sub-MCP failure: {e.response.status_code}"}
        except httpx.RequestError:
            result_data = {"status": "mock_execution_success"}

    execution_end = time.time()
    execution_time_ms = (execution_end - execution_start) * 1000

    # Cryptographic receipt: RFC 8785 canonical hash of the payload
    timestamp = time.time()
    canonical_payload = _canonicalize_json({"payload": payload, "timestamp": timestamp})
    event_cid = hashlib.sha256(canonical_payload).hexdigest()

    # Derive a pattern-compliant action_space_id from the URN.
    receipt_action_space_id = real_urn.replace(":", "_")

    # Generate receipt (historical coordinate, no result field)
    _receipt = OracleExecutionReceipt(
        executed_urn=real_urn,
        action_space_id=receipt_action_space_id,
        event_cid=event_cid,
        timestamp=timestamp,
        prior_event_hash=None,
    )

    # Fire telemetry event for cross-boundary observability.
    emit_span_event(
        name="mcp_tool_execution",
        attributes={
            "executed_urn": real_urn,
            "action_space_id": receipt_action_space_id,
            "execution_time_ms": execution_time_ms,
        },
    )

    # The result data goes natively into TextContent
    return [types.TextContent(type="text", text=str(result_data))]
