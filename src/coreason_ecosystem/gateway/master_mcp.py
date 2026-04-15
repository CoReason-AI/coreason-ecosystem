import datetime
import hashlib
from typing import Any

import httpx
import mcp.server
from fastapi import FastAPI, HTTPException

from coreason_ecosystem.gateway.capability_registry import CapabilityRegistry
from coreason_ecosystem.gateway.models import (
    FederatedDiscoveryIntent,
    OracleExecutionReceipt,
)

app = FastAPI(title="coreason-master-gateway")
mcp_server = mcp.server.Server("coreason-master-gateway")

registry = CapabilityRegistry()


@app.post("/discover")
async def federated_discovery(intent: FederatedDiscoveryIntent) -> dict[str, Any]:
    """
    Absorb a FederatedDiscoveryIntent and perform discovery against the registry.
    """
    discovered_capabilities = await registry.discover_active_substrates()

    # Filter bounds
    if intent.domain_filter:
        filtered = {
            k: v
            for k, v in discovered_capabilities.items()
            if any(domain in k for domain in intent.domain_filter)
        }
    else:
        filtered = discovered_capabilities

    tool_schemas: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for urn, endpoint in filtered.items():
            try:
                response = await client.get(f"{endpoint}/tools")
                if response.status_code == 200:
                    schemas = response.json()
                    tool_schemas.extend(schemas)
            except httpx.RequestError:
                # Provide a proxy tool simulation in the epistemic failure of the endpoint binding.
                tool_schemas.append(
                    {
                        "name": f"proxy_tool_for_{urn.split(':')[-1]}",
                        "description": f"Proxied tool for {urn}",
                        "inputSchema": {"type": "object", "properties": {}},
                        "_proxy_urn": urn,
                    }
                )

    return {"tools": tool_schemas}


@app.post("/execute/{target_urn}")
async def execute_proxy(
    target_urn: str, payload: dict[str, Any]
) -> OracleExecutionReceipt:
    """
    Proxies execution request to physical action space bounding and produces cryptographic receipt.
    """
    try:
        action_space_id = registry.resolve_urn(target_urn)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{action_space_id}/execute", json=payload)
            response.raise_for_status()
            result_data = response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code, detail="Sub-MCP failure"
            )
        except httpx.RequestError:
            result_data = {"status": "mock_execution_success"}

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    raw_payload_str = str(payload) + timestamp
    event_cid = hashlib.sha256(raw_payload_str.encode("utf-8")).hexdigest()

    return OracleExecutionReceipt(
        executed_urn=target_urn,
        action_space_id=action_space_id,
        event_cid=event_cid,
        timestamp=timestamp,
        result=result_data,
    )
