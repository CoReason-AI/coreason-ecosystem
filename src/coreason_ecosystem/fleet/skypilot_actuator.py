# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

try:
    import sky
except ImportError:
    sky = None  # type: ignore

import asyncio
from typing import Any, cast
from loguru import logger
from pydantic import BaseModel
from coreason_manifest.spec.ontology import (
    SpatialHardwareProfile as HardwareProfile,
    EscrowPolicy,
    EpistemicSecurityProfile as SecurityProfile,
)
from coreason_ecosystem.fleet.mesh_injector import MeshInjector


class SkyPilotTarget(BaseModel):
    """Encapsulates spatial hardware configuration objectives targeting SkyPilot orchestration."""

    provider_whitelist: list[str] | None = None
    use_spot: bool = True
    autostop_idle_minutes: int = 10
    hardware_profile: HardwareProfile | None = None
    security_profile: SecurityProfile | None = None
    mesh_auth_key: str | None = None
    temporal_mesh_ip: str | None = None
    escrow_policy: EscrowPolicy | None = None


class SkyPilotActuator:
    """Implement the Governance Plane Actuator using SkyPilot for multi-cloud orchestration.

    Structural Rationale:
    SkyPilot abstracts the multi-cloud spot market (AWS, GCP, Azure, Vast.ai) and provides
    managed recovery for preempted instances. This actuator replaces the custom Pulumi-based
    provisioning logic, adhering to the 'Borrow Do Not Build' architectural mandate.
    """

    def __init__(self) -> None:
        self.injector = MeshInjector()

    async def provision_node(self, target: SkyPilotTarget) -> dict[str, Any]:
        """Execute physical instantiation via SkyPilot managed clusters."""

        # 1. Hardware Mapping
        accelerators = None
        if target.hardware_profile:
            accel_type = target.hardware_profile.accelerator_type or "A100"
            if accel_type.startswith("urn:coreason:accelerator:"):
                accel_type = accel_type.split(":")[-1].upper()
            accel_count = 1  # Default to 1
            accelerators = f"{accel_type}:{accel_count}"

        resources = sky.Resources(
            accelerators=accelerators,
            use_spot=target.use_spot,
        )

        # 2. Mesh Injection Setup
        setup_cmds = []
        cluster_name = f"coreason-sky-{int(asyncio.get_event_loop().time())}"

        if (
            target.hardware_profile
            and target.security_profile
            and target.mesh_auth_key
            and target.temporal_mesh_ip
        ):
            payload_b64 = self.injector.compile_payload(
                node_cid=cluster_name,
                provider="skypilot",  # Abstracted provider
                hardware=target.hardware_profile.model_dump(),
                security=target.security_profile.model_dump(),
                mesh_auth_key=target.mesh_auth_key,
                temporal_mesh_ip=target.temporal_mesh_ip,
            )
            # Inject the payload into the node setup
            setup_cmds.append("mkdir -p /etc/coreason")
            setup_cmds.append(
                f"echo {payload_b64} | base64 -d > /etc/coreason/payload.json"
            )
            setup_cmds.append("/opt/coreason/bin/bootstrap.sh")

        task = sky.Task(
            setup="\n".join(setup_cmds)
            if setup_cmds
            else 'echo "SkyPilot Node Booting..."',
            run="sleep infinity",  # Keep the node alive for the mesh
        )
        task.set_resources(resources)

        logger.info(
            f"SkyPilot: Launching cluster {cluster_name} with {accelerators} (spot={target.use_spot})..."
        )

        def _launch() -> Any:
            rid = sky.launch(
                task,
                cluster_name=cluster_name,
                idle_minutes_to_autostop=target.autostop_idle_minutes,
            )
            return sky.get(rid)

        await asyncio.to_thread(_launch)

        return {"cluster_name": cluster_name, "status": "provisioned"}

    async def destroy_node(self, cluster_name: str) -> None:
        """Terminate a SkyPilot cluster and free all cloud resources."""
        logger.info(f"SkyPilot: Terminating cluster {cluster_name}...")

        def _down() -> Any:
            rid = sky.down(cluster_name)
            return sky.get(rid)

        await asyncio.to_thread(_down)

    async def reconcile_state(self) -> list[dict[str, Any]]:
        """List and summarize all active SkyPilot clusters managed by CoReason."""

        def _status() -> list[dict[str, Any]]:
            rid = sky.status()
            return cast(list[dict[str, Any]], sky.get(rid))

        clusters = await asyncio.to_thread(_status)
        active_nodes = []
        for cluster in clusters:
            name = cluster["name"]
            if name.startswith("coreason-sky-"):
                status = str(cluster["status"])
                # Extract cloud from handle if available
                cloud = "unknown"
                if cluster.get("handle"):
                    try:
                        cloud = cluster["handle"].cloud.name()
                    except Exception:
                        logger.debug(
                            "Failed to extract cloud name from SkyPilot handle"
                        )

                active_nodes.append(
                    {
                        "cluster_name": name,
                        "status": status,
                        "provider": cloud,
                        "vram_capacity": 80.0
                        if "A100" in (str(cluster.get("resources", "")))
                        else 0.0,  # Heuristic
                    }
                )
        return active_nodes

    async def execute_thermodynamic_guillotine(self, threshold_breached: bool) -> None:
        """Sever all SkyPilot nodes if the thermodynamic threshold is breached."""
        if not threshold_breached:
            return

        logger.critical(
            "[SkyPilotActuator] Thermodynamic Guillotine: Severing all infrastructure!"
        )
        nodes = await self.reconcile_state()

        coroutines = [self.destroy_node(node["cluster_name"]) for node in nodes]
        if coroutines:
            await asyncio.gather(*coroutines)


class ThermodynamicAssessment(BaseModel):
    """Diagnostic snapshot of the swarm's thermodynamic expenditure."""

    gpu_utilization: float
    token_velocity: float
    api_cost_hourly: float
    vfe_divergence: float
    threshold_breached: bool


DEFAULT_VFE_THRESHOLD = 0.85


async def assess_thermodynamic_expenditure(
    hardware_profile: HardwareProfile,
    max_budget_hr: float,
    current_gpu_utilization: float = 0.0,
    current_token_velocity: float = 0.0,
    current_api_cost_hourly: float = 0.0,
    vfe_threshold: float = DEFAULT_VFE_THRESHOLD,
) -> ThermodynamicAssessment:
    """Calculate Variational Free Energy divergence for the swarm topology."""
    cost_pressure = (
        current_api_cost_hourly / max_budget_hr if max_budget_hr > 0 else 1.0
    )

    vfe_divergence = 0.6 * current_gpu_utilization + 0.4 * cost_pressure
    breached = vfe_divergence >= vfe_threshold

    if breached:
        logger.critical(
            f"Economic Guillotine: VFE divergence {vfe_divergence:.3f} "
            f">= threshold {vfe_threshold:.3f}. "
            "Emitting TopologicalHaltIntent to sever kinetic execution."
        )

    return ThermodynamicAssessment(
        gpu_utilization=current_gpu_utilization,
        token_velocity=current_token_velocity,
        api_cost_hourly=current_api_cost_hourly,
        vfe_divergence=vfe_divergence,
        threshold_breached=breached,
    )
