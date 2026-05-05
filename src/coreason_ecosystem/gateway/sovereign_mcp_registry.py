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

import ast
import asyncio
import re
import warnings
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from temporalio import workflow
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.worker import Worker

_LEGACY_URN_PREFIXES = ("urn:coreason:oracle:", "urn:coreason:state:")
_ARCHETYPE_PREFIXES = (
    "urn:coreason:archetype_a:storage:",
    "urn:coreason:archetype_b:tools:",
    "urn:coreason:archetype_c:sensory:",
    "urn:coreason:archetype_d:state:",
)

# Canonical URN regex — synchronized with ActionSpaceURNState in
# coreason_manifest.spec.ontology.  Supports federated namespace
# authorities (e.g. coreason, nlm, ohdsi).
_ACTIONSPACE_URN_PATTERN = re.compile(
    r"^urn:[a-z0-9_]+:actionspace:(oracle|solver|effector|substrate|sensory|node):[a-z0-9_]+:v[0-9]+$"
)
_VALID_CATEGORIES = frozenset(
    {"oracle", "solver", "effector", "substrate", "sensory", "node"}
)


@workflow.defn
class RegistryStateWorkflow:
    """Temporal workflow to hold the routing table state.

    This fulfills the decentralized registry pattern avoiding Redis/etcd dependencies
    and utilizing Temporal's native state execution fabric.
    """

    def __init__(self) -> None:
        """Initialize the empty routing cache."""
        self._cache: dict[str, dict[str, str]] = {}

    @workflow.run
    async def run(self) -> None:
        """Keep the workflow active indefinitely to serve queries and signals."""
        while True:
            await workflow.wait_condition(lambda: False)

    @workflow.signal
    def update_urn(
        self,
        urn: str,
        endpoint: str,
        clearance: str,
        epistemic_status: str,
        content_hash: str = "",
    ) -> None:
        """Update a specific URN mapping in the state cache."""
        self._cache[urn] = {
            "endpoint": endpoint,
            "clearance": clearance,
            "epistemic_status": epistemic_status,
            "content_hash": content_hash,
        }

    @workflow.query
    def get_state(self) -> dict[str, dict[str, str]]:
        """Retrieve the entire registry state cache."""
        return self._cache


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
        """Initialize the capability registry client wrapper."""
        self._client: Client | None = None
        self._worker: Worker | None = None
        self._worker_task: asyncio.Task[Any] | None = None
        self._workflow_id = "sovereign-registry-workflow"

    async def initialize(self, temporal_url: str = "localhost:7233") -> None:
        """Connect to Temporal and spin up the routing workflow and worker."""
        if self._client:
            return

        self._client = await Client.connect(temporal_url)
        self._worker = Worker(
            self._client,
            task_queue="registry-task-queue",
            workflows=[RegistryStateWorkflow],
        )

        # Start the worker in the background
        self._worker_task = asyncio.create_task(self._worker.run())

        try:
            await self._client.start_workflow(
                RegistryStateWorkflow.run,
                id=self._workflow_id,
                task_queue="registry-task-queue",
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            )
        except WorkflowAlreadyStartedError:
            logger.info(f"Registry workflow {self._workflow_id} already running.")

    async def shutdown(self) -> None:
        """Gracefully shutdown the background Temporal worker."""
        if hasattr(self, "_worker_task") and self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _update_urn(
        self,
        urn: str,
        endpoint: str,
        clearance: str,
        epistemic_status: str,
        content_hash: str = "",
    ) -> None:
        """Send a signal to update the state in the Temporal workflow."""
        if not self._client:
            raise RuntimeError("Registry not initialized. Call initialize() first.")
        handle = self._client.get_workflow_handle(self._workflow_id)
        await handle.signal(
            RegistryStateWorkflow.update_urn,
            args=[urn, endpoint, clearance, epistemic_status, content_hash],
        )

    async def _get_state(self) -> dict[str, dict[str, str]]:
        """Query the current state from the Temporal workflow."""
        if not self._client:
            return {}
        handle = self._client.get_workflow_handle(self._workflow_id)
        return await handle.query(RegistryStateWorkflow.get_state)

    async def hydrate_from_matrix(self, matrix_path: Path | None = None) -> None:
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

        count = 0
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

                await self._update_urn(urn, endpoint, clearance, epistemic_status)
                count += 1

        logger.info(f"Hydrated {count} capabilities from {matrix_path.name}")

    async def hydrate_from_compiled_matrix(self, json_path: Path) -> None:
        """Hydrate the URN routing table from a compiled JSON matrix.

        Implements Dynamic Endpoint Interpolation: The AST ledger does not
        include physical endpoints. This method parses the URN geometry to
        synthesize the `target_endpoint_uri` dynamically, converting
        underscores to hyphens for valid DNS mapping prior to strict
        Pydantic instance validation.

        Args:
            json_path: Path to the JSON matrix file.
        """
        import json
        from coreason_manifest.spec.ontology import (
            FederatedSecurityMacroManifest,
            SemanticClassificationProfile,
        )

        raw = json.loads(json_path.read_text(encoding="utf-8"))
        count = 0
        for urn, metadata in raw.items():
            if "target_endpoint_uri" not in metadata:
                urn_parts = urn.split(":")
                if len(urn_parts) >= 2:
                    bundle_name = urn_parts[-2]
                    dns_name = bundle_name.replace("_", "-")
                    metadata["target_endpoint_uri"] = f"http://{dns_name}:8000"

            # Coerce clearance string to Enum for Pydantic V2 strict instance checks
            if "required_clearance" in metadata and isinstance(
                metadata["required_clearance"], str
            ):
                try:
                    metadata["required_clearance"] = SemanticClassificationProfile(
                        metadata["required_clearance"].lower()
                    )
                except ValueError as e:
                    logger.warning(f"Clearance validation failure for {urn}: {e}")

            # Epistemic status might not be in the strict macro manifest, extract it first
            epistemic_status = metadata.pop("epistemic_status", "DRAFT")

            # Extract the content-addressed hash for zero-trust verification
            content_hash = metadata.pop("content_hash", "")

            # Extract capability metadata fields that are not part of FederatedSecurityMacroManifest.
            # These fields are injected by the coreason-urn-authority compile_registry.py
            # and must be stripped before strict Pydantic validation (CoreasonBaseState extra='forbid').
            capability_metadata: dict[str, Any] = {
                "path": metadata.pop("path", ""),
                "default_clearance_tiers": metadata.pop(
                    "default_clearance_tiers", [255]
                ),
                "default_minimum_rigidity_tier": metadata.pop(
                    "default_minimum_rigidity_tier", 255
                ),
                "provided_epistemic_security": metadata.pop(
                    "provided_epistemic_security", "PUBLIC"
                ),
                "provided_vram_gb": metadata.pop("provided_vram_gb", 0),
                "supported_remote_decoding_protocols": metadata.pop(
                    "supported_remote_decoding_protocols", ["NONE"]
                ),
            }

            # Pass raw metadata through Pydantic schema for strict type-safety
            manifest = FederatedSecurityMacroManifest.model_validate(metadata)

            endpoint = manifest.target_endpoint_uri
            clearance = str(
                manifest.required_clearance.value
                if hasattr(manifest.required_clearance, "value")
                else manifest.required_clearance
            )

            if _ACTIONSPACE_URN_PATTERN.match(urn):
                pass  # Modern multi-authority actionspace URN
            else:
                match urn.split(":"):
                    case [
                        "urn",
                        "coreason",
                        "archetype_a"
                        | "archetype_b"
                        | "archetype_c"
                        | "archetype_d"
                        | "oracle"
                        | "state",
                        *_,
                    ]:
                        warnings.warn(
                            f"Legacy URN prefix detected: '{urn}'. "
                            "This format is deprecated. Use "
                            "'urn:{{authority}}:actionspace:{{category}}:{{name}}:v{{version}}'.",
                            DeprecationWarning,
                            stacklevel=2,
                        )
                    case _:
                        pass

            await self._update_urn(
                urn, endpoint, clearance, epistemic_status, content_hash
            )
            logger.debug(
                f"Registered capability metadata for {urn}: "
                f"rigidity={capability_metadata['default_minimum_rigidity_tier']}, "
                f"security={capability_metadata['provided_epistemic_security']}, "
                f"protocols={capability_metadata['supported_remote_decoding_protocols']}, "
                f"content_hash={content_hash or 'none'}"
            )
            count += 1

        logger.info(f"Hydrated {count} capabilities from {json_path.name}")

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
                    await self._update_urn(urn, endpoint, clearance, epistemic_status)

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
            A mapping of URN strings to physical network actionSpaceCId URIs.
        """
        agent_level = self.CLEARANCE_LEVELS.get(agent_clearance, 0)
        state = await self._get_state()

        masked_substrates: dict[str, str] = {}
        for urn, data in state.items():
            required_clearance = data.get("clearance", "RESTRICTED")
            required_level = self.CLEARANCE_LEVELS.get(required_clearance, 3)

            if agent_level >= required_level:
                masked_substrates[urn] = data["endpoint"]

        return masked_substrates

    async def resolve_urn(self, target_urn: str) -> str:
        """Strict physical lookup over the active substrates.

        Args:
            target_urn: The URN of the capability to resolve.

        Returns:
            The mapped physical endpoint URI.

        Raises:
            KeyError: if the target_urn is not in the registry.
        """
        state = await self._get_state()
        if target_urn not in state:
            raise KeyError(f"Geometrical topology fault: unregistered URN {target_urn}")

        return state[target_urn]["endpoint"]

    async def get_epistemic_status(self, target_urn: str) -> str:
        """Retrieve the SRB governance lifecycle status for a registered URN.

        Args:
            target_urn: The URN to query.

        Returns:
            The epistemic status string (DRAFT, SRB_APPROVED,
            CLIENT_APPROVED, or PUBLISHED).  Defaults to ``"DRAFT"``
            if the URN is not registered.
        """
        state = await self._get_state()
        entry = state.get(target_urn)
        if entry is None:
            return "DRAFT"
        return entry.get("epistemic_status", "DRAFT")

    @staticmethod
    def validate_archetype_urn(urn: str) -> None:
        """Zero-trust URN validation for newly forged action spaces.

        Validates the modern multi-authority actionspace taxonomy via the
        canonical regex pattern synchronized with ``ActionSpaceURNState``
        in ``coreason-manifest``.  Supports federated namespace authorities
        (e.g. ``coreason``, ``nlm``, ``ohdsi``).

        Retains legacy archetype/oracle/state prefixes under a deprecation
        warning to prevent immediate topology severance of older containers.
        """
        if _ACTIONSPACE_URN_PATTERN.match(urn):
            return  # Modern multi-authority actionspace URN — valid

        # Legacy prefix check for backward compatibility
        match urn.split(":"):
            case [
                "urn",
                "coreason",
                "archetype_a"
                | "archetype_b"
                | "archetype_c"
                | "archetype_d"
                | "oracle"
                | "state",
                *_,
            ]:
                warnings.warn(
                    f"Legacy URN prefix detected: '{urn}'. "
                    "This format is deprecated. Use "
                    "'urn:{{authority}}:actionspace:{{category}}:{{name}}:v{{version}}'.",
                    DeprecationWarning,
                    stacklevel=2,
                )
            case _:
                raise ValueError(
                    f"URN Topology Breach: '{urn}' does not conform to the "
                    f"modern actionspace taxonomy or legacy bounds. "
                    "Rejecting hallucinated capability."
                )

    async def scan_action_space_modules(
        self, scan_dirs: list[Path] | None = None
    ) -> int:
        """Passively discover assets bearing ``__action_space_urn__`` via AST parsing.

        Uses Python's ``ast`` module to parse source files into Abstract Syntax
        Trees — NO module-level code is ever executed (Zero-Trust Passive
        Projection).  Extracts ``__action_space_urn__`` string assignments and
        validates them against the canonical actionspace URN regex.

        Args:
            scan_dirs: Directories to scan for ``.py`` files.  Defaults to
                ``['./action_spaces/']`` relative to the current working
                directory.

        Returns:
            Number of newly discovered action spaces registered in the cache.
        """
        if scan_dirs is None:
            scan_dirs = [Path.cwd() / "action_spaces"]

        state = await self._get_state()
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
                                if urn_value not in state:
                                    await self._update_urn(
                                        urn_value, urn_value, "RESTRICTED", "DRAFT"
                                    )
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
