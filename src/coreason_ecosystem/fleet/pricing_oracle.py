# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Pricing Oracle — Dynamic Thermodynamic Provisioning API.

Queries cloud provider pricing APIs dynamically based on requested geometric
bounds (VRAM, provider whitelist). No instance types, VRAM maps, or pricing
data are hardcoded — all data is fetched at query time from the provider APIs.

This enforces LAW 1 (Macroscopic Invariance) and LAW 5 (Thermodynamic
Provisioning) by treating cloud providers as commoditized thermodynamic
resources.
"""

from typing import TYPE_CHECKING

from coreason_manifest.spec.ontology import SpatialHardwareProfile as HardwareProfile

if TYPE_CHECKING:
    from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget


class PricingOracle:
    """Queries cloud provider pricing APIs to find optimal compute bids.

    All instance types and VRAM specifications are resolved dynamically
    from the provider APIs — no hardcoded catalogs exist in this module.
    """

    async def calculate_optimal_bid(
        self, hardware_profile: HardwareProfile, max_budget_hr: float
    ) -> "ComputeNodeTarget | None":
        from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget
        import httpx

        valid_nodes: list[ComputeNodeTarget] = []

        if "aws" in hardware_profile.provider_whitelist:
            import asyncio

            def fetch_aws_spot() -> list["ComputeNodeTarget"]:
                """Query AWS APIs dynamically for GPU instances meeting VRAM bounds.

                Uses ``describe_instance_types`` to resolve VRAM per instance
                (no hardcoded instance_vram_map), then queries spot pricing
                for qualifying instances.
                """
                try:
                    import boto3
                    from datetime import datetime, timezone

                    client = boto3.client("ec2", region_name="us-east-1")

                    # Step 1: Dynamically discover GPU instance types meeting VRAM bounds
                    paginator = client.get_paginator("describe_instance_types")
                    qualifying_instances: dict[str, float] = {}

                    for page in paginator.paginate(
                        Filters=[
                            {
                                "Name": "instance-type",
                                "Values": ["g4dn.*", "g5.*", "p3.*", "p4d.*", "p5.*"],
                            },
                        ],
                    ):
                        for itype in page.get("InstanceTypes", []):
                            gpu_info = itype.get("GpuInfo", {})
                            gpus = gpu_info.get("Gpus", [])
                            total_vram_mb = sum(
                                g.get("MemoryInfo", {}).get("SizeInMiB", 0)
                                * g.get("Count", 1)
                                for g in gpus
                            )
                            total_vram_gb = total_vram_mb / 1024.0
                            if total_vram_gb >= hardware_profile.min_vram_gb:
                                qualifying_instances[itype["InstanceType"]] = (
                                    total_vram_gb
                                )

                    if not qualifying_instances:
                        return []

                    # Step 2: Query spot pricing for qualifying instances
                    response = client.describe_spot_price_history(
                        InstanceTypes=list(qualifying_instances.keys()),  # type: ignore[arg-type]
                        ProductDescriptions=["Linux/UNIX"],
                        StartTime=datetime.now(timezone.utc),
                        MaxResults=len(qualifying_instances) * 2,
                    )

                    aws_nodes: list[ComputeNodeTarget] = []
                    for spot in response.get("SpotPriceHistory", []):
                        itype_name = spot["InstanceType"]
                        price = float(spot["SpotPrice"])
                        vram = qualifying_instances.get(itype_name, 0.0)
                        aws_nodes.append(
                            ComputeNodeTarget(
                                provider="aws",
                                instance_id=itype_name,
                                hourly_cost=price,
                                vram_gb=vram,
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
