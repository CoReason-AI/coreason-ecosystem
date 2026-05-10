from typing import Any
# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import base64

from coreason_ecosystem.fleet.mesh_injector import MeshInjector
from coreason_manifest.spec.ontology import (
    SpatialHardwareProfile as HardwareProfile,
    EpistemicSecurityProfile as SecurityProfile,
)


def test_mesh_injector_aws_isolated() -> None:
    """AWS with network isolation renders cloud-init with firewall rules."""
    injector = MeshInjector()
    hw = HardwareProfile(min_vram_gb=16.0, provider_whitelist=["aws"])
    sec = SecurityProfile(network_isolation=True)
    payload_b64 = injector.compile_payload(
        "test-node-123",
        "aws",
        hw.model_dump(),
        sec.model_dump(),
        "test_auth_key",
        "10.0.0.5",
    )
    payload = base64.b64decode(payload_b64).decode("utf-8")
    assert "#cloud-config" in payload
    assert "tailscale.com" in payload
    assert "test_auth_key" in payload
    assert "cilium endpoint config coreason.node.cid=test-node-123" in payload
    assert "10.0.0.5" in payload
    assert "WASM_MAX_PAGES" in payload


def test_mesh_injector_vast_not_isolated() -> None:
    """Vast without network isolation renders cloud-init without firewall rules."""
    injector = MeshInjector()
    hw = HardwareProfile(min_vram_gb=16.0, provider_whitelist=["vast"])
    sec = SecurityProfile(network_isolation=False)
    payload_b64 = injector.compile_payload(
        "test-node-123",
        "vast",
        hw.model_dump(),
        sec.model_dump(),
        "test_auth_key",
        "10.0.0.5",
    )
    payload = base64.b64decode(payload_b64).decode("utf-8")
    assert "#cloud-config" in payload
    assert "test_auth_key" in payload
    assert "cilium endpoint config" not in payload


def test_verify_payload_integrity() -> None:
    import json
    import hashlib

    injector = MeshInjector()

    # Test valid JSON
    valid_json = {"test": 123, "a": "b"}
    raw_bytes = json.dumps(valid_json).encode("utf-8")
    expected_hash = hashlib.sha256(
        json.dumps(valid_json, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert injector.verify_payload_integrity(raw_bytes, expected_hash) is True

    # Test invalid JSON / binary payload
    binary_payload = b"\x80\x81\x82"
    expected_binary_hash = hashlib.sha256(binary_payload).hexdigest()
    assert (
        injector.verify_payload_integrity(binary_payload, expected_binary_hash) is True
    )

    # Test mismatch
    import pytest

    with pytest.raises(ValueError, match="Payload Quarantine Breach"):
        injector.verify_payload_integrity(raw_bytes, "wrong_hash")
