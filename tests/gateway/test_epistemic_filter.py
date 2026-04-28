
import pytest

@pytest.fixture(autouse=True)
def mock_registry_temporal(monkeypatch):
    from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry
    async def mock_update_urn(self, urn, endpoint, clearance, epistemic_status):
        if not hasattr(self, "_mock_state"):
            self._mock_state = {}
        self._mock_state[urn] = {
            "endpoint": endpoint,
            "clearance": clearance,
            "epistemic_status": epistemic_status,
        }

    async def mock_get_state(self):
        if not hasattr(self, "_mock_state"):
            self._mock_state = {}
        return self._mock_state

    monkeypatch.setattr(SovereignMCPRegistry, "_update_urn", mock_update_urn)
    monkeypatch.setattr(SovereignMCPRegistry, "_get_state", mock_get_state)
    
    original_init = SovereignMCPRegistry.__init__
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._mock_state = {}
    monkeypatch.setattr(SovereignMCPRegistry, "__init__", new_init)

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

from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry
from coreason_ecosystem.gateway.epistemic_filter import (
    EPISTEMIC_LIFECYCLE_ORDER,
    EpistemicTransmuter,
)
from coreason_manifest.spec.ontology import (
    FederatedBilateralSLA,
    SemanticClassificationProfile,
)


@pytest.fixture
def populated_registry() -> SovereignMCPRegistry:
    """Construct a SovereignMCPRegistry pre-loaded with mixed epistemic statuses."""
    registry = SovereignMCPRegistry()

    # Directly inject cache entries to avoid needing a YAML file.
    registry._mock_state = {
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
def epistemic_filter(populated_registry: SovereignMCPRegistry) -> EpistemicTransmuter:
    """Construct an EpistemicTransmuter backed by the populated registry."""
    return EpistemicTransmuter(populated_registry)


def _all_urns(registry: SovereignMCPRegistry) -> dict[str, str]:
    """Shortcut to resolve all URNs → endpoints."""
    return {urn: data["endpoint"] for urn, data in registry._mock_state.items()}


class TestEpistemicTransmuterDRAFT:
    """DRAFT is the floor — no filtering should occur."""

    @pytest.mark.asyncio
    async def test_draft_returns_all(
        self,
        epistemic_filter: EpistemicTransmuter,
        populated_registry: SovereignMCPRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = await epistemic_filter.project_capabilities(available, "DRAFT")
        assert result == available

    @pytest.mark.asyncio
    async def test_draft_default_returns_all(
        self,
        epistemic_filter: EpistemicTransmuter,
        populated_registry: SovereignMCPRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = await epistemic_filter.project_capabilities(available)
        assert result == available


class TestEpistemicTransmuterSRBApproved:
    """SRB_APPROVED should strip DRAFT entries."""

    @pytest.mark.asyncio
    async def test_strips_draft(
        self,
        epistemic_filter: EpistemicTransmuter,
        populated_registry: SovereignMCPRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = await epistemic_filter.project_capabilities(available, "SRB_APPROVED")
        assert "urn:coreason:oracle:staging_tool" not in result
        assert len(result) == 3


class TestEpistemicTransmuterClientApproved:
    """CLIENT_APPROVED should strip DRAFT and SRB_APPROVED entries."""

    @pytest.mark.asyncio
    async def test_strips_draft_and_srb(
        self,
        epistemic_filter: EpistemicTransmuter,
        populated_registry: SovereignMCPRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = await epistemic_filter.project_capabilities(available, "CLIENT_APPROVED")
        assert "urn:coreason:oracle:staging_tool" not in result
        assert "urn:coreason:oracle:experimental_prover" not in result
        assert "urn:coreason:oracle:medical_kg" in result
        assert "urn:coreason:oracle:clinical_vector" in result
        assert len(result) == 2


class TestEpistemicTransmuterPublished:
    """PUBLISHED should strip everything except PUBLISHED entries."""

    @pytest.mark.asyncio
    async def test_only_published(
        self,
        epistemic_filter: EpistemicTransmuter,
        populated_registry: SovereignMCPRegistry,
    ) -> None:
        available = _all_urns(populated_registry)
        result = await epistemic_filter.project_capabilities(available, "PUBLISHED")
        assert result == {"urn:coreason:oracle:medical_kg": "http://neo4j-mcp:8000"}


class TestEpistemicTransmuterEmptyRegistry:
    """An empty registry should always return empty."""

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self) -> None:
        registry = SovereignMCPRegistry()
        ef = EpistemicTransmuter(registry)
        result = await ef.project_capabilities({}, "PUBLISHED")
        assert result == {}


class TestEpistemicLifecycleOrder:
    """Verify the lifecycle ordering constants are monotonically increasing."""

    @pytest.mark.asyncio
    async def test_ordering(self) -> None:
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


class TestSovereignMCPRegistryEpistemicStatus:
    """Verify get_epistemic_status on the SovereignMCPRegistry."""

    @pytest.mark.asyncio
    async def test_known_urn(self, populated_registry: SovereignMCPRegistry) -> None:
        assert (
            await populated_registry.get_epistemic_status("urn:coreason:oracle:medical_kg")
            == "PUBLISHED"
        )

    @pytest.mark.asyncio
    async def test_unknown_urn_defaults_draft(
        self, populated_registry: SovereignMCPRegistry
    ) -> None:
        assert (
            await populated_registry.get_epistemic_status("urn:coreason:oracle:nonexistent")
            == "DRAFT"
        )


class TestSLABasedFiltering:
    """FederatedBilateralSLA classification ceiling enforcement."""

    @pytest.mark.asyncio
    async def test_sla_strips_restricted_urns(
        self,
        epistemic_filter: EpistemicTransmuter,
        populated_registry: SovereignMCPRegistry,
    ) -> None:
        """SLA with 'public' ceiling strips CONFIDENTIAL and RESTRICTED URNs."""
        sla = FederatedBilateralSLA(
            receiving_tenant_cid="tenant-001",
            max_permitted_classification=SemanticClassificationProfile.PUBLIC,
            liability_limit_magnitude=100,
        )
        available = _all_urns(populated_registry)
        result = await epistemic_filter.project_capabilities(
            available, "DRAFT", federation_sla=sla
        )
        # Only PUBLIC clearance URNs should pass
        assert "urn:coreason:oracle:medical_kg" in result
        assert "urn:coreason:oracle:staging_tool" in result
        # CONFIDENTIAL and RESTRICTED are stripped
        assert "urn:coreason:oracle:clinical_vector" not in result
        assert "urn:coreason:oracle:experimental_prover" not in result

    @pytest.mark.asyncio
    async def test_sla_confidential_allows_public_and_confidential(
        self,
        epistemic_filter: EpistemicTransmuter,
        populated_registry: SovereignMCPRegistry,
    ) -> None:
        """SLA with 'confidential' ceiling allows PUBLIC + CONFIDENTIAL."""
        sla = FederatedBilateralSLA(
            receiving_tenant_cid="tenant-002",
            max_permitted_classification=SemanticClassificationProfile.CONFIDENTIAL,
            liability_limit_magnitude=100,
        )
        available = _all_urns(populated_registry)
        result = await epistemic_filter.project_capabilities(
            available, "DRAFT", federation_sla=sla
        )
        assert "urn:coreason:oracle:medical_kg" in result
        assert "urn:coreason:oracle:clinical_vector" in result
        assert "urn:coreason:oracle:staging_tool" in result
        assert "urn:coreason:oracle:experimental_prover" not in result

    @pytest.mark.asyncio
    async def test_no_sla_returns_all_at_draft(
        self,
        epistemic_filter: EpistemicTransmuter,
        populated_registry: SovereignMCPRegistry,
    ) -> None:
        """Without SLA, DRAFT returns everything (existing behavior preserved)."""
        available = _all_urns(populated_registry)
        result = await epistemic_filter.project_capabilities(available, "DRAFT")
        assert result == available
