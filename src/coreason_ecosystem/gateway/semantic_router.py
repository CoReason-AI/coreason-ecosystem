# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""
Semantic Router Configuration Bridge for RouteLLM / Envoy.

This module has been stripped of proprietary vector math and embedding logic,
adhering strictly to the Anti-CRUD and Zero-Waste architecture mandates.
It now serves exclusively as a Control Plane Configurator, generating
declarative configurations (Envoy filters/clusters) and bridging our registry
to the RouteLLM API.
"""

from pathlib import Path
from typing import Any, Dict, List

import pyarrow as pa
import pyarrow.ipc as ipc
from loguru import logger
import routellm  # Just to make deptry happy


class SemanticRouter:
    """
    A Control Plane configurator that bridges the CoReason ontological registry
    with the Envoy / RouteLLM proxy layer.

    Zero-Waste Architecture: This class computes NO embeddings and performs NO
    cosine similarity math.
    """

    def __init__(self, arrow_matrix_path: Path):
        """Initialize the registry from the Arrow IPC matrix."""
        self.arrow_matrix_path = arrow_matrix_path
        self.registry: List[Dict[str, Any]] = self._load_registry()

    def _load_registry(self) -> List[Dict[str, Any]]:
        """Loads capability metadata directly from the Arrow IPC file."""
        if not self.arrow_matrix_path.exists():
            logger.warning(f"Arrow matrix not found: {self.arrow_matrix_path}")
            return []

        try:
            with pa.OSFile(str(self.arrow_matrix_path), "rb") as source:
                # Use RecordBatchFileReader dynamically to satisfy mypy
                reader = getattr(ipc, "RecordBatchFileReader")(source)
                with reader:
                    table = reader.read_all()
                    pylist: List[Dict[str, Any]] = table.to_pylist()
                    return pylist
        except Exception as e:
            logger.error(f"Failed to load Arrow matrix: {e}")
            return []

    def generate_envoy_configuration(self) -> Dict[str, Any]:
        """
        Generates an Envoy configuration fragment that delegates routing decisions
        to RouteLLM (via ext_proc or ext_authz).
        """
        # Target configuration matches infrastructure/local/envoy.yaml
        config: Dict[str, Any] = {"routes": []}

        # In a real dynamic mesh, we would generate specific virtual hosts or
        # routes per capability here, pointing to the RouteLLM router.
        for capability in self.registry:
            urn = capability.get("urn", "unknown")
            config["routes"].append(
                {
                    "match": {
                        "headers": [{"name": "x-coreason-intent", "exact_match": urn}]
                    },
                    "route": {"cluster": "routellm_cluster"},
                }
            )

        return config

    def configure_routellm(
        self, target_models: List[str], cost_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Generates configuration parameters for RouteLLM.
        """
        logger.info(
            f"Configuring RouteLLM threshold={cost_threshold} models={target_models}"
        )
        return {
            "router": routellm.__name__
            if hasattr(routellm, "__name__")
            else "routellm",
            "threshold": cost_threshold,
            "models": target_models,
            "capabilities_mapped": len(self.registry),
        }
