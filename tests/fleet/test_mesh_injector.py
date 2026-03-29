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
from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile  # type: ignore[attr-defined]


def test_mesh_injector_aws_isolated() -> None:
    injector = MeshInjector()
    hw = HardwareProfile(
        min_vram_gb=16.0, provider_whitelist=["aws"], accelerator_type="ampere"
    )
    sec = SecurityProfile(network_isolation=True)
    payload_b64 = injector.compile_payload("aws", hw, sec, "test_auth_key", "10.0.0.5")
    payload = base64.b64decode(payload_b64).decode("utf-8")
    assert "tailscale.com" in payload
    assert "test_auth_key" in payload
    assert "iptables -A INPUT -i eth0 -j DROP" in payload
    assert "10.0.0.5" in payload
    assert "WASM_MAX_PAGES" in payload
    assert "#cloud-config" in payload


def test_mesh_injector_vast_not_isolated() -> None:
    injector = MeshInjector()
    hw = HardwareProfile(
        min_vram_gb=16.0, provider_whitelist=["vast"], accelerator_type="ampere"
    )
    sec = SecurityProfile(network_isolation=False)
    payload_b64 = injector.compile_payload("vast", hw, sec, "test_auth_key", "10.0.0.5")
    payload = base64.b64decode(payload_b64).decode("utf-8")
    assert "#!/bin/bash" in payload
    assert "test_auth_key" in payload
    assert "iptables -A INPUT -i eth0 -j DROP" not in payload
