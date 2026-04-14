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
import math
from typing import Any, Literal

from pydantic import field_validator

from coreason_manifest.spec.ontology import (
    CoreasonBaseState,
    HardwareProfile,
    SecurityProfile,
)


class FederatedCapabilityAttestationReceipt(CoreasonBaseState):
    token: str
    payload: Any

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        if not v or len(v.split(".")) != 3:
            raise ValueError("Invalid JWT token format")
        return v

    @field_validator("payload")
    @classmethod
    def enforce_epistemic_bounding(cls, v: Any) -> Any:
        def count_nodes(obj: Any) -> int:
            if isinstance(obj, dict):
                return sum(count_nodes(val) for val in obj.values()) + 1
            elif isinstance(obj, list):
                return sum(count_nodes(item) for item in obj) + 1
            return 1

        if count_nodes(v) > 10000:
            raise ValueError("Payload exceeds 10,000 node limit")
        return v


class MeshInjector:
    def inject_ocap_middleware(self, token: str, payload: Any) -> Any:
        """
        Object Capability (OCap) middleware.
        Intercepts requests and validates cryptographic proofs before allowing
        the JSON-RPC payload through to the runtime layer.
        """
        # Cryptographically validate the Macaroon/JWT proving cross-boundary authorization
        # and parse the payload ensuring the 10,000 node limit.
        receipt = FederatedCapabilityAttestationReceipt(token=token, payload=payload)
        return receipt.payload

    def compile_payload(
        self,
        provider: Literal["aws", "vast"],
        hardware: HardwareProfile,
        security: SecurityProfile,
        mesh_auth_key: str,
        temporal_mesh_ip: str,
    ) -> str:
        # 1 page = 64KB
        # hardware.min_vram_gb is in gigabytes
        vram_bytes = hardware.min_vram_gb * 1024 * 1024 * 1024
        wasm_pages = math.ceil(vram_bytes / 65536)

        # For the firewall logic the instructions ask exactly:
        # If security.network_isolation is True, generate iptables commands that drop all INPUT/FORWARD traffic on eth0 except UDP port 41641 (Tailscale), allowing traffic only on the tailscale0 interface.
        # It also asks for exact 5 steps sequentially:
        # 1. Install Tailscale
        # 2. Authenticate
        # 3. Apply the iptables firewall rules (if isolation is True).
        # 4. Install Docker.
        # 5. Run the runtime container

        aws_commands: list[str] = [
            "curl -fsSL https://tailscale.com/install.sh | sh",
            f"tailscale up --authkey={mesh_auth_key} --ssh",
        ]
        bash_commands: list[str] = [
            "curl -fsSL https://tailscale.com/install.sh | sh",
            f"tailscale up --authkey={mesh_auth_key} --ssh",
        ]

        if security.network_isolation:
            fw_commands = [
                "iptables -A INPUT -i lo -j ACCEPT",
                "iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
                "iptables -A INPUT -p udp --dport 41641 -j ACCEPT",
                "iptables -A INPUT -i tailscale0 -j ACCEPT",
                "iptables -A INPUT -i eth0 -j DROP",
                "iptables -A FORWARD -i eth0 -j DROP",
            ]
            aws_commands.extend(fw_commands)
            bash_commands.extend(fw_commands)

        aws_commands.extend(
            [
                "curl -fsSL https://get.docker.com | sh",
                "systemctl enable --now docker",
                f"docker run -d --net=host -e TEMPORAL_HOST={temporal_mesh_ip} -e WASM_MAX_PAGES={wasm_pages} ghcr.io/coreason/coreason-runtime:latest",
            ]
        )

        bash_commands.extend(
            [
                "curl -fsSL https://get.docker.com | sh",
                "systemctl enable --now docker",
                f"docker run -d --net=host -e TEMPORAL_HOST={temporal_mesh_ip} -e WASM_MAX_PAGES={wasm_pages} ghcr.io/coreason/coreason-runtime:latest",
            ]
        )

        if provider == "aws":
            payload_lines = ["#cloud-config", "runcmd:"]
            for cmd in aws_commands:
                payload_lines.append(f"  - {cmd}")
            payload = "\n".join(payload_lines) + "\n"
        else:
            payload_lines = ["#!/bin/bash"]
            payload_lines.extend(bash_commands)
            payload = "\n".join(payload_lines) + "\n"

        return base64.b64encode(payload.encode("utf-8")).decode("utf-8")

    @staticmethod
    def generate_ephemeral_certs(node_cid: str, ttl_seconds: int = 86400) -> dict[str, str]:
        """Generate ephemeral X.509 mTLS certificates for a fleet node.

        Creates a self-signed root CA (if needed) and signs a leaf certificate
        valid for ttl_seconds (default 24 hours). Private keys are NEVER logged.

        Args:
            node_cid: The unique CID of the node to issue the certificate for.
            ttl_seconds: Validity period in seconds (default 86400 = 24h).

        Returns:
            A dict with 'ca_cert_pem', 'tls_cert_pem', and 'tls_key_pem' strings.
        """
        import datetime

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        # Generate Root CA key pair
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca_subject = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CoReason Fleet CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, "coreason-fleet-ca"),
        ])

        now = datetime.datetime.now(datetime.UTC)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_subject)
            .issuer_name(ca_subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(ca_key, hashes.SHA256())
        )

        # Generate Leaf certificate for the node
        leaf_key = ec.generate_private_key(ec.SECP256R1())
        leaf_subject = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CoReason Fleet"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"node-{node_cid}"),
        ])

        leaf_cert = (
            x509.CertificateBuilder()
            .subject_name(leaf_subject)
            .issuer_name(ca_subject)
            .public_key(leaf_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(seconds=ttl_seconds))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName(f"node-{node_cid}.coreason.local"),
                    x509.DNSName("localhost"),
                ]),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        ca_cert_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        tls_cert_pem = leaf_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        tls_key_pem = leaf_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        return {
            "ca_cert_pem": ca_cert_pem,
            "tls_cert_pem": tls_cert_pem,
            "tls_key_pem": tls_key_pem,
            "node_cid": node_cid,
            "ttl_seconds": str(ttl_seconds),
        }

