# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

from typing import TYPE_CHECKING

from coreason_manifest.spec.ontology import SpatialHardwareProfile as HardwareProfile

if TYPE_CHECKING:
    from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget


class PricingOracle:
    async def calculate_optimal_bid(
        self, hardware_profile: HardwareProfile, max_budget_hr: float
    ) -> "ComputeNodeTarget | None":
        from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget
        import httpx

        valid_nodes = []

        if "aws" in hardware_profile.provider_whitelist:
            import asyncio
            from datetime import datetime, timezone

            def fetch_aws_spot() -> list["ComputeNodeTarget"]:
                instance_vram_map = {
                    "g4dn.xlarge": 16.0,
                    "g4dn.2xlarge": 16.0,
                    "g4dn.4xlarge": 16.0,
                    "g4dn.8xlarge": 16.0,
                    "g4dn.12xlarge": 16.0,
                    "g5.xlarge": 24.0,
                    "g5.2xlarge": 24.0,
                    "p3.2xlarge": 16.0,
                    "p3.8xlarge": 64.0,
                    "p4d.24xlarge": 320.0,
                }
                valid_instances = [
                    k
                    for k, v in instance_vram_map.items()
                    if v >= hardware_profile.min_vram_gb
                ]
                if not valid_instances:
                    return []
                try:
                    import boto3

                    client = boto3.client("ec2", region_name="us-east-1")
                    response = client.describe_spot_price_history(
                        InstanceTypes=valid_instances,
                        ProductDescriptions=["Linux/UNIX"],
                        StartTime=datetime.now(timezone.utc),
                        MaxResults=len(valid_instances) * 2,
                    )
                    aws_nodes = []
                    for spot in response.get("SpotPriceHistory", []):
                        itype = spot["InstanceType"]
                        price = float(spot["SpotPrice"])
                        aws_nodes.append(
                            ComputeNodeTarget(
                                provider="aws",
                                instance_id=itype,
                                hourly_cost=price,
                                vram_gb=instance_vram_map[itype],
                            )
                        )
                    return aws_nodes
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        f"AWS Boto3 API oracle failed: {e}"
                    )
                    return []

            aws_nodes = await asyncio.to_thread(fetch_aws_spot)
            valid_nodes.extend(aws_nodes)

        if "vast" in hardware_profile.provider_whitelist:
            try:
                async with httpx.AsyncClient() as client:
                    # Query live order book from Vast.ai
                    resp = await client.get(
                        "https://offers.vast.ai/v1/machine_offers", timeout=15.0
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    offers = data.get("offers", [])
                    for offer in offers:
                        vram_mb = offer.get("gpu_ram", 0)
                        vram_gb = vram_mb / 1024.0 if vram_mb else 0.0
                        hourly_cost = offer.get("dph_base", float("inf"))
                        instance_id = str(offer.get("machine_id", "unknown"))
                        valid_nodes.append(
                            ComputeNodeTarget(
                                provider="vast",
                                instance_id=instance_id,
                                hourly_cost=float(hourly_cost),
                                vram_gb=float(vram_gb),
                            )
                        )
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(f"Vast.ai API oracle failed: {e}")

        # Filter nodes based on constraints
        filtered_nodes = []
        for node in valid_nodes:
            if node.provider not in hardware_profile.provider_whitelist:
                continue  # pragma: no cover
            if node.vram_gb < hardware_profile.min_vram_gb:
                continue
            if node.hourly_cost > max_budget_hr:
                continue

            filtered_nodes.append(node)

        if not filtered_nodes:
            return None

        # Return the node with the lowest hourly cost
        return min(filtered_nodes, key=lambda n: n.hourly_cost)
