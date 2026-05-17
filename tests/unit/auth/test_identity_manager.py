# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

import jwt
from coreason_ecosystem.auth.identity_manager import extract_workload_identity


def test_extract_workload_identity_spiffe_only():
    headers = {"X-SPIFFE-ID": "spiffe://coreason.ai/workload/test"}
    identity = extract_workload_identity(headers)
    assert identity["spiffe_id"] == "spiffe://coreason.ai/workload/test"
    assert identity["jwt_payload"] is None


def test_extract_workload_identity_jwt_only():
    payload = {"sub": "user123", "iat": 1600000000}
    token = jwt.encode(payload, "secret", algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    identity = extract_workload_identity(headers)
    assert identity["jwt_payload"] == payload
    assert identity["spiffe_id"] is None
    assert identity["raw_jwt"] == token


def test_extract_workload_identity_jwt_and_spiffe():
    payload = {"sub": "user-1"}
    token = jwt.encode(payload, "secret", algorithm="HS256")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-SPIFFE-ID": "spiffe://local/workload",
        "X-Tenant-CID": "tenant-123",
    }

    result = extract_workload_identity(headers)

    assert result["spiffe_id"] == "spiffe://local/workload"
    assert result["jwt_payload"] == payload
    assert result["raw_jwt"] == token
    assert result["tenant_cid"] == "tenant-123"


def test_extract_workload_identity_case_insensitivity():
    payload = {"sub": "user-1"}
    token = jwt.encode(payload, "secret", algorithm="HS256")
    headers = {
        "authorization": f"Bearer {token}",
        "x-spiffe-id": "spiffe://local/workload",
    }

    result = extract_workload_identity(headers)

    assert result["spiffe_id"] == "spiffe://local/workload"
    assert result["jwt_payload"] == payload
    assert result["raw_jwt"] == token


def test_extract_workload_identity_mixed_case():
    headers = {
        "x-spiffe-id": "spiffe://coreason.ai/workload/test",
        "authorization": "Bearer token123",
    }
    # Note: token123 is invalid JWT but extract_workload_identity handles it gracefully
    identity = extract_workload_identity(headers)
    assert identity["spiffe_id"] == "spiffe://coreason.ai/workload/test"
    assert identity["jwt_payload"] is None
    assert identity["raw_jwt"] == "token123"


def test_extract_workload_identity_tenant_cid():
    headers = {"X-Tenant-CID": "tenant-123"}
    identity = extract_workload_identity(headers)
    assert identity["tenant_cid"] == "tenant-123"
