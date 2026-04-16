# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Epistemic Filter — SRB Governance Lifecycle Guillotine.

Intercepts ``FederatedDiscoveryIntent`` from the Runtime and physically strips
URNs from the capability matrix that do not meet the requested
``minimum_epistemic_status`` before the schema is projected to the LLM.

SRB Governance Lifecycle ordering (ascending):
  DRAFT → SRB_APPROVED → CLIENT_APPROVED → PUBLISHED

This enforces LAW 2 (Stateless Variable Projection) by ensuring that
unapproved capabilities are never projected to the kinetic plane.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from coreason_ecosystem.gateway.capability_registry import CapabilityRegistry

# SRB Governance Lifecycle — strictly ordered by epistemic maturity.
EPISTEMIC_LIFECYCLE_ORDER: dict[str, int] = {
    "DRAFT": 0,
    "SRB_APPROVED": 1,
    "CLIENT_APPROVED": 2,
    "PUBLISHED": 3,
}


class EpistemicFilter:
    """Middleware guillotine enforcing SRB governance lifecycle constraints.

    Given a ``minimum_epistemic_status`` (e.g., ``"CLIENT_APPROVED"``),
    this filter strips any URNs from the capability registry whose
    ``epistemic_status`` does not meet or exceed that threshold.
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def filter_capabilities(
        self,
        available_urns: dict[str, str],
        minimum_epistemic_status: str = "DRAFT",
    ) -> dict[str, str]:
        """Apply the Epistemic Guillotine to the discovered capability set.

        Args:
            available_urns: Mapping of URN → endpoint from the registry.
            minimum_epistemic_status: The minimum SRB lifecycle phase
                required for projection.  Defaults to ``"DRAFT"`` (no
                filtering).

        Returns:
            A filtered mapping containing only URNs whose epistemic
            status meets or exceeds the requested minimum.
        """
        min_level = EPISTEMIC_LIFECYCLE_ORDER.get(minimum_epistemic_status, 0)

        if min_level == 0:
            # DRAFT is the floor — no filtering required.
            return available_urns

        filtered: dict[str, str] = {}
        for urn, endpoint in available_urns.items():
            urn_status = self._registry.get_epistemic_status(urn)
            urn_level = EPISTEMIC_LIFECYCLE_ORDER.get(urn_status, 0)

            if urn_level >= min_level:
                filtered[urn] = endpoint
            else:
                logger.debug(
                    f"Epistemic Guillotine: stripping {urn} "
                    f"(status={urn_status}, required≥{minimum_epistemic_status})"
                )

        logger.info(
            f"Epistemic Filter: {len(filtered)}/{len(available_urns)} URNs "
            f"passed at minimum status '{minimum_epistemic_status}'."
        )
        return filtered
