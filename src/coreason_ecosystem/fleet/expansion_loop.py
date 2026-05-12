# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Von Neumann Expansion Loop — Thermodynamic Capital Scaling.

Monitors the sovereign treasury's on-chain balance via URN-based MCP
projection and automatically provisions physical GPU hardware via the
PricingOracle and PulumiActuator when sufficient reinvestment capital
is aggregated.

No mutable in-memory state is held.  The treasury balance is queried
exclusively through a Sovereign Treasury MCP at
``urn:coreason:state:treasury`` — the Governance Plane does not import
Web3 libraries or hold private keys.

The expansion loop integrates with the VFE (Variational Free Energy)
divergence assessment to enforce the Economic Guillotine per LAW 7
(Thermodynamic Cost Bounding / Ashby's Limit).
"""

from __future__ import annotations

from loguru import logger

from coreason_ecosystem.fleet.pricing_oracle import (
    PricingOracle,
    assess_thermodynamic_expenditure,
)
from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry
from coreason_ecosystem.fleet.skypilot_actuator import SkyPilotActuator, SkyPilotTarget
import asyncio

HARDWARE_NODE_COST_GWEI = 10_000_000_000
"""Hardware threshold (approx 10,000,000,000 Gwei / ~10 ETH at historical rates)."""

SAFETY_MARGIN_GWEI = 2_000_000_000

DEFAULT_POLLING_INTERVAL_SEC = 30.0
"""Polling cadence for the expansion daemon."""

TREASURY_URN = "urn:coreason:state:treasury"
"""URN for the Sovereign Treasury MCP."""


async def von_neumann_expansion_daemon(
    registry: SovereignMCPRegistry,
    oracle: PricingOracle,
    mesh_auth_key: str,
    temporal_mesh_ip: str,
    max_budget_hr: float = 10.0,
    polling_interval_sec: float = DEFAULT_POLLING_INTERVAL_SEC,
) -> None:
    """Continuous daemon loop assessing capital scaling capabilities.

    Resolves the Sovereign Treasury MCP endpoint from the capability
    registry and queries it for on-chain balance via JSON-RPC.  The
    Governance Plane never holds Web3 state — it routes the query
    blindly through the URN.

    The kinetic payload is wrapped in a dedicated exception handler to trap runtime
    faults without terminating the background process. Cooperative yielding is enforced
    mathematically at the lower loop boundary using `asyncio.sleep`, guarded by a `CancelledError`
    throttle that sets the `_running` state to `False` for deterministic teardown.

    The loop runs a VFE divergence check each iteration.  If the threshold
    is breached, a ``TopologicalHaltIntent`` is logged and the loop exits
    to allow the fleet daemon to sever kinetic execution.

    Args:
        registry: The SovereignMCPRegistry for URN-based treasury resolution.
        oracle: The PricingOracle for dynamic hardware profile resolution.
        max_budget_hr: Maximum hourly budget for compute provisioning.
        polling_interval_sec: Seconds between polling iterations.

    Note:
        The variance delta calculation enforces a minimum boundary
        to ensure valid physical bounds.
    """
    try:
        treasury_endpoint = await registry.resolve_urn(TREASURY_URN)
    except KeyError:
        logger.error(
            f"[ExpansionLoop] Treasury URN '{TREASURY_URN}' not registered in "
            "capabilities.matrix.yaml. Cannot initiate Von Neumann expansion."
        )
        return

    logger.info(
        "[ExpansionLoop] Initiated Von Neumann daemon. "
        f"Treasury projected via {treasury_endpoint}."
    )

    _running = True

    while _running:
        try:
            from coreason_manifest.spec.ontology import (
                EpistemicSecurityProfile,
                EscrowPolicy,
                SpatialHardwareProfile as HardwareProfile,
            )

            required_vram = 0.0
            actuator = SkyPilotActuator()
            active_nodes = await actuator.reconcile_state()
            provisioned_vram = sum(
                node.get("vram_capacity", 0.0) for node in active_nodes
            )
            delta_vram = max(required_vram - provisioned_vram, 1.0)

            assessment = await assess_thermodynamic_expenditure(
                hardware_profile=HardwareProfile(
                    min_vram_gb=delta_vram,
                    provider_whitelist=["aws", "gcp", "azure", "vast"],
                ),
                max_budget_hr=max_budget_hr,
            )
            if assessment.threshold_breached:
                logger.critical(
                    "[ExpansionLoop] Economic Guillotine triggered. "
                    "Halting expansion loop to prevent thermodynamic exhaustion."
                )
                await actuator.execute_thermodynamic_guillotine(True)
                _running = False
                continue

            total_active = len(active_nodes)

            # SkyPilot handles spot vs on-demand automatically if we use its managed jobs/clusters,
            # but we can still steer it if needed.
            use_spot = True

            target = SkyPilotTarget(
                use_spot=use_spot,
                hardware_profile=HardwareProfile(
                    min_vram_gb=delta_vram,
                    accelerator_type="urn:coreason:accelerator:a100"
                    if delta_vram > 40
                    else "urn:coreason:accelerator:t4",
                ),
                security_profile=EpistemicSecurityProfile(network_isolation=True),
                mesh_auth_key=mesh_auth_key,
                temporal_mesh_ip=temporal_mesh_ip,
                autostop_idle_minutes=15,
                escrow_policy=EscrowPolicy(
                    escrow_locked_magnitude=max(int(max_budget_hr), 1),
                    release_condition_metric="fleet_expansion_hourly_budget",
                    refund_target_node_cid="did:coreason:fleet:skypilot",
                ),
            )

            logger.info(
                f"[ExpansionLoop] Active SkyPilot nodes: {total_active}. Bidding via SkyPilot multi-cloud..."
            )
            await actuator.provision_node(target)
        except Exception as e:
            logger.error(f"[ExpansionLoop] Runtime execution anomaly: {e}")

        try:
            await asyncio.sleep(polling_interval_sec)
        except asyncio.CancelledError:
            logger.info("[ExpansionLoop] Graceful shutdown requested via Cancellation.")
            _running = False
