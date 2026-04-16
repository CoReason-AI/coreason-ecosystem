# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Capability Registry — Dynamic URN Routing Table.

Maps URN boundaries to deployed action spaces. The registry initializes
as an empty substrate and hydrates its routing table dynamically by reading
an external ``capabilities.matrix.yaml`` configuration file or querying an
upstream discovery port. No URN-to-endpoint mappings are hardcoded.

Each capability entry tracks:
  - ``endpoint``: Physical network URI of the deployed action space.
  - ``clearance``: LBAC clearance level (PUBLIC / CONFIDENTIAL / RESTRICTED).
  - ``epistemic_status``: SRB governance lifecycle phase
    (DRAFT / SRB_APPROVED / CLIENT_APPROVED / PUBLISHED).

This enforces LAW 1 (Macroscopic Invariance) by keeping the Governance Plane
immune to domain-level semantic drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from loguru import logger


class CapabilityRegistry:
    """Dynamic routing table linking URN boundaries to deployed action spaces.

    Initializes empty and must be hydrated via ``hydrate_from_matrix()``
    (reading a ``capabilities.matrix.yaml``) or ``hydrate_from_discovery_port()``
    (querying an upstream discovery endpoint) before operation.
    """

    CLEARANCE_LEVELS = {
        "PUBLIC": 1,
        "CONFIDENTIAL": 2,
        "RESTRICTED": 3,
    }

    def __init__(self) -> None:
        """Initialize the capability registry with an empty routing table."""
        self._cache: dict[str, dict[str, str]] = {}

    def hydrate_from_matrix(self, matrix_path: Path | None = None) -> None:
        """Hydrate the URN routing table from a ``capabilities.matrix.yaml`` file.

        Args:
            matrix_path: Path to the YAML matrix file. Defaults to
                ``./capabilities.matrix.yaml`` relative to the current
                working directory.

        Raises:
            FileNotFoundError: If the matrix file does not exist.
        """
        import yaml

        if matrix_path is None:
            matrix_path = Path.cwd() / "capabilities.matrix.yaml"

        if not matrix_path.exists():
            logger.warning(
                f"Capability matrix not found at {matrix_path}. "
                "Registry remains empty — operating in discovery-only mode."
            )
            return

        raw = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
        capabilities: list[dict[str, Any]] = raw.get("capabilities", [])

        for entry in capabilities:
            urn = entry.get("urn", "")
            endpoint = entry.get("endpoint", "")
            clearance = entry.get("clearance", "RESTRICTED")
            epistemic_status = entry.get("epistemic_status", "DRAFT")
            if urn and endpoint:
                self._cache[urn] = {
                    "endpoint": endpoint,
                    "clearance": clearance,
                    "epistemic_status": epistemic_status,
                }

        logger.info(f"Hydrated {len(self._cache)} capabilities from {matrix_path.name}")

    async def hydrate_from_discovery_port(self, discovery_url: str) -> None:
        """Hydrate the URN routing table from an upstream discovery endpoint.

        Queries the discovery port and merges the returned capabilities
        into the local routing cache. Existing entries are overwritten
        if the upstream provides a newer mapping.

        Args:
            discovery_url: The URL of the upstream discovery service.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(discovery_url, timeout=10.0)
                resp.raise_for_status()
                data = resp.json()

            capabilities: list[dict[str, Any]] = data.get("capabilities", [])
            for entry in capabilities:
                urn = entry.get("urn", "")
                endpoint = entry.get("endpoint", "")
                clearance = entry.get("clearance", "RESTRICTED")
                epistemic_status = entry.get("epistemic_status", "DRAFT")
                if urn and endpoint:
                    self._cache[urn] = {
                        "endpoint": endpoint,
                        "clearance": clearance,
                        "epistemic_status": epistemic_status,
                    }

            logger.info(
                f"Hydrated {len(capabilities)} capabilities from {discovery_url}"
            )
        except Exception as e:
            logger.warning(f"Discovery port hydration failed: {e}")

    async def discover_active_substrates(
        self, agent_clearance: str = "PUBLIC"
    ) -> dict[str, str]:
        """Interrogates the routing table to resolve available subsystems.

        Applies epistemic masking based on the agent's clearance level.

        Args:
            agent_clearance: The semantic clearance of the requesting agent.

        Returns:
            A mapping of URN strings to physical network actionSpaceId URIs.
        """
        agent_level = self.CLEARANCE_LEVELS.get(agent_clearance, 0)

        masked_substrates: dict[str, str] = {}
        for urn, data in self._cache.items():
            required_clearance = data.get("clearance", "RESTRICTED")
            required_level = self.CLEARANCE_LEVELS.get(required_clearance, 3)

            if agent_level >= required_level:
                masked_substrates[urn] = data["endpoint"]

        return masked_substrates

    def resolve_urn(self, target_urn: str) -> str:
        """Strict physical lookup over the active substrates.

        Args:
            target_urn: The URN of the capability to resolve.

        Returns:
            The mapped physical endpoint URI.

        Raises:
            KeyError: if the target_urn is not in the registry.
        """
        if target_urn not in self._cache:
            raise KeyError(f"Geometrical topology fault: unregistered URN {target_urn}")

        return self._cache[target_urn]["endpoint"]

    def get_epistemic_status(self, target_urn: str) -> str:
        """Retrieve the SRB governance lifecycle status for a registered URN.

        Args:
            target_urn: The URN to query.

        Returns:
            The epistemic status string (DRAFT, SRB_APPROVED,
            CLIENT_APPROVED, or PUBLISHED).  Defaults to ``"DRAFT"``
            if the URN is not registered.
        """
        entry = self._cache.get(target_urn)
        if entry is None:
            return "DRAFT"
        return entry.get("epistemic_status", "DRAFT")
