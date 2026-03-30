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
from typing import Literal

from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile


class MeshInjector:
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
