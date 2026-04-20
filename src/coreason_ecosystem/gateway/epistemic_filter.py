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
    from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry

from coreason_manifest.spec.ontology import (
    FederatedBilateralSLA,
    SemanticClassificationProfile,
)

# SRB Governance Lifecycle — strictly ordered by epistemic maturity.
EPISTEMIC_LIFECYCLE_ORDER: dict[str, int] = {
    "DRAFT": 0,
    "SRB_APPROVED": 1,
    "CLIENT_APPROVED": 2,
    "PUBLISHED": 3,
}


class EpistemicTransmuter:
    """Middleware guillotine enforcing SRB governance lifecycle constraints.

    Given a ``minimum_epistemic_status`` (e.g., ``"CLIENT_APPROVED"``),
    this transmuter severs any URNs from the capability registry whose
    ``epistemic_status`` does not meet or exceed that threshold.
    """

    def __init__(self, registry: "SovereignMCPRegistry") -> None:
        self._registry = registry

    def sever_causal_edge(self, reason: str) -> None:
        """Actively sever the causal edge due to epistemic violation."""
        from fastapi import HTTPException
        logger.critical(f"Severing causal edge: {reason}")
        raise HTTPException(status_code=401, detail=f"Causal Edge Severed: {reason}")

    def transmute_canonical_payload(self, payload: dict[str, Any], reported_hash: str) -> None:
        """Verify the JSON payload matches its RFC 8785 canonical hash. 
        If a payload violates RFC 8785 canonical hashing, sever_causal_edge is invoked.
        """
        import json
        import hashlib
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        canonical_hash = hashlib.sha256(canonical).hexdigest()
        if canonical_hash != reported_hash:
            self.sever_causal_edge(f"RFC 8785 canonical hash mismatch. Expected {canonical_hash}, got {reported_hash}.")

    def project_capabilities(
        self,
        available_urns: dict[str, str],
        minimum_epistemic_status: str = "DRAFT",
        federation_sla: FederatedBilateralSLA | None = None,
    ) -> dict[str, str]:
        """Apply the Epistemic Guillotine to the discovered capability set.

        Args:
            available_urns: Mapping of URN → endpoint from the registry.
            minimum_epistemic_status: The minimum SRB lifecycle phase
                required for projection.  Defaults to ``"DRAFT"`` (no
                filtering).
            federation_sla: Optional ``FederatedBilateralSLA`` from the
                manifest.  When provided, URNs whose clearance exceeds
                the SLA's ``max_permitted_classification`` are stripped.

        Returns:
            A filtered mapping containing only URNs whose epistemic
            status meets or exceeds the requested minimum, and whose
            clearance satisfies any federation SLA constraints.
        """
        min_level = EPISTEMIC_LIFECYCLE_ORDER.get(minimum_epistemic_status, 0)

        if min_level == 0 and federation_sla is None:
            # DRAFT is the floor — no filtering required.
            return available_urns

        # Resolve the SLA classification ceiling if provided.
        _classification_levels: dict[str, int] = {
            "public": 0,
            "internal": 1,
            "confidential": 2,
            "restricted": 3,
        }
        sla_max_level: int | None = None
        if federation_sla is not None:
            sla_cls = federation_sla.max_permitted_classification
            sla_cls_value = (
                sla_cls.value
                if isinstance(sla_cls, SemanticClassificationProfile)
                else str(sla_cls)
            )
            sla_max_level = _classification_levels.get(sla_cls_value, 0)

        filtered: dict[str, str] = {}
        for urn, endpoint in available_urns.items():
            urn_status = self._registry.get_epistemic_status(urn)
            urn_level = EPISTEMIC_LIFECYCLE_ORDER.get(urn_status, 0)

            if urn_level >= min_level:
                # SLA classification quarantine: map LBAC clearance to classification.
                if sla_max_level is not None:
                    assert federation_sla is not None  # narrowing for mypy
                    urn_clearance = self._registry._cache.get(urn, {}).get(
                        "clearance", "RESTRICTED"
                    )
                    urn_cls_level = _classification_levels.get(urn_clearance.lower(), 3)
                    if urn_cls_level > sla_max_level:
                        logger.debug(
                            f"Federation SLA Guillotine: quarantining {urn} "
                            f"(clearance={urn_clearance}, "
                            f"SLA max={federation_sla.max_permitted_classification})"
                        )
                        continue
                filtered[urn] = endpoint
            else:
                logger.debug(
                    f"Epistemic Guillotine: quarantining {urn} "
                    f"(status={urn_status}, required≥{minimum_epistemic_status})"
                )

        logger.info(
            f"Epistemic Filter: {len(filtered)}/{len(available_urns)} URNs "
            f"passed at minimum status '{minimum_epistemic_status}'."
        )
        return filtered
