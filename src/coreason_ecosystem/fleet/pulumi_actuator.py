# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0

import asyncio
import uuid
from typing import Any, Literal
from pathlib import Path

from pydantic import BaseModel
from pulumi import automation as auto


class ComputeNodeTarget(BaseModel):
    provider: Literal["aws", "vast"]
    instance_id: str
    hourly_cost: float
    vram_gb: float


class PulumiFleetDriver:
    def __init__(self, templates_dir: str | Path) -> None:
        self.templates_dir = Path(templates_dir).resolve()

    async def provision_node(self, target: ComputeNodeTarget) -> dict[str, Any]:
        stack_name = f"fleet-worker-{uuid.uuid4().hex[:8]}"
        work_dir = (
            self.templates_dir / f"{target.provider}_spot"
            if target.provider == "aws"
            else self.templates_dir / f"{target.provider}_ai"
        )

        def _provision() -> dict[str, Any]:
            stack = auto.create_stack(stack_name=stack_name, work_dir=str(work_dir))

            # Set configurations based on provider
            if target.provider == "aws":
                stack.set_config(
                    "instance_type", auto.ConfigValue(value=target.instance_id)
                )
                # Using dummy AMI and pub key for standard template fulfillment
                stack.set_config(
                    "ami_id", auto.ConfigValue(value="ami-0c55b159cbfafe1f0")
                )
                stack.set_config(
                    "ssh_pub_key",
                    auto.ConfigValue(value="ssh-rsa AAAAB3NzaC1... dummy-key"),
                )
                # Note: Configure AWS region if necessary
                stack.set_config("aws:region", auto.ConfigValue(value="us-east-1"))
            elif target.provider == "vast":
                stack.set_config(
                    "machine_id", auto.ConfigValue(value=target.instance_id)
                )
                stack.set_config("gpu_name", auto.ConfigValue(value="RTX_4090"))
                stack.set_config(
                    "ssh_pub_key",
                    auto.ConfigValue(value="ssh-rsa AAAAB3NzaC1... dummy-key"),
                )

            up_res = stack.up(on_output=print)

            return {
                "stack_name": stack_name,
                "outputs": {k: v.value for k, v in up_res.outputs.items()},
            }

        return await asyncio.to_thread(_provision)

    async def destroy_node(
        self, stack_name: str, provider: Literal["aws", "vast"]
    ) -> None:
        work_dir = (
            self.templates_dir / f"{provider}_spot"
            if provider == "aws"
            else self.templates_dir / f"{provider}_ai"
        )

        def _destroy() -> None:
            stack = auto.select_stack(stack_name=stack_name, work_dir=str(work_dir))
            stack.destroy(on_output=print)
            stack.workspace.remove_stack(stack_name)

        await asyncio.to_thread(_destroy)

    async def reconcile_state(self) -> list[str]:
        def _reconcile() -> list[str]:
            # Scan through all provider directories for active fleet stacks.
            active_stacks: list[str] = []
            for provider_dir in self.templates_dir.iterdir():
                if provider_dir.is_dir():
                    try:
                        workspace = auto.LocalWorkspace(work_dir=str(provider_dir))
                        stacks = workspace.list_stacks()
                        for stack in stacks:
                            if stack.name.startswith("fleet-worker-"):
                                active_stacks.append(stack.name)
                    except Exception:
                        pass
            return active_stacks

        return await asyncio.to_thread(_reconcile)
