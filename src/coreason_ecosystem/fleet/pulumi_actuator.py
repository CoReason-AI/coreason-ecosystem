# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import asyncio
import uuid
from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic import BaseModel
from pulumi import automation as auto

from coreason_ecosystem.fleet.mesh_injector import MeshInjector
from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile


class ComputeNodeTarget(BaseModel):
    provider: Literal["aws", "vast"]
    instance_id: str
    hourly_cost: float
    vram_gb: float
    hardware_profile: HardwareProfile | None = None
    security_profile: SecurityProfile | None = None
    mesh_auth_key: str | None = None
    temporal_mesh_ip: str | None = None


class PulumiFleetDriver:
    def __init__(self, templates_dir: Path) -> None:
        self.templates_dir = templates_dir
        self.injector = MeshInjector()

    async def provision_node(self, target: ComputeNodeTarget) -> dict[str, str]:
        stack_name = f"fleet-worker-{uuid.uuid4().hex[:8]}"
        provider_dir = self.templates_dir / (
            "aws_spot" if target.provider == "aws" else "vast_ai"
        )

        logger.info(f"Provisioning {target.provider} node on stack {stack_name}...")

        def _provision() -> dict[str, str]:
            stack = auto.create_stack(
                stack_name=stack_name,
                work_dir=str(provider_dir),
            )

            stack.set_config("provider", auto.ConfigValue(target.provider))

            if (
                target.hardware_profile
                and target.security_profile
                and target.mesh_auth_key
                and target.temporal_mesh_ip
            ):
                payload_b64 = self.injector.compile_payload(
                    provider=target.provider,
                    hardware=target.hardware_profile,
                    security=target.security_profile,
                    mesh_auth_key=target.mesh_auth_key,
                    temporal_mesh_ip=target.temporal_mesh_ip,
                )
                stack.set_config(
                    "boot_payload_b64", auto.ConfigValue(value=payload_b64)
                )

            if target.provider == "aws":
                stack.set_config("instance_type", auto.ConfigValue(target.instance_id))
                stack.set_config("ami_id", auto.ConfigValue("ami-0abcdef1234567890"))
                stack.set_config("ssh_pub_key", auto.ConfigValue("ssh-rsa AAA..."))
                stack.set_config("aws:region", auto.ConfigValue("us-west-2"))
            elif target.provider == "vast":
                stack.set_config("machine_id", auto.ConfigValue(target.instance_id))
                stack.set_config("gpu_name", auto.ConfigValue("RTX_4090"))
                stack.set_config("ssh_pub_key", auto.ConfigValue("ssh-rsa AAA..."))

            up_res = stack.up(
                on_output=lambda msg: logger.debug(
                    f"Pulumi [{stack_name}]: {msg.strip()}"
                )
            )
            return {
                "stack_name": stack_name,
                "outputs": str({k: v.value for k, v in up_res.outputs.items()}),
            }

        res = await asyncio.to_thread(_provision)
        logger.info(f"Node provisioned on stack {stack_name} successfully.")
        return res

    async def destroy_node(
        self, stack_name: str, provider: Literal["aws", "vast"]
    ) -> None:
        provider_dir = self.templates_dir / (
            "aws_spot" if provider == "aws" else "vast_ai"
        )
        logger.info(f"Destroying {provider} node on stack {stack_name}...")

        def _destroy() -> None:
            stack = auto.select_stack(
                stack_name=stack_name,
                work_dir=str(provider_dir),
            )

            stack.destroy(
                on_output=lambda msg: logger.debug(
                    f"Pulumi [{stack_name}]: {msg.strip()}"
                )
            )
            stack.workspace.remove_stack(stack_name)

        await asyncio.to_thread(_destroy)
        logger.info(f"Stack {stack_name} destroyed and removed.")

    async def reconcile_state(self) -> list[dict[str, str]]:
        def _reconcile() -> list[dict[str, str]]:
            active_stacks: list[dict[str, str]] = []
            for provider_dir in self.templates_dir.iterdir():
                if provider_dir.is_dir():
                    # Infer the provider from the directory name
                    provider = "aws" if "aws" in provider_dir.name else "vast"
                    try:
                        workspace = auto.LocalWorkspace(work_dir=str(provider_dir))
                        stacks = workspace.list_stacks()
                        for stack in stacks:
                            if stack.name.startswith("fleet-worker-"):
                                active_stacks.append(
                                    {"stack_name": stack.name, "provider": provider}
                                )
                                logger.warning(
                                    f"Orphaned stack found: {stack.name} in {provider}"
                                )
                    except Exception as e:
                        logger.warning(
                            f"Failed to read Pulumi workspace in {provider_dir}: {e}"
                        )
            return active_stacks

        return await asyncio.to_thread(_reconcile)
