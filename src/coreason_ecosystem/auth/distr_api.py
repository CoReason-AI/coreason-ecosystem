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
