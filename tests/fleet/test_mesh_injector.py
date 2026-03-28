# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.
#

import pytest
import base64
from coreason_ecosystem.fleet.mesh_injector import MeshInjector
from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile

def test_mesh_injector_aws_isolated():
    injector = MeshInjector()
    hw = HardwareProfile(min_vram_gb=16.0, provider_whitelist=["aws"], accelerator_type="ampere")
    sec = SecurityProfile(network_isolation=True)
    payload_b64 = injector.compile_payload("aws", hw, sec, "test_auth_key", "10.0.0.5")
    payload = base64.b64decode(payload_b64).decode("utf-8")
    assert "tailscale.com" in payload
    assert "test_auth_key" in payload
    assert "iptables -A INPUT -i eth0 -j DROP" in payload
    assert "10.0.0.5" in payload
    assert "WASM_MAX_PAGES" in payload
    assert "#cloud-config" in payload

def test_mesh_injector_vast_not_isolated():
    injector = MeshInjector()
    hw = HardwareProfile(min_vram_gb=16.0, provider_whitelist=["vast"], accelerator_type="ampere")
    sec = SecurityProfile(network_isolation=False)
    payload_b64 = injector.compile_payload("vast", hw, sec, "test_auth_key", "10.0.0.5")
    payload = base64.b64decode(payload_b64).decode("utf-8")
    assert "#!/bin/bash" in payload
    assert "test_auth_key" in payload
    assert "iptables -A INPUT -i eth0 -j DROP" not in payload
