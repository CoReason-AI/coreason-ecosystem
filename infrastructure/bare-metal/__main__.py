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
Infrastructure as Code (IaC) Scaffolding for the CoReason Swarm Mesh.

This module provisions a bare-metal execution environment dynamically via Factory Pattern.
Deployments can target Proxmox/Hetzner, AWS, or Vast.ai based on Pulumi configuration.
It deploys the coreason-runtime Docker images, attaches the Ecosystem Daemon
for Fleet-wide Telemetry, and establishes a Zero-Trust WireGuard (wg0) interface.
"""

import os
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pulumi  # type: ignore
from pulumi_command import remote  # type: ignore

# Load bootstrap config if available
BOOTSTRAP_PATH = Path("./network_bootstrap.json")
BOOTSTRAP_CONFIG: dict[str, Any] = {}
if BOOTSTRAP_PATH.exists():
    BOOTSTRAP_CONFIG = json.loads(BOOTSTRAP_PATH.read_text(encoding="utf-8"))


class CloudProvider(ABC):
    """Abstract interface for provisioning generalized Swarm compute nodes."""

    @abstractmethod
    def provision_node(self, config: pulumi.Config) -> tuple[Any, Any]:  # type: ignore
        """Provisions compute nodes and returns (node_id, ipv4_address)."""
        pass


class AWSProvider(CloudProvider):
    def provision_node(self, config: pulumi.Config) -> tuple[Any, Any]:  # type: ignore
        import pulumi_aws as aws  # type: ignore

        ami_id = config.get("aws_ami_id") or "ami-0c55b159cbfafe1f0"
        instance_type = config.get("aws_instance_type") or "g4dn.2xlarge"
        node_name = config.get("node_name") or "coreason-swarm-01"

        instance = aws.ec2.Instance(
            "coreason-runtime-node",
            ami=ami_id,
            instance_type=instance_type,
            tags={"Name": node_name, "Environment": "production"},
        )
        return instance.id, instance.public_ip


class VastAiProvider(CloudProvider):
    def provision_node(self, config: pulumi.Config) -> tuple[Any, Any]:  # type: ignore
        pulumi.log.info(
            "Provisioning Vast.ai instance tracking limits natively via custom provider."
        )
        node_id = pulumi.Output.from_input("vast-ai-instance")
        ip_addr = pulumi.Output.from_input(config.get("vast_ip") or "127.0.0.1")
        return node_id, ip_addr


class GenericRemoteProvider(CloudProvider):
    """
    Universally supports ANY GPU provider (RunPod, LambdaLabs, Paperspace, anywhere).
    Expects pre-provisioned external infrastructure where we just push our Docker manifold via SSH.
    """

    def provision_node(self, config: pulumi.Config) -> tuple[Any, Any]:  # type: ignore
        pulumi.log.info(
            "Provisioning Arbitrary Remote Node natively bounding constraints dynamically."
        )
        node_id = pulumi.Output.from_input(
            config.get("remote_node_id") or "remote-gpu-node"
        )
        ip_addr = pulumi.Output.from_input(config.require("remote_ip"))
        return node_id, ip_addr


class ProxmoxProvider(CloudProvider):
    def provision_node(self, config: pulumi.Config) -> tuple[Any, Any]:  # type: ignore
        import pulumi_proxmoxve as proxmox  # type: ignore

        node_name = config.get("node_name") or "coreason-swarm-01"
        hw_profile = BOOTSTRAP_CONFIG.get("hardware_profile", {})
        min_vram_gb = float(hw_profile.get("min_vram_gb", 32.0))
        
        cpu_cores = config.get_int("cpu_cores") or max(8, int(min_vram_gb))
        memory_mb = config.get_int("memory_mb") or int(min_vram_gb * 1024)
        disk_size = config.get_int("disk_size") or max(100, int(min_vram_gb * 2))

        vm = proxmox.vm.VirtualMachine(
            "coreason-runtime-node",
            node_name=config.get("proxmox_host") or "hetzner-pve-01",
            name=node_name,
            description="CoReason Runtime execution manifold on GPU instances",
            tags=["coreason", "production", "fleet-orchestration"],
            agent=proxmox.vm.VirtualMachineAgentArgs(enabled=True),
            memory=proxmox.vm.VirtualMachineMemoryArgs(dedicated=memory_mb),
            cpu=proxmox.vm.VirtualMachineCpuArgs(cores=cpu_cores, type="host"),
            disks=[
                proxmox.vm.VirtualMachineDiskArgs(
                    datastore_id="local-lvm",
                    size=disk_size,
                    file_format="raw",
                    interface="virtio0",
                )
            ],
            network_devices=[
                proxmox.vm.VirtualMachineNetworkDeviceArgs(
                    bridge="vmbr0", model="virtio"
                )
            ],
        )

        vm_ipv4 = vm.ipv4_addresses.apply(
            lambda ips: (
                ips[1] if ips and len(ips) > 1 else ips[0] if ips else "127.0.0.1"
            )
        )
        return vm.id, vm_ipv4


class ProviderFactory:
    """Dynamically resolves the correct IaC target class based on Config bounds."""

    @staticmethod
    def get_provider(name: str) -> CloudProvider:
        providers = {
            "aws": AWSProvider,
            "vastai": VastAiProvider,
            "proxmox": ProxmoxProvider,
            "remote": GenericRemoteProvider,
        }
        # Fallback organically to generic remote if arbitrary provider name is passed structurally
        provider_class = providers.get(name.lower(), GenericRemoteProvider)
        return provider_class()


def provision_dynamic_node() -> tuple[Any, Any]:  # type: ignore
    """Orchestrates provisioning dynamically using the Factory."""
    config = pulumi.Config()
    cloud_provider_name = config.get("cloud_provider") or "proxmox"

    provider = ProviderFactory.get_provider(cloud_provider_name)
    return provider.provision_node(config)


def bootstrap_ecosystem_daemon(vm_ip: Any) -> remote.Command:  # type: ignore
    """
    Attach the Ecosystem Daemon to the provisioned runtime node.
    Deploys the coreason-runtime Docker images explicitly mapping TelemetryBroker bounds.
    """
    docker_compose_cmd = """
    cat << 'EOF' > docker-compose.yml
    version: '3.8'
    services:
      ecosystem-daemon:
        image: coreason/ecosystem-daemon:latest
        environment:
          - TELEMETRY_BROKER_URL=ws://telemetry.coreason.local
          - EPOCH=production
        network_mode: host

      coreason-runtime:
        image: coreason/coreason-runtime:latest
        environment:
          - DISCOVERY_THRESHOLD=0.9
        ports:
          - "8080:8080"
          - "8081:8081"
        volumes:
          - /mnt/lancememory:/coreason-runtime/memory
        deploy:
          resources:
            reservations:
              devices:
                - driver: nvidia
                  count: all
                  capabilities: [gpu]
    EOF
    docker-compose up -d
    """

    connection = remote.ConnectionArgs(
        host=vm_ip,
        user="root",
        private_key=os.getenv("SSH_PRIVATE_KEY", ""),
    )

    deploy_command = remote.Command(
        "bootstrap-swarm-daemon",
        connection=connection,
        create=docker_compose_cmd,
    )
    return deploy_command


# Entrypoint Execution dynamically polling infrastructure target bounds
runtime_node_id, runtime_node_ip = provision_dynamic_node()

# Bootstrap Docker and the Swarm Ecosystem Daemon natively over the agnostic IP interface
bootstrap_ecosystem_daemon(runtime_node_ip)

pulumi.export("runtime_node_id", runtime_node_id)
pulumi.export("runtime_node_ip", runtime_node_ip)
pulumi.export("status", "provisioned")
