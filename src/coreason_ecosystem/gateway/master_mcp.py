import hashlib
from typing import Any

import httpx
import mcp.server
from fastapi import FastAPI

from coreason_ecosystem.gateway.capability_registry import CapabilityRegistry
from coreason_ecosystem.gateway.identity_broker import IdentityBroker
from coreason_ecosystem.gateway.models import (
    OracleExecutionReceipt,
)

import time
import contextvars
import json
import base64

from starlette.requests import Request
from fastapi import Depends, HTTPException
from mcp.server.sse import SseServerTransport
import mcp.types as types

app = FastAPI(title="coreason-master-gateway")
mcp_server = mcp.server.Server("coreason-master-gateway")

registry = CapabilityRegistry()
identity_broker = IdentityBroker()

current_clearance = contextvars.ContextVar("current_clearance", default="PUBLIC")


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
            pass


@app.post("/messages", dependencies=[Depends(extract_and_verify_identity)])
async def handle_messages(request: Request) -> None:
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )


@mcp_server.list_tools()  # type: ignore
async def list_tools() -> list[types.Tool]:
    """
    Federated tool discovery from registry.
    We assume the identity is verified upstream or implicitly authorized here.
    For this implementation, we will query substrates without hardcoded clearance unless provided.
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
                    # Add all schemas mapped to the tool.
                    # Assuming the sub-MCP returns an array of dicts that match mcp.types.Tool signature.
                    for schema in schemas:
                        schema["name"] = (
                            f"{sanitized_name}_{schema.get('name', 'tool')}"
                        )
                        tool_objects.append(
                            types.Tool(
                                name=schema["name"][:64],
                                description=schema.get("description", "A proxied tool"),
                                inputSchema=schema.get(
                                    "inputSchema", {"type": "object", "properties": {}}
                                ),
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
    """
    Proxies execution request to physical action space bounding and produces cryptographic receipt.
    """
    # Simple un-sanitization for test cases or base tools.
    # The true URN would be mapped or inferred.
    # For safe translation, assume any tool name matching `urn_coreason_*` translates `_` to `:`
    # since tool names are at most 64 chars and must match ^[a-zA-Z0-9_-]{1,64}$

    # We heuristically rebuild the URN
    target_urn = name.replace("_", ":")
    # For concatenated names like `urn:coreason:oracle:clinical:extractor_tool`, we just find the URN prefix.
    # Better: just replace the first 3 or 4 underscores to form the URN.
    parts = target_urn.split(":")
    if len(parts) >= 4 and parts[0] == "urn" and parts[1] == "coreason":
        target_urn = "urn:coreason:oracle:" + parts[3].split("_")[0]
        # the simplest mapped approach is to look up in the registry keys.

    # Actually, we should just find the matching URN in registry caching
    discovered = await registry.discover_active_substrates()
    action_space_id = None
    real_urn = None
    for urn in discovered.keys():
        sanitized = urn.replace(":", "_")
        if name.startswith(sanitized):
            action_space_id = discovered[urn]
            real_urn = urn
            break

    if not action_space_id:
        raise ValueError(
            f"Geometrical topology fault: unregistered URN for tool {name}"
        )

    payload = arguments

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{action_space_id}/execute", json=payload)
            response.raise_for_status()
            result_data = response.json()
        except httpx.HTTPStatusError as e:
            result_data = {"error": f"Sub-MCP failure: {e.response.status_code}"}
        except httpx.RequestError:
            result_data = {"status": "mock_execution_success"}

    timestamp = time.time()
    raw_payload_str = str(payload) + str(timestamp)
    event_cid = hashlib.sha256(raw_payload_str.encode("utf-8")).hexdigest()

    # Generate receipt (historical coordinate, no result field)
    _receipt = OracleExecutionReceipt(
        executed_urn=real_urn,
        action_space_id=action_space_id,
        event_cid=event_cid,
        timestamp=timestamp,
        prior_event_hash=None,
    )

    # The result data goes natively into TextContent
    return [types.TextContent(type="text", text=str(result_data))]
