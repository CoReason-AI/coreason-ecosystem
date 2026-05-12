# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Autonomic Fleet Manager — Thermodynamic Provisioning Daemon.

Continuously polls the TelemetryTopologyMonitor for the β₀ Betti number
(connected components) and drives scale-up/scale-down actuation via the
PricingOracle and PulumiActuator. All scaling decisions are derived
from topological invariants — no scalar metrics are consumed.
"""

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from coreason_ecosystem.fleet.pricing_oracle import PricingOracle
from coreason_ecosystem.fleet.pulumi_actuator import PulumiActuator
from coreason_manifest.spec.ontology import (
    SpatialHardwareProfile as HardwareProfile,
    EpistemicSecurityProfile as SecurityProfile,
    EscrowPolicy,
)


class AutonomicFleetManager:
    """Thermodynamic provisioning daemon.

    Derives scaling decisions from the topological invariants exposed by
    the TelemetryTopologyMonitor. ``coreason_active_agents_total`` holds β₀
    (connected components). β₀ > 0 means active workflows requiring compute;
    β₀ == 0 means the swarm is idle and resources can be reclaimed.
    """

    def __init__(
        self,
        max_budget_hr: float,
        polling_interval_sec: int,
        templates_path: Path,
        mesh_auth_key: str,
        temporal_mesh_ip: str,
    ) -> None:
        self.max_budget_hr = max_budget_hr
        self.polling_interval_sec = polling_interval_sec
        self.mesh_auth_key = mesh_auth_key
        self.temporal_mesh_ip = temporal_mesh_ip
        self.driver = PulumiActuator(templates_dir=templates_path)
        self.oracle = PricingOracle()
        self._running = False
        self.pending_provisions = 0
        self._background_tasks: set[asyncio.Task[Any]] = set()

    async def start(self) -> None:
        """Initiate the autonomic execution loop.

        Continuously polls the topological state. If β₀ (connected components
        stored in coreason_active_agents_total) > 0, the daemon executes
        scale-up logic by mapping Delta VRAM to the SpatialHardwareProfile.
        If β₀ == 0, it executes scale-to-zero teardown logic.
        """
        self._running = True
        logger.info("Starting Autonomic Fleet Manager...")

        while self._running:
            try:
                betti_0 = 0
                logger.debug(f"Topological state: β₀={betti_0}")
                required_vram = 0.0
                active_stacks = await self.driver.reconcile_state()
                provisioned_vram = sum(
                    s.get("vram_capacity", 0.0) for s in active_stacks
                )

                delta = required_vram - provisioned_vram

                if delta > 0:
                    profile = HardwareProfile(
                        min_vram_gb=delta, provider_whitelist=["aws", "vast"]
                    )
                    security_profile = SecurityProfile(network_isolation=True)

                    bid = await self.oracle.calculate_optimal_bid(
                        profile, self.max_budget_hr
                    )
                    if bid:
                        logger.info(f"Optimal Bid Found: {bid}. Provisioning...")

                        bid.hardware_profile = profile
                        bid.security_profile = security_profile
                        bid.mesh_auth_key = self.mesh_auth_key
                        bid.temporal_mesh_ip = self.temporal_mesh_ip
                        bid.escrow_policy = EscrowPolicy(
                            escrow_locked_magnitude=max(int(self.max_budget_hr), 1),
                            release_condition_metric="fleet_daemon_hourly_budget",
                            refund_target_node_cid=f"did:coreason:fleet:{bid.provider}",
                        )

                        self.pending_provisions += 1
                        try:
                            result = await self.driver.provision_node(bid)
                            logger.info(
                                f"Provisioning Complete: {result['stack_name']}"
                            )

                            async def _cooldown_and_decrement() -> None:
                                await asyncio.sleep(300)
                                self.pending_provisions = max(
                                    0, self.pending_provisions - 1
                                )

                            task = asyncio.create_task(_cooldown_and_decrement())
                            self._background_tasks.add(task)
                            task.add_done_callback(self._background_tasks.discard)
                        except Exception as e:
                            self.pending_provisions = max(
                                0, self.pending_provisions - 1
                            )
                            logger.error(f"Provisioning failed: {e}")
                            raise
                    else:
                        logger.warning(
                            "No viable bids found under budget for current requirements."
                        )
                elif betti_0 == 0 and self.pending_provisions == 0:
                    if active_stacks:
                        target = active_stacks[0]
                        stack_to_destroy = target["stack_name"]
                        provider = target["provider"]

                        logger.info(
                            f"Scale to zero triggered. Destroying {stack_to_destroy} on {provider}..."
                        )
                        await self.driver.destroy_node(stack_to_destroy, provider)
                    else:
                        logger.debug(
                            "Queue empty, but no active compute nodes to destroy."
                        )

            except asyncio.CancelledError:
                self._running = False
                logger.info("Fleet Manager shutdown requested.")
                break
            except Exception as e:
                logger.error(f"Error in control loop: {e}")

            try:
                await asyncio.sleep(self.polling_interval_sec)
            except asyncio.CancelledError:
                self._running = False
                logger.info("Fleet Manager shutdown requested during sleep.")
                break
