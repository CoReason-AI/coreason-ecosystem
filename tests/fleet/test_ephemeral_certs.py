# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

from coreason_ecosystem.fleet.mesh_injector import MeshInjector


def test_generate_ephemeral_certs() -> None:
    """Test that ephemeral certs are generated with correct keys and content."""
    certs = MeshInjector.generate_ephemeral_certs("test-node-cid-001")

    assert "ca_cert_pem" in certs
    assert "tls_cert_pem" in certs
    assert "tls_key_pem" in certs
    assert certs["node_cid"] == "test-node-cid-001"
    assert certs["ttl_seconds"] == "86400"

    # Verify PEM format
    assert certs["ca_cert_pem"].startswith("-----BEGIN CERTIFICATE-----")
    assert certs["tls_cert_pem"].startswith("-----BEGIN CERTIFICATE-----")
    assert certs["tls_key_pem"].startswith("-----BEGIN PRIVATE KEY-----")


def test_generate_ephemeral_certs_custom_ttl() -> None:
    """Test ephemeral cert generation with custom TTL."""
    certs = MeshInjector.generate_ephemeral_certs("node-abc", ttl_seconds=3600)
    assert certs["ttl_seconds"] == "3600"
    assert certs["node_cid"] == "node-abc"
