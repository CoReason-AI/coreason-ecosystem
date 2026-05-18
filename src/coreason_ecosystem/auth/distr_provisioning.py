# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""
AGENT INSTRUCTION: This module implements the internal Distr licensing backend.
It is explicitly used by the CoReason owner and Sales teams to perform the "Key Generation Ceremony"
and issue VCDM v2.0 CommercialOverrideReceipts.

CAUSAL AFFORDANCE: Generates cryptographic keys and mathematically signs SD-JWT licenses
that unlock premium runtime constraints in `coreason-runtime`.

EPISTEMIC BOUNDS: Strict isolation from standard orchestration logic. This module must
NEVER execute inside an agentic runtime loop. It is an offline administrative tool.

MCP ROUTING TRIGGERS: License Generation, Key Ceremony, Distr Backend, Ed25519, VCDM Provisioning
"""

import logging
import os
import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from coreason_manifest.spec.ontology import CommercialOverrideReceipt

logger = logging.getLogger(__name__)

VAULT_DIR = Path.home() / ".coreason" / "vault"
MASTER_KEY_FILE = VAULT_DIR / "master.pem"


def init_vault() -> None:
    """The Key Generation Ceremony."""
    if MASTER_KEY_FILE.exists():
        raise FileExistsError(f"Vault already initialized at {MASTER_KEY_FILE}")

    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate Ed25519 Private Key
    private_key = ed25519.Ed25519PrivateKey.generate()

    # Export Private Key
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Securely write the key (simulate HSM storage)
    with open(MASTER_KEY_FILE, "wb") as f:
        f.write(pem_bytes)

    # Strictly lock permissions to the current owner (Unix only)
    if os.name != "nt":
        MASTER_KEY_FILE.chmod(0o600)

    # Export Public Key for the manifest verification anchor
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )

    logger.info(
        f"Key Generation Ceremony Complete. Master key vaulted at {MASTER_KEY_FILE}"
    )
    logger.info(f"Public Key (Hex): {pub_bytes.hex()}")
    logger.info(
        "ACTION REQUIRED: Embed this Public Key into coreason-runtime/execution_plane/license_verifier.py"
    )


def issue_license(
    tenant_cid: str,
    entitlements: list[str],
    valid_days: int = 365,
    hardware_zk_proof: str | None = None,
) -> str:
    """Issue a CommercialOverrideReceipt (Signed VCDM v2.0 JWT)."""
    if not MASTER_KEY_FILE.exists():
        raise FileNotFoundError(
            "Master key vault not initialized. Run `coreason distr init-vault` first."
        )

    with open(MASTER_KEY_FILE, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    current_time = int(time.time())
    expires_at = current_time + (valid_days * 86400)

    # Construct the receipt
    receipt = CommercialOverrideReceipt(
        distr_license_cid=f"lic_{int(time.time())}",
        tenant_cid=tenant_cid,
        entitlements=entitlements,
        issued_at_epoch=current_time,
        expires_at_epoch=expires_at,
        network_mode="private",
        license_tier="commercial",
        signer_did="did:key:z6MkhaXgBZDvotDkL5257faiztiuC2ZXsdY4SSgMnh3YEFWbYB",  # gitleaks:allow
    )

    # Create standard JWT wrapping the VCDM credential
    payload = receipt.model_dump(mode="json")

    # Sign with Ed25519
    token = jwt.encode(payload, private_key, algorithm="EdDSA")  # type: ignore

    return token
