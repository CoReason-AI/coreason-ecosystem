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
Hollow Semantic Router for the Ecosystem Gateway.

AGENT INSTRUCTION: This module is a "Hollow Plane" projection. It does NOT compute
semantic embeddings or perform vector math locally. Instead, it delegates all
epistemic discovery tasks to the 'coreason-runtime' Kinetic Execution Plane via RPC.

CAUSAL AFFORDANCE: Provides a unified interface for the Gateway to resolve
intents into URN capabilities without bearing the thermodynamic cost of ML inference.

EPISTEMIC BOUNDS: Relies entirely on the availability and correctness of the
remote discovery endpoint. Returns an empty list if the runtime is unreachable.

MCP ROUTING TRIGGERS: Hollow Gateway, RPC Discovery, Semantic Proxy
"""

import os
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


class SemanticRouter:
    """Hollow semantic router that delegates to the Coreason Runtime.

    Replaces the legacy hybrid Aurelio/Multi-well router with a stateless
    RPC client, following the Tripartite Architecture mandate.
    """

    def __init__(self, runtime_url: Optional[str] = None):
        """Initialize the hollow router.

        Args:
            runtime_url: The base URL of the coreason-runtime API.
                         Defaults to COREASON_RUNTIME_URL env var or localhost:8000.
        """
        self.runtime_url = runtime_url or os.getenv("COREASON_RUNTIME_URL", "http://localhost:8000")
        self._client = httpx.AsyncClient(base_url=self.runtime_url, timeout=10.0)

    async def route_intent(
        self,
        query_text: str,
        limit: int = 5,
        tenant_cid: str = "889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531",
        **_kwargs: Any,
    ) -> List[str]:
        """Routes an intent by calling the remote runtime discovery API.

        AGENT INSTRUCTION: This is the primary entry point for intent matching.
        It preserves the legacy method signature where possible but simplifies
        the internals to a single RPC call.

        Args:
            query_text: The natural language intent to resolve.
            limit: Maximum number of ranked URNs to return.
            tenant_cid: Tenant identifier for security segregation.
            _kwargs: Consumed for backward compatibility with legacy router.

        Returns:
            List of URNs sorted by final score (highest first).
        """
        logger.debug(f"Delegating semantic discovery for intent: '{query_text}' to {self.runtime_url}")

        try:
            response = await self._client.post(
                "/api/v1/discovery/search",
                json={
                    "query": query_text,
                    "limit": limit,
                    "tenant_cid": tenant_cid,
                },
            )
            response.raise_for_status()
            results = response.json()

            # The runtime returns a list of dicts with 'name' (the URN), 'description', 'inputSchema', 'distance'
            urns = [r["name"] for r in results if "name" in r]
            logger.info(f"Resolved {len(urns)} capabilities via remote discovery.")
            return urns

        except Exception as e:
            logger.error(f"Remote semantic discovery failed: {e}")
            # Fallback to empty list to prevent gateway crash
            return []

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


# Note: Legacy configuration classes are kept as empty stubs or minimal
# implementations to prevent breaking imports in other modules, but they
# no longer influence the routing logic.

class IntentWeighting:
    """Legacy stub for IntentWeighting."""

    def __init__(self, **_kwargs: Any):
        pass


class ScoreCalibration:
    """Legacy stub for ScoreCalibration."""

    def __init__(self, **_kwargs: Any):
        pass


class HybridWeighting:
    """Legacy stub for HybridWeighting."""

    def __init__(self, **_kwargs: Any):
        pass
