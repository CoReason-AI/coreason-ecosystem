# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Tests for the Epistemic Filter — SRB Governance Lifecycle Guillotine."""

import pytest

from coreason_ecosystem.gateway.capability_registry import CapabilityRegistry
from coreason_ecosystem.gateway.epistemic_filter import (
    EPISTEMIC_LIFECYCLE_ORDER,
    EpistemicFilter,
)


@pytest.fixture
def populated_registry() -> CapabilityRegistry:
    """Construct a CapabilityRegistry pre-loaded with mixed epistemic statuses."""
    registry = CapabilityRegistry()

    # Directly inject cache entries to avoid needing a YAML file.
    registry._cache = {
        "urn:coreason:oracle:medical_kg": {
            "endpoint": "http://neo4j-mcp:8000",
            "clearance": "PUBLIC",
            "epistemic_status": "PUBLISHED",
        },
        "urn:coreason:oracle:clinical_vector": {
            "endpoint": "http://milvus-mcp:8000",
            "clearance": "CONFIDENTIAL",
            "epistemic_status": "CLIENT_APPROVED",
        },
        "urn:coreason:oracle:experimental_prover": {
            "endpoint": "http://lean4-mcp:8000",
            "clearance": "RESTRICTED",
            "epistemic_status": "SRB_APPROVED",
        },
        "urn:coreason:oracle:staging_tool": {
            "endpoint": "http://staging-mcp:8000",
            "clearance": "PUBLIC",
            "epistemic_status": "DRAFT",
        },
    }
    return registry


@pytest.fixture
def epistemic_filter(populated_registry: CapabilityRegistry) -> EpistemicFilter:
    """Construct an EpistemicFilter backed by the populated registry."""
    return EpistemicFilter(populated_registry)


def _all_urns(registry: CapabilityRegistry) -> dict[str, str]:
    """Shortcut to resolve all URNs → endpoints."""
    return {urn: data["endpoint"] for urn, data in registry._cache.items()}


class TestEpistemicFilterDRAFT:
    """DRAFT is the floor — no filtering should occur."""

    def test_draft_returns_all(
        self,
        epistemic_filter: EpistemicFilter,
        populated_registry: CapabilityRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = epistemic_filter.filter_capabilities(available, "DRAFT")
        assert result == available

    def test_draft_default_returns_all(
        self,
        epistemic_filter: EpistemicFilter,
        populated_registry: CapabilityRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = epistemic_filter.filter_capabilities(available)
        assert result == available


class TestEpistemicFilterSRBApproved:
    """SRB_APPROVED should strip DRAFT entries."""

    def test_strips_draft(
        self,
        epistemic_filter: EpistemicFilter,
        populated_registry: CapabilityRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = epistemic_filter.filter_capabilities(available, "SRB_APPROVED")
        assert "urn:coreason:oracle:staging_tool" not in result
        assert len(result) == 3


class TestEpistemicFilterClientApproved:
    """CLIENT_APPROVED should strip DRAFT and SRB_APPROVED entries."""

    def test_strips_draft_and_srb(
        self,
        epistemic_filter: EpistemicFilter,
        populated_registry: CapabilityRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = epistemic_filter.filter_capabilities(available, "CLIENT_APPROVED")
        assert "urn:coreason:oracle:staging_tool" not in result
        assert "urn:coreason:oracle:experimental_prover" not in result
        assert "urn:coreason:oracle:medical_kg" in result
        assert "urn:coreason:oracle:clinical_vector" in result
        assert len(result) == 2


class TestEpistemicFilterPublished:
    """PUBLISHED should strip everything except PUBLISHED entries."""

    def test_only_published(
        self,
        epistemic_filter: EpistemicFilter,
        populated_registry: CapabilityRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = epistemic_filter.filter_capabilities(available, "PUBLISHED")
        assert result == {"urn:coreason:oracle:medical_kg": "http://neo4j-mcp:8000"}


class TestEpistemicFilterEmptyRegistry:
    """An empty registry should always return empty."""

    def test_empty_returns_empty(self) -> None:
        registry = CapabilityRegistry()
        ef = EpistemicFilter(registry)
        result = ef.filter_capabilities({}, "PUBLISHED")
        assert result == {}


class TestEpistemicLifecycleOrder:
    """Verify the lifecycle ordering constants are monotonically increasing."""

    def test_ordering(self) -> None:
        assert (
            EPISTEMIC_LIFECYCLE_ORDER["DRAFT"]
            < EPISTEMIC_LIFECYCLE_ORDER["SRB_APPROVED"]
        )
        assert (
            EPISTEMIC_LIFECYCLE_ORDER["SRB_APPROVED"]
            < EPISTEMIC_LIFECYCLE_ORDER["CLIENT_APPROVED"]
        )
        assert (
            EPISTEMIC_LIFECYCLE_ORDER["CLIENT_APPROVED"]
            < EPISTEMIC_LIFECYCLE_ORDER["PUBLISHED"]
        )


class TestCapabilityRegistryEpistemicStatus:
    """Verify get_epistemic_status on the CapabilityRegistry."""

    def test_known_urn(self, populated_registry: CapabilityRegistry) -> None:
        assert (
            populated_registry.get_epistemic_status("urn:coreason:oracle:medical_kg")
            == "PUBLISHED"
        )

    def test_unknown_urn_defaults_draft(
        self, populated_registry: CapabilityRegistry
    ) -> None:
        assert (
            populated_registry.get_epistemic_status("urn:coreason:oracle:nonexistent")
            == "DRAFT"
        )


class TestSLABasedFiltering:
    """FederatedBilateralSLA classification ceiling enforcement."""

    def test_sla_strips_restricted_urns(
        self,
        epistemic_filter: EpistemicFilter,
        populated_registry: CapabilityRegistry,
    ) -> None:
        """SLA with 'public' ceiling strips CONFIDENTIAL and RESTRICTED URNs."""
        from coreason_manifest.spec.ontology import (
            FederatedBilateralSLA,
            SemanticClassificationProfile,
        )

        sla = FederatedBilateralSLA(
            receiving_tenant_id="tenant-001",
            max_permitted_classification=SemanticClassificationProfile.PUBLIC,
            liability_limit_magnitude=100,
        )
        available = _all_urns(populated_registry)
        result = epistemic_filter.filter_capabilities(
            available, "DRAFT", federation_sla=sla
        )
        # Only PUBLIC clearance URNs should pass
        assert "urn:coreason:oracle:medical_kg" in result
        assert "urn:coreason:oracle:staging_tool" in result
        # CONFIDENTIAL and RESTRICTED are stripped
        assert "urn:coreason:oracle:clinical_vector" not in result
        assert "urn:coreason:oracle:experimental_prover" not in result

    def test_sla_confidential_allows_public_and_confidential(
        self,
        epistemic_filter: EpistemicFilter,
        populated_registry: CapabilityRegistry,
    ) -> None:
        """SLA with 'confidential' ceiling allows PUBLIC + CONFIDENTIAL."""
        from coreason_manifest.spec.ontology import (
            FederatedBilateralSLA,
            SemanticClassificationProfile,
        )

        sla = FederatedBilateralSLA(
            receiving_tenant_id="tenant-002",
            max_permitted_classification=SemanticClassificationProfile.CONFIDENTIAL,
            liability_limit_magnitude=100,
        )
        available = _all_urns(populated_registry)
        result = epistemic_filter.filter_capabilities(
            available, "DRAFT", federation_sla=sla
        )
        assert "urn:coreason:oracle:medical_kg" in result
        assert "urn:coreason:oracle:clinical_vector" in result
        assert "urn:coreason:oracle:staging_tool" in result
        assert "urn:coreason:oracle:experimental_prover" not in result

    def test_no_sla_returns_all_at_draft(
        self,
        epistemic_filter: EpistemicFilter,
        populated_registry: CapabilityRegistry,
    ) -> None:
        """Without SLA, DRAFT returns everything (existing behavior preserved)."""
        available = _all_urns(populated_registry)
        result = epistemic_filter.filter_capabilities(available, "DRAFT")
        assert result == available
