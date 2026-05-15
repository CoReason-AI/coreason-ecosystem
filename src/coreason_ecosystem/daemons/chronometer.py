# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

import asyncio
import os
import time
from pathlib import Path

import hvac
import requests

GENESIS_TIME_PATH = Path.cwd() / "registry" / "vault" / "genesis_time.txt"

# 30 days in seconds
SOVEREIGN_WINDOW_SECONDS = 30 * 24 * 60 * 60


def _get_genesis_time() -> float:
    """Gets or initializes the cluster instantiation time."""
    if not GENESIS_TIME_PATH.exists():
        GENESIS_TIME_PATH.parent.mkdir(parents=True, exist_ok=True)
        genesis_time = time.time()
        with open(GENESIS_TIME_PATH, "w") as f:
            f.write(str(genesis_time))
        return genesis_time

    with open(GENESIS_TIME_PATH, "r") as f:
        return float(f.read().strip())


def _has_valid_commercial_license() -> bool:
    # Borrow vs. Build: Fetch token securely via HashiCorp Vault API
    vault_url = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
    vault_token = os.environ.get("VAULT_TOKEN", "dev-only-token")

    try:
        client = hvac.Client(url=vault_url, token=vault_token)
        existing_response = client.secrets.kv.v2.read_secret_version(
            path="coreason/license", raise_on_deleted_version=False
        )
        if (
            not existing_response
            or "data" not in existing_response
            or "data" not in existing_response["data"]
        ):
            return False

        payload = existing_response["data"]["data"]
    except Exception:
        return False

    # Borrow vs. Build: Evaluate authorization logic via Open Policy Agent (OPA)
    opa_url = os.environ.get("OPA_ADDR", "http://127.0.0.1:8181")
    try:
        # POST the payload to the OPA policy endpoint
        opa_resp = requests.post(
            f"{opa_url}/v1/data/coreason/governance/license/is_sovereign",
            json={"input": payload},
            timeout=2.0,
        )
        if opa_resp.status_code == 200:
            result = opa_resp.json()
            return result.get("result", False)
        return False
    except requests.exceptions.RequestException:
        # Fallback if OPA daemon is offline
        return False


async def run_chronometer() -> None:
    """
    Continually monitors the timeline of the cluster.
    If 30 days have elapsed AND there is no valid commercial license,
    it toggles the AST Guillotine, activating auto-CLA assignment.
    """
    genesis_time = _get_genesis_time()

    while True:
        elapsed = time.time() - genesis_time

        has_license = _has_valid_commercial_license()

        if elapsed > SOVEREIGN_WINDOW_SECONDS and not has_license:
            os.environ["AST_GUILLOTINE_ACTIVE"] = "True"
        else:
            os.environ["AST_GUILLOTINE_ACTIVE"] = "False"

        await asyncio.sleep(60)  # Check every minute
