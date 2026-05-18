# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

"""Workload Identity Passthrough.

This module provides utilities to extract SPIFFE IDs and JWT tokens from
inbound headers for use in zero-trust authorization sidecars.
"""

import logging
from typing import Any

from coreason_ecosystem.auth import jwt_compat as jwt

logger = logging.getLogger(__name__)


def extract_workload_identity(headers: dict[str, str]) -> dict[str, Any]:
    """
    Extracts the SPIFFE SVID or JWT from Envoy/NATS headers.

    This is a passthrough function. Actual authorization decisions are
    delegated to the Envoy proxy layer or an external OPA sidecar.
    """
    # Normalize headers to lowercase for deterministic lookups
    norm_headers = {k.lower(): v for k, v in headers.items()}

    # Extract SPIFFE ID (typically injected by Envoy/SPIRE)
    spiffe_id = norm_headers.get("x-spiffe-id")

    # Extract JWT (typically in Authorization header)
    auth_header = norm_headers.get("authorization")
    jwt_payload = None
    raw_jwt = None

    if auth_header and auth_header.startswith("Bearer "):
        raw_jwt = auth_header[7:]
        try:
            # Note: We do NOT verify the signature here. We are a passthrough.
            # Signature verification is handled at the network edge or sidecar.
            jwt_payload = jwt.decode(raw_jwt, options={"verify_signature": False})
        except Exception as e:
            logger.debug("Failed to decode JWT for passthrough: %s", e)

    return {
        "spiffe_id": spiffe_id,
        "jwt_payload": jwt_payload,
        "raw_jwt": raw_jwt,
        "tenant_cid": norm_headers.get("x-tenant-cid"),
    }
