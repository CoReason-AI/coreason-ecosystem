# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.
#


from typing import TYPE_CHECKING

from coreason_manifest.spec.ontology import HardwareProfile, SecurityProfile  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget


class PricingOracle:
    async def calculate_optimal_bid(
        self, hardware_profile: HardwareProfile, max_budget_hr: float
    ) -> "ComputeNodeTarget | None":
        from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget
        # Mock order book for available nodes
        order_book = [
            ComputeNodeTarget(
                provider="aws",
                instance_id="t3.micro",
                hourly_cost=0.01,
                vram_gb=0.0,
            ),
            ComputeNodeTarget(
                provider="vast",
                instance_id="12345",
                hourly_cost=0.40,
                vram_gb=24.0,  # e.g., RTX_4090
            ),
            ComputeNodeTarget(
                provider="aws",
                instance_id="p3.2xlarge",
                hourly_cost=3.06,
                vram_gb=16.0,
            ),
        ]

        # Filter nodes based on constraints
        valid_nodes = []
        for node in order_book:
            if node.provider not in hardware_profile.provider_whitelist:
                continue
            if node.vram_gb < hardware_profile.min_vram_gb:
                continue
            if node.hourly_cost > max_budget_hr:
                continue

            valid_nodes.append(node)

        if not valid_nodes:
            return None

        # Return the node with the lowest hourly cost
        return min(valid_nodes, key=lambda n: n.hourly_cost)
