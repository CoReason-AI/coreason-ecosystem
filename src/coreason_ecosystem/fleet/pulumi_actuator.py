import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from coreason_ecosystem.fleet.pricing_oracle import ThermodynamicAssessment

from loguru import logger
from pydantic import BaseModel
from pulumi import automation as auto

from coreason_ecosystem.fleet.mesh_injector import MeshInjector
from coreason_manifest.spec.ontology import (
    EpistemicSecurityProfile as SecurityProfile,
)
from coreason_manifest.spec.ontology import (
    EscrowPolicy,
)
from coreason_manifest.spec.ontology import (
    SpatialHardwareProfile as HardwareProfile,
)
from coreason_manifest.spec.ontology import ChaosExperimentTask


class ComputeNodeTarget(BaseModel):
    """Encapsulates spatial hardware configuration objectives targeting defined spatial clouds.

    Attributes:
        provider: Differentiates orchestration bounds ('aws' or 'vast').
        instance_id: Hard target bounds for deployment profiles.
        hourly_cost: Estimated projection scalar in decimal dollars.
        vram_gb: Allocated visual random access unit count constraints.
        hardware_profile: The epistemic hardware ontology projection bounds.
        security_profile: The mesh security requirements context constraint.
        mesh_auth_key: A topological node bridging structural integrity vector.
        temporal_mesh_ip: Target edge projection endpoint routing destination.
        escrow_policy: The locked economic transaction guarantee enforcing thermodynamic boundaries.
    """

    provider: Literal["aws", "vast"]
    instance_id: str
    hourly_cost: float
    vram_gb: float
    hardware_profile: HardwareProfile | None = None
    security_profile: SecurityProfile | None = None
    mesh_auth_key: str | None = None
    temporal_mesh_ip: str | None = None
    escrow_policy: EscrowPolicy | None = None
    market_type: Literal["spot", "on-demand"] | None = None


ATOMIC_MAGNITUDE_MULTIPLIER = 10000


class PulumiActuator:
    """Implement the Governance Plane Actuator with strict thermodynamic routing bounds.

    Structural Rationale:
    This class adheres to the Hollow Plane Mandate by eliminating direct logical
    calculations and strictly projecting infrastructure mappings using the Pulumi
    Automation API. To achieve an event-driven performance envelope the actuator maintains
    a local cache (`_cached_stacks`) tracking orchestration instances synchronized against
    a TTL constraint track (`_last_sync_time`). The underlying mechanism requires threading
    controls bounded strictly by an initialized `_lock` preventing concurrent CLI process spawns.
    Cache resets exclusively occur during mutating orchestration calls enforcing downstream constraints.
    """

    def __init__(self, templates_dir: Path) -> None:
        """Instantiate the Actuator matrix cache bounds constraint configurations.

        Args:
            templates_dir (Path): The Epistemic Substrate bounds directory housing Pulumi stacks.
        """
        self.templates_dir = templates_dir
        self.injector = MeshInjector()
        self._cached_stacks: list[dict[str, Any]] | None = None
        self._last_sync_time = 0.0
        self._lock = asyncio.Lock()

    async def provision_node(self, target: ComputeNodeTarget) -> dict[str, str]:
        """Execute physical instantiation bounds evaluating thermodynamic guillotine bounds.

        Args:
            target (ComputeNodeTarget): Desired thermodynamic payload instantiation details.

        Returns:
            dict[str, str]: Structural outputs mapping the node deployment keys.

        Hardware Guillotine Protocol:
        The routine transmits an intent checking the bounds of an `escrow_policy`. Cost scaling is
        evaluated via an atomic multiplier unit (10000x scalar) preventing floating point IEEE 754
        errors during comparison against strict token bounds natively attached to the policy constraints.
        Upon valid completion of the Pulumi `stack.up()` instantiation, the local thermodynamic
        cache state flag (`_last_sync_time`) is forcefully invalidated bounding downstream refreshes.
        """
        if target.escrow_policy is None:
            raise ValueError(
                "Hardware Guillotine: Provisioning rejected — no EscrowPolicy attached. "
                "The runtime must transmit a ComputeProvisioningIntent with a valid escrow."
            )

        cost_atomic = int(target.hourly_cost * ATOMIC_MAGNITUDE_MULTIPLIER)
        if cost_atomic > target.escrow_policy.escrow_locked_magnitude:
            raise ValueError(
                f"Hardware Guillotine: hourly_cost {target.hourly_cost} "
                f"(atomic={cost_atomic}) exceeds escrow_locked_magnitude "
                f"({target.escrow_policy.escrow_locked_magnitude})."
            )

        stack_name = f"fleet-worker-{uuid.uuid4().hex[:8]}"
        provider_dir = self.templates_dir / (
            "aws_spot" if target.provider == "aws" else "vast_ai"
        )

        logger.info(f"Provisioning {target.provider} node on stack {stack_name}...")

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
                node_cid=stack_name,
                provider=target.provider,
                hardware=target.hardware_profile.model_dump(),
                security=target.security_profile.model_dump(),
                mesh_auth_key=target.mesh_auth_key,
                temporal_mesh_ip=target.temporal_mesh_ip,
            )
            stack.set_config("boot_payload_b64", auto.ConfigValue(value=payload_b64))

        if target.market_type:
            stack.set_config("market_type", auto.ConfigValue(target.market_type))

        if target.provider == "aws":
            stack.set_config("instance_type", auto.ConfigValue(target.instance_id))
            stack.set_config(
                "ami_id",
                auto.ConfigValue(os.environ.get("AWS_AMI_ID", "ami-strict-required")),
            )
            stack.set_config(
                "ssh_pub_key",
                auto.ConfigValue(os.environ.get("SSH_PUB_KEY", "strict-key-required")),
            )
            stack.set_config(
                "aws:region",
                auto.ConfigValue(os.environ.get("AWS_REGION", "us-east-1")),
            )
        elif target.provider == "vast":
            stack.set_config("machine_id", auto.ConfigValue(target.instance_id))
            accel_type = (
                target.hardware_profile.accelerator_type
                if target.hardware_profile
                else "unknown"
            )
            stack.set_config("gpu_name", auto.ConfigValue(accel_type))
            stack.set_config(
                "ssh_pub_key",
                auto.ConfigValue(os.environ.get("SSH_PUB_KEY", "strict-key-required")),
            )

        up_res = stack.up(
            on_output=lambda msg: logger.debug(f"Pulumi [{stack_name}]: {msg.strip()}")
        )

        logger.info(f"Node provisioned on stack {stack_name} successfully.")

        self._last_sync_time = 0.0

        return {
            "stack_name": stack_name,
            "outputs": str({k: v.value for k, v in up_res.outputs.items()}),
        }

    async def destroy_node(
        self, stack_name: str, provider: Literal["aws", "vast"]
    ) -> None:
        """Physically sever localized infrastructure target configurations via provider API maps.

        Args:
            stack_name (str): Identifier bounded exclusively for this runtime environment.
            provider (Literal['aws', 'vast']): Evaluated target orchestrator destination bounds.

        Structural Rationale:
        Eliminates topological state mapped to the physical stack. Strictly triggers local
        thermodynamic cache invalidation mapping zero threshold downstream requiring logical
        CLI synchronization on proceeding reconcile iterations.
        """
        provider_dir = self.templates_dir / (
            "aws_spot" if provider == "aws" else "vast_ai"
        )
        logger.info(f"Destroying {provider} node on stack {stack_name}...")

        stack = auto.select_stack(
            stack_name=stack_name,
            work_dir=str(provider_dir),
        )

        stack.destroy(
            on_output=lambda msg: logger.debug(f"Pulumi [{stack_name}]: {msg.strip()}")
        )
        stack.workspace.remove_stack(stack_name)
        logger.info(f"Stack {stack_name} destroyed and removed.")

        self._last_sync_time = 0.0

    async def reconcile_state(self) -> list[dict[str, Any]]:
        """Determine structural matrix allocations bridging local cache mapping non-blocking operations.

        Structural Rationale:
        Implements throttled hybrid polling evaluating TTL constraints against 600.0 second
        boundaries utilizing local synchronization tracking `_last_sync_time`. Prevents concurrent
        thread thundering execution execution using the local module constraint `_lock`. Explicitly
        maps active allocations natively into dictionary projection structures without caching the CLI.
        Provider mapping evaluation natively extracts provider bounds parsing localized node names.

        Returns:
            list[dict[str, Any]]: The array projection bounds outlining temporal cluster instances.
        """
        async with self._lock:
            if (
                self._cached_stacks is not None
                and (time.time() - self._last_sync_time) < 600.0
            ):
                return self._cached_stacks

            def _reconcile() -> list[dict[str, Any]]:
                active_stacks: list[dict[str, Any]] = []
                for provider_dir in self.templates_dir.iterdir():
                    if provider_dir.is_dir():
                        provider = "aws" if "aws" in provider_dir.name else "vast"
                        try:
                            workspace = auto.LocalWorkspace(work_dir=str(provider_dir))
                            stacks = workspace.list_stacks()
                            for stack in stacks:
                                if stack.name.startswith("fleet-worker-"):
                                    s = auto.select_stack(
                                        stack_name=stack.name,
                                        work_dir=str(provider_dir),
                                    )
                                    outs = s.outputs()
                                    m_type = (
                                        outs["market_type"].value
                                        if "market_type" in outs
                                        else "spot"
                                    )
                                    active_stacks.append(
                                        {
                                            "stack_name": stack.name,
                                            "provider": provider,
                                            "market_type": m_type,
                                        }
                                    )
                                    logger.warning(
                                        f"Orphaned stack found: {stack.name} in {provider} ({m_type})"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Failed to read Pulumi workspace in {provider_dir}: {e}"
                            )
                return active_stacks

            active_stacks_resolved = await asyncio.to_thread(_reconcile)
            self._cached_stacks = active_stacks_resolved
            self._last_sync_time = time.time()
            return active_stacks_resolved

    async def execute_thermodynamic_guillotine(
        self, assessment: "ThermodynamicAssessment"
    ) -> None:
        """Physically sever all kinetic nodes checking global VFE threshold divergence bounds.

        Structural Rationale:
        The termination sequence aggregates all localized runtime instances utilizing an
        asynchronous synchronization envelope bound temporally at 600 seconds. Fault tolerance
        flags eliminate single instance failures cascading onto the wider bounds ensuring pure
        global economic termination deceleration checks.

        Args:
            assessment (ThermodynamicAssessment): The physical bounds struct resolving constraints.
        """
        if not assessment.threshold_breached:
            return

        logger.critical(
            "[PulumiActuator] Economic Guillotine triggered! VFE divergence "
            f"{assessment.vfe_divergence:.3f} breached threshold. "
            "Severing all autonomous infrastructure..."
        )

        active_stacks = await self.reconcile_state()

        coroutines = [
            self.destroy_node(
                stack["stack_name"], cast(Literal["aws", "vast"], stack["provider"])
            )
            for stack in active_stacks
        ]

        if not coroutines:
            return

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*coroutines, return_exceptions=True), timeout=600.0
            )
            for stack, result in zip(active_stacks, results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Failed to sever node {stack['stack_name']}: {result}"
                    )
        except asyncio.TimeoutError:
            logger.error(
                "Thermodynamic guillotine bounds breached. Actuation timed out after 600.0s."
            )


async def inject_chaos_fault(manifest: ChaosExperimentTask) -> None:
    """Inject a chaos fault based on the experiment task manifest.

    Executes the thermodynamic infrastructure disruption (Chaos Engineering).
    """
    logger.info(
        f"[Thermodynamic Actuator] Injecting chaos fault: {manifest.experiment_cid}"
    )
    
    from pathlib import Path
    # The default location for the ephemeral infrastructure templates
    actuator = PulumiActuator(templates_dir=Path("infrastructure/ephemeral"))
    
    for fault in manifest.faults:
        if fault.target_node_cid:
            logger.warning(f"Severing specific target node: {fault.target_node_cid}")
            active_stacks = await actuator.reconcile_state()
            for stack in active_stacks:
                if stack["stack_name"] == fault.target_node_cid:
                    from typing import cast, Literal
                    await actuator.destroy_node(stack["stack_name"], cast(Literal["aws", "vast"], stack["provider"]))
        else:
            logger.warning("Swarm-wide chaos fault requested, escalating to thermodynamic guillotine.")
            from coreason_ecosystem.fleet.pricing_oracle import ThermodynamicAssessment
            assessment = ThermodynamicAssessment(
                threshold_breached=True,
                vfe_divergence=fault.intensity * 100.0,
                current_epistemic_value=0.0,
                current_thermodynamic_cost=1000.0,
                gpu_utilization=100.0,
                token_velocity=0.0,
                api_cost_hourly=10.0
            )
            await actuator.execute_thermodynamic_guillotine(assessment)
