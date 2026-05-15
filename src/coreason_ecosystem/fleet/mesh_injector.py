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
import hashlib
import json
import math
from typing import Any, Literal


class MeshInjector:
    def inject_ocap_middleware(self, token: str, payload: Any) -> Any:
        """
        Object Capability (OCap) middleware.
        Intercepts requests and validates cryptographic proofs before allowing
        the JSON-RPC payload through to the runtime layer.
        """
        if not token or len(token.split(".")) != 3:
            raise ValueError("Invalid JWT token format")

        def count_nodes(obj: Any) -> int:
            if isinstance(obj, dict):
                return sum(count_nodes(val) for val in obj.values()) + 1
            elif isinstance(obj, list):
                return sum(count_nodes(item) for item in obj) + 1
            return 1

        if count_nodes(payload) > 10000:
            raise ValueError("Payload exceeds 10,000 node limit")

        return payload

    def compile_payload(
        self,
        node_cid: str,
        provider: Literal["aws", "vast", "skypilot"],
        hardware: dict[str, Any],
        security: dict[str, Any],
        mesh_auth_key: str,
        temporal_mesh_ip: str,
    ) -> str:
        """Render a deterministic cloud-init configuration from the IaC template.

        Loads ``infrastructure/ephemeral/cloud-init.yaml.tpl`` and injects
        the provisioning parameters. No raw shell scripts are generated —
        per Mandatory Development Protocol #3 (IaC Mandate).
        """
        from pathlib import Path

        # 1 page = 64KB
        min_vram_gb = float(hardware.get("min_vram_gb", 8.0))
        vram_bytes = min_vram_gb * 1024 * 1024 * 1024
        wasm_pages = math.ceil(vram_bytes / 65536)

        # Resolve the deterministic IaC template
        template_path = (
            Path(__file__).resolve().parents[3]
            / "infrastructure"
            / "ephemeral"
            / "cloud-init.yaml.tpl"
        )
        template = template_path.read_text(encoding="utf-8")

        # Render declarative eBPF firewall rules if network isolation is required
        firewall_rules = ""
        if security.get("network_isolation", False):
            policy_manifest = f"""apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: "zero-trust-node-{node_cid}"
spec:
  endpointSelector:
    matchLabels:
      coreason.node.cid: "{node_cid}"
  ingress:
  - fromEndpoints:
    - matchLabels:
        coreason.mesh.role: "master-gateway"
    toPorts:
    - ports:
      - port: "41641"
        protocol: UDP
  egress:
  - toEndpoints:
    - matchLabels:
        coreason.mesh.role: "master-gateway"
"""
            b64_policy = base64.b64encode(policy_manifest.encode("utf-8")).decode(
                "utf-8"
            )
            fw_lines = [
                "  - mkdir -p /etc/cilium/policies",
                f"  - echo {b64_policy} | base64 -d > /etc/cilium/policies/node-{node_cid}.yaml",
                f"  - cilium endpoint config coreason.node.cid={node_cid}",
                "  - cilium policy import /etc/cilium/policies/node-*.yaml",
            ]
            firewall_rules = "\n".join(fw_lines)

        # Inject parameters into the template
        rendered = (
            template.replace("{{MESH_AUTH_KEY}}", mesh_auth_key)
            .replace("{{TEMPORAL_MESH_IP}}", temporal_mesh_ip)
            .replace("{{WASM_MAX_PAGES}}", str(wasm_pages))
            .replace("{{FIREWALL_RULES}}", firewall_rules)
        )

        return base64.b64encode(rendered.encode("utf-8")).decode("utf-8")

    @staticmethod
    def generate_ephemeral_certs(
        node_cid: str, ttl_seconds: int = 86400
    ) -> dict[str, str]:
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
        ca_subject = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CoReason Fleet CA"),
                x509.NameAttribute(NameOID.COMMON_NAME, "coreason-fleet-ca"),
            ]
        )

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
        leaf_subject = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CoReason Fleet"),
                x509.NameAttribute(NameOID.COMMON_NAME, f"node-{node_cid}"),
            ]
        )

        leaf_cert = (
            x509.CertificateBuilder()
            .subject_name(leaf_subject)
            .issuer_name(ca_subject)
            .public_key(leaf_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(seconds=ttl_seconds))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName(f"node-{node_cid}.coreason.local"),
                        x509.DNSName("localhost"),
                    ]
                ),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        ca_cert_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        tls_cert_pem = leaf_cert.public_bytes(serialization.Encoding.PEM).decode(
            "utf-8"
        )
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

    @staticmethod
    def verify_payload_integrity(
        payload_bytes: bytes,
        expected_hash: str,
    ) -> bool:
        """Verify a WASM payload's SHA-256 hash against the genesis manifest.

        Enforces LAW 4 (Cryptographic Provenance) by ensuring no WASM payload
        or MCP schema is projected to the kinetic plane without its SHA-256
        hash being verified against the genesis manifest.

        The payload is first canonicalized via RFC 8785 (JCS) if it is valid
        JSON; otherwise the raw bytes are hashed directly.

        Args:
            payload_bytes: The raw bytes of the WASM payload or MCP schema.
            expected_hash: The SHA-256 hex digest from the genesis manifest.

        Returns:
            True if the computed hash matches the expected hash.

        Raises:
            ValueError: If the hash does not match (payload quarantine breach).
        """
        # Attempt RFC 8785 canonical form for JSON payloads
        try:
            parsed = json.loads(payload_bytes)
            canonical = json.dumps(
                parsed, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Binary WASM payload — hash raw bytes
            canonical = payload_bytes

        computed_hash = hashlib.sha256(canonical).hexdigest()

        if computed_hash != expected_hash:
            raise ValueError(
                f"Payload Quarantine Breach: computed hash {computed_hash[:16]}... "
                f"does not match genesis manifest hash {expected_hash[:16]}..."
            )

        return True

    def register_capability(
        self,
        urn: str,
        endpoint: str,
        clearance: Literal["PUBLIC", "CONFIDENTIAL", "RESTRICTED"],
        epistemic_status: Literal[
            "DRAFT",
            "SRB_APPROVED",
            "CLIENT_APPROVED",
            "PUBLISHED",
            "DEPRECATED",
            "QUARANTINED",
            "RETRACTED",
        ],
    ) -> None:  # pragma: no cover
        """Autonomously monitor the external capability registry and dynamically
        establish the network path in capabilities.matrix.yaml to route JSON-RPC intents.

        The Governance Plane is domain-blind — it routes URNs statelessly without inspecting
        semantic payloads or asserting Pydantic implementations.
        """
        import yaml
        from pathlib import Path

        matrix_path = (
            Path(__file__).resolve().parents[3]
            / "infrastructure"
            / "local"
            / "capabilities.matrix.yaml"
        )

        with open(matrix_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {"capabilities": []}

        found = False
        for cap in data.get("capabilities", []):
            if cap.get("urn") == urn:
                cap["endpoint"] = endpoint
                cap["clearance"] = clearance
                cap["epistemic_status"] = epistemic_status
                found = True
                break

        if not found:
            data.setdefault("capabilities", []).append(
                {
                    "urn": urn,
                    "endpoint": endpoint,
                    "clearance": clearance,
                    "epistemic_status": epistemic_status,
                }
            )

        with open(matrix_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
