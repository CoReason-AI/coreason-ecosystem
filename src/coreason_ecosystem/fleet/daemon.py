# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.

import asyncio
from pathlib import Path

from loguru import logger

from coreason_ecosystem.fleet.pricing_oracle import PricingOracle
from coreason_ecosystem.fleet.pulumi_actuator import PulumiFleetDriver
from coreason_ecosystem.fleet.temporal_monitor import ThermodynamicMonitor


class AutonomicFleetManager:
    def __init__(
        self,
        max_budget_hr: float,
        polling_interval_sec: int,
        templates_path: Path,
    ) -> None:
        self.max_budget_hr = max_budget_hr
        self.polling_interval_sec = polling_interval_sec
        self.driver = PulumiFleetDriver(templates_dir=templates_path)
        self.oracle = PricingOracle()
        self.monitor = ThermodynamicMonitor()
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Starting Autonomic Fleet Manager...")

        while self._running:
            try:
                derivative = await self.monitor.get_queue_derivative()
                logger.debug(f"Queue Derivative: {derivative}")

                if derivative > 0:
                    # Scale Up Logic
                    profile = await self.monitor.get_active_task_hardware_profile()
                    if profile:
                        bid = await self.oracle.calculate_optimal_bid(
                            profile, self.max_budget_hr
                        )
                        if bid:
                            logger.info(f"Optimal Bid Found: {bid}. Provisioning...")
                            result = await self.driver.provision_node(bid)
                            logger.info(
                                f"Provisioning Complete: {result['stack_name']}"
                            )
                        else:
                            logger.warning(
                                "No viable bids found under budget for current requirements."
                            )
                elif derivative == 0:
                    # Scale Down Logic
                    active_stacks = await self.driver.reconcile_state()
                    if active_stacks:
                        target = active_stacks[0]
                        stack_to_destroy = target["stack_name"]
                        provider = target["provider"]

                        logger.info(
                            f"Scale to zero triggered. Destroying {stack_to_destroy} on {provider}..."
                        )
                        # Pass the dynamically resolved provider to the actuator
                        await self.driver.destroy_node(stack_to_destroy, provider)  # type: ignore[arg-type]
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
