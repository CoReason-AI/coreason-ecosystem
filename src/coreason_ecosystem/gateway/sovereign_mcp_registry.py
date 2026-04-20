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

Maps URN boundaries to deployed actuator/oracle action spaces. The registry
initializes as an empty substrate and hydrates its routing table dynamically
by reading an external ``capabilities.matrix.yaml`` configuration file,
querying an upstream discovery port, or passively scanning for modules
bearing the ``__action_space_urn__`` attribute (Passive Ontological Projection).
No URN-to-endpoint mappings are hardcoded.

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

import ast
import warnings

import httpx
from loguru import logger

_LEGACY_URN_PREFIXES = ("urn:coreason:oracle:", "urn:coreason:state:")
_ARCHETYPE_PREFIXES = (
    "urn:coreason:archetype_a:storage:",
    "urn:coreason:archetype_b:tools:",
    "urn:coreason:archetype_c:sensory:",
    "urn:coreason:archetype_d:state:",
)


class SovereignMCPRegistry:
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
                match urn.split(":"):
                    case ["urn", "coreason", "oracle" | "state", *_]:
                        warnings.warn(
                            f"Legacy URN prefix detected: '{urn}'. "
                            "'oracle:' and 'state:' are deprecated in favor of 'archetype_*'.",
                            DeprecationWarning,
                            stacklevel=2,
                        )
                    case _:
                        pass

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
                    match urn.split(":"):
                        case ["urn", "coreason", "oracle" | "state", *_]:
                            warnings.warn(
                                f"Legacy URN prefix detected: '{urn}'. "
                                "'oracle:' and 'state:' are deprecated in favor of 'archetype_*'.",
                                DeprecationWarning,
                                stacklevel=2,
                            )
                        case _:
                            pass
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

    @staticmethod
    def validate_archetype_urn(urn: str) -> None:
        """Zero-trust URN prefix validation for newly forged action spaces.

        Rejects any URN that does not begin with one of the canonical
        Four Archetype prefixes.
        """
        match urn.split(":"):
            case [
                "urn",
                "coreason",
                "archetype_a" | "archetype_b" | "archetype_c" | "archetype_d",
                *_,
            ]:
                pass
            case _:
                raise ValueError(
                    f"URN Topology Breach: '{urn}' does not bear a "
                    f"canonical Archetype prefix. "
                    "Rejecting hallucinated capability."
                )

    def scan_action_space_modules(self, scan_dirs: list[Path] | None = None) -> int:
        """Passively discover assets bearing ``__action_space_urn__`` via AST parsing.

        Uses Python's ``ast`` module to parse source files into Abstract Syntax
        Trees — NO module-level code is ever executed (Zero-Trust Passive
        Projection).  Extracts ``__action_space_urn__`` string assignments and
        validates them against the ``urn:coreason:actionspace:`` prefix.

        Args:
            scan_dirs: Directories to scan for ``.py`` files.  Defaults to
                ``['./action_spaces/']`` relative to the current working
                directory.

        Returns:
            Number of newly discovered action spaces registered in the cache.
        """
        if scan_dirs is None:
            scan_dirs = [Path.cwd() / "action_spaces"]

        discovered = 0
        for scan_dir in scan_dirs:
            if not scan_dir.is_dir():
                logger.debug(
                    f"Passive Ontological Projection: scan directory "
                    f"{scan_dir} does not exist — skipping."
                )
                continue

            for py_file in scan_dir.rglob("*.py"):
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError) as e:
                    logger.warning(
                        f"Passive Ontological Projection: failed to parse "
                        f"{py_file}: {e}"
                    )
                    continue

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Assign):
                        continue
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "__action_space_urn__"
                        ):
                            if isinstance(node.value, ast.Constant) and isinstance(
                                node.value.value, str
                            ):
                                urn_value = node.value.value
                                try:
                                    self.validate_archetype_urn(urn_value)
                                except ValueError:
                                    logger.warning(
                                        f"Passive Ontological Projection: "
                                        f"invalid URN '{urn_value}' in {py_file}. "
                                        "Skipping."
                                    )
                                    continue

                                # Register the discovered action space.
                                # Endpoint defaults to the URN itself until
                                # a runtime deployment resolves the physical URI.
                                if urn_value not in self._cache:
                                    self._cache[urn_value] = {
                                        "endpoint": urn_value,
                                        "clearance": "RESTRICTED",
                                        "epistemic_status": "DRAFT",
                                    }
                                    discovered += 1
                                    logger.info(
                                        f"Passive Ontological Projection: "
                                        f"discovered '{urn_value}' in {py_file.name}"
                                    )

        logger.info(
            f"Passive Ontological Projection: {discovered} new action "
            f"space(s) discovered."
        )
        return discovered
