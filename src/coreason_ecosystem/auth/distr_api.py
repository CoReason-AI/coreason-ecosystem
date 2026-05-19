# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from coreason_ecosystem.auth.distr_provisioning import (
    init_vault,
    issue_license,
    MASTER_KEY_FILE,
)

import base64
from cryptography.hazmat.primitives import serialization
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from coreason_manifest.spec.ontology import CoreasonBaseState

app = FastAPI(title="Distr License Provisioning API")

# Enable CORS for the local Vite dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IssueLicenseRequest(BaseModel):
    tenant_cid: str
    entitlements: list[str]
    valid_days: int = 365
    hardware_zk_proof: str | None = None


@app.get("/api/vault/status")
def get_vault_status() -> dict[str, Any]:
    """Check if the master key vault has been initialized."""
    return {"initialized": MASTER_KEY_FILE.exists()}


@app.post("/api/vault/init")
def initialize_vault() -> dict[str, Any]:
    """Perform the Key Generation Ceremony."""
    try:
        init_vault()
        return {
            "status": "success",
            "message": "Key Generation Ceremony Complete. Vault initialized.",
        }
    except FileExistsError:
        raise HTTPException(status_code=400, detail="Vault already initialized.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/license/issue")
def issue_new_license(request: IssueLicenseRequest) -> dict[str, Any]:
    """Issue a CommercialOverrideReceipt."""
    try:
        token = issue_license(
            tenant_cid=request.tenant_cid,
            entitlements=request.entitlements,
            valid_days=request.valid_days,
            hardware_zk_proof=request.hardware_zk_proof,
        )
        return {"status": "success", "token": token}
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Vault not initialized.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/forge/intent")
async def proxy_forge_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """
    Proxy GeometricSchemaIntent to the coreason-meta-engineering MCP server.
    Enforces Zero-Trust MCP routing through the Governance Plane.
    """
    server_params = StdioServerParameters(
        command="uv", args=["run", "mcp_server.py"], env=None
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Assuming the MCP tool is called scaffold_manifest_state or similar
                # We dynamically pass the intent payload
                result = await session.call_tool(
                    "scaffold_manifest_state", arguments={"intent": intent}
                )
                return {"status": "success", "result": result.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forge MCP routing failed: {e}")


@app.get("/.well-known/jwks.json")
def get_jwks() -> dict[str, Any]:
    """Provide the JWKS for Authlib in coreason-runtime."""
    try:
        with open(MASTER_KEY_FILE, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        x_b64 = base64.urlsafe_b64encode(public_bytes).decode("ascii").rstrip("=")
        return {
            "keys": [
                {
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": x_b64,
                    "use": "sig",
                    "kid": "master-key",
                }
            ]
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="Vault not initialized. Run key generation."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/capabilities/schema")
def get_capabilities_schema() -> dict[str, Any]:
    """Serve the CoreasonBaseState ontology JSON schema for DynamicToposRenderer."""
    return CoreasonBaseState.model_json_schema()
