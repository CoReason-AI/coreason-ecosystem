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
import logging
from typing import Any

import hvac
import hvac.exceptions
from coreason_ecosystem.auth import jwt_compat as jwt

logger = logging.getLogger(__name__)


def get_root_ca_key() -> str:
    env = os.environ.get("COREASON_ENV", "development")
    root_ca = os.environ.get("COREASON_ROOT_CA_KEY")

    if env == "production":
        if not root_ca:
            raise RuntimeError("Root CA Key not configured. Owner Ceremony required.")
        return root_ca

    if root_ca:
        return root_ca

    dev_key = os.environ.get("COREASON_DEV_KEY")
    if dev_key:
        logger.warning(
            "Operating with COREASON_DEV_KEY. System is not using the official Root CA."
        )
        return dev_key

    raise RuntimeError(
        "Neither COREASON_ROOT_CA_KEY nor COREASON_DEV_KEY is configured."
    )


def verify_token_signature(jwt_string: str) -> dict[str, Any]:
    """
    Verifies the Ed25519 signature of the JWT using PyJWT.
    Returns the decoded payload if valid.
    """
    public_key = get_root_ca_key()
    try:
        # Signature verification is performed using the trusted public key.
        payload = jwt.decode(jwt_string, public_key, algorithms=["EdDSA"])
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
    env = os.environ.get("COREASON_ENV", "development")
    vault_url = os.environ.get("VAULT_ADDR")
    vault_token = os.environ.get("VAULT_TOKEN")

    if env == "production":
        if (
            not vault_url
            or not vault_token
            or "127.0.0.1" in vault_url
            or "localhost" in vault_url
        ):
            raise ValueError(
                "Production deployment requires valid Vault credentials and non-local Vault address."
            )

    vault_url = vault_url or "http://127.0.0.1:8200"
    vault_token = vault_token or "dev-only-token"

    try:
        client = hvac.Client(url=vault_url, token=vault_token)
        # Attempt to read existing token to check supersession
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

        # Atomic swap into HashiCorp Vault
        client.secrets.kv.v2.create_or_update_secret(
            path="coreason/license", secret=payload
        )
    except hvac.exceptions.InvalidPath:
        # KV engine not mounted or path not found, fallback or raise
        raise ValueError("Vault KV engine not properly configured at 'secret/'.")
    except hvac.exceptions.VaultError as e:
        raise ValueError(f"Failed to securely store license in Vault: {e}")
