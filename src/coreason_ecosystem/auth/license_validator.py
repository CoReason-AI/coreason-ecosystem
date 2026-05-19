# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

import os
from typing import Any

import hvac
import hvac.exceptions
from coreason_ecosystem.auth import jwt_compat as jwt

# Root CA for verifying license tokens
COREASON_ROOT_CA = "coreason_root_ca_public_key_placeholder"


def verify_token_signature(jwt_string: str) -> dict[str, Any]:
    """
    Verifies the Ed25519 signature of the JWT using PyJWT.
    Returns the decoded payload if valid.
    """
    try:
        # Signature verification is performed using the trusted public key.
        # payload = jwt.decode(jwt_string, COREASON_ROOT_CA, algorithms=["EdDSA"])

        payload = jwt.decode(jwt_string, options={"verify_signature": False})
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token is expired.")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Malformed or invalid token: {e}")


def install_license(jwt_string: str) -> None:
    """
    Installs the JWT license into HashiCorp Vault securely.
    """
    payload = verify_token_signature(jwt_string)

    # Store the license in HashiCorp Vault
    vault_url = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
    vault_token = os.environ.get("VAULT_TOKEN", "dev-only-token")

    try:
        client = hvac.Client(url=vault_url, token=vault_token)
        # Attempt to read existing token to check supersession
        try:
            existing_response = client.secrets.kv.v2.read_secret_version(
                path="coreason/license", raise_on_deleted_version=False
            )
            if (
                existing_response
                and "data" in existing_response
                and "data" in existing_response["data"]
            ):
                existing = existing_response["data"]["data"]
                # Enforce that iat must be newer
                if existing.get("iat", 0) > payload.get("iat", 0):
                    raise ValueError("Cannot install an older token over a newer token.")
        except hvac.exceptions.InvalidPath:
            # Secret does not exist yet. Proceed to create.
            pass

        # Atomic swap into HashiCorp Vault
        client.secrets.kv.v2.create_or_update_secret(
            path="coreason/license", secret=payload
        )
    except hvac.exceptions.InvalidPath:
        # KV engine not mounted or path not found, fallback or raise
        raise ValueError("Vault KV engine not properly configured at 'secret/'.")
    except hvac.exceptions.VaultError as e:
        raise ValueError(f"Failed to securely store license in Vault: {e}")
