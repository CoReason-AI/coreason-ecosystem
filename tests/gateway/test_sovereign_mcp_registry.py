# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Tests for Passive Ontological Projection, URN validation, and deprecation warnings."""

import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml

from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry


@pytest.fixture(autouse=True)
def mock_registry_temporal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_update_urn(
        self: Any,
        urn: str,
        clearance: str,
        epistemic_status: str,
        capability_metadata: dict[str, Any] | None = None,
    ) -> None:
        if not hasattr(self, "_mock_state"):
            self._mock_state = {}
        self._mock_state[urn] = {
            "clearance": clearance,
            "epistemic_status": epistemic_status,
            "capability_metadata": capability_metadata or {},
        }

    async def mock_get_state(self: Any) -> dict[str, dict[str, Any]]:
        if not hasattr(self, "_mock_state"):
            self._mock_state = {}
        return self._mock_state  # type: ignore[no-any-return]

    monkeypatch.setattr(SovereignMCPRegistry, "_update_urn", mock_update_urn)
    monkeypatch.setattr(SovereignMCPRegistry, "_get_state", mock_get_state)

    # Initialize _mock_state for tests that instantiate directly
    original_init = SovereignMCPRegistry.__init__

    def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self._mock_state = {}

    monkeypatch.setattr(SovereignMCPRegistry, "__init__", new_init)


class TestValidateActionspaceURN:
    """Zero-trust URN prefix validation guard."""

    @pytest.mark.asyncio
    async def test_valid_urn_passes(self) -> None:
        SovereignMCPRegistry.validate_archetype_urn(
            "urn:coreason:actionspace:solver:clinical_extractor:v1"
        )

    @pytest.mark.asyncio
    async def test_valid_federated_urn_passes(self) -> None:
        """Federated namespace authorities (e.g. nlm, ohdsi) must be accepted."""
        SovereignMCPRegistry.validate_archetype_urn(
            "urn:nlm:actionspace:oracle:mesh_lookup:v3"
        )

    @pytest.mark.asyncio
    async def test_invalid_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="URN Topology Breach"):
            SovereignMCPRegistry.validate_archetype_urn(
                "urn:coreason:invalid:clinical_extractor"
            )

    @pytest.mark.asyncio
    async def test_empty_urn_raises(self) -> None:
        with pytest.raises(ValueError, match="URN Topology Breach"):
            SovereignMCPRegistry.validate_archetype_urn("")

    @pytest.mark.asyncio
    async def test_hallucinated_urn_raises(self) -> None:
        with pytest.raises(ValueError, match="URN Topology Breach"):
            SovereignMCPRegistry.validate_archetype_urn(
                "urn:hallucinated:fake:capability"
            )


class TestScanActionSpaceModules:
    """AST-based Passive Ontological Projection scanner."""

    @pytest.mark.asyncio
    async def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty scan dir returns 0 discovered."""
        scan_dir = tmp_path / "action_spaces"
        scan_dir.mkdir()
        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 0
        assert len(registry._mock_state) == 0  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Non-existent scan dir is silently skipped."""
        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([tmp_path / "does_not_exist"])
        assert count == 0

    @pytest.mark.asyncio
    async def test_discovers_valid_urn(self, tmp_path: Path) -> None:
        """Scanner discovers a .py file with valid __action_space_urn__."""
        scan_dir = tmp_path / "action_spaces"
        scan_dir.mkdir()
        module_file = scan_dir / "test_actuator.py"
        module_file.write_text(
            '__action_space_urn__ = "urn:coreason:actionspace:oracle:probe:v1"\n',
            encoding="utf-8",
        )

        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 1
        assert "urn:coreason:actionspace:oracle:probe:v1" in registry._mock_state  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_rejects_invalid_prefix(self, tmp_path: Path) -> None:
        """Scanner rejects files with non-actionspace URN prefixes."""
        scan_dir = tmp_path / "action_spaces"
        scan_dir.mkdir()
        module_file = scan_dir / "bad_actuator.py"
        module_file.write_text(
            '__action_space_urn__ = "urn:coreason:invalid:bad"\n',
            encoding="utf-8",
        )

        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 0
        assert len(registry._mock_state) == 0  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_skips_syntax_error_files(self, tmp_path: Path) -> None:
        """Scanner gracefully skips files with syntax errors."""
        scan_dir = tmp_path / "action_spaces"
        scan_dir.mkdir()
        bad_file = scan_dir / "broken.py"
        bad_file.write_text("def broken(\n", encoding="utf-8")

        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_registration(self, tmp_path: Path) -> None:
        """Scanner does not re-register already cached URNs."""
        scan_dir = tmp_path / "action_spaces"
        scan_dir.mkdir()
        module_file = scan_dir / "actuator.py"
        module_file.write_text(
            '__action_space_urn__ = "urn:coreason:actionspace:solver:duplicate:v1"\n',
            encoding="utf-8",
        )

        registry = SovereignMCPRegistry()
        registry._mock_state["urn:coreason:actionspace:solver:duplicate:v1"] = {  # type: ignore[attr-defined]
            "clearance": "PUBLIC",
            "epistemic_status": "PUBLISHED",
        }
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 0
        # Original cache entry preserved
        assert (
            registry._mock_state["urn:coreason:actionspace:solver:duplicate:v1"][  # type: ignore[attr-defined]
                "clearance"
            ]
            == "PUBLIC"
        )

    @pytest.mark.asyncio
    async def test_skips_non_string_assignments(self, tmp_path: Path) -> None:
        """Scanner ignores __action_space_urn__ with non-string values."""
        scan_dir = tmp_path / "action_spaces"
        scan_dir.mkdir()
        module_file = scan_dir / "numeric_urn.py"
        module_file.write_text("__action_space_urn__ = 12345\n", encoding="utf-8")

        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 0

    @pytest.mark.asyncio
    async def test_recursive_scan(self, tmp_path: Path) -> None:
        """Scanner discovers URNs in nested subdirectories."""
        scan_dir = tmp_path / "action_spaces"
        nested = scan_dir / "subdir" / "deep"
        nested.mkdir(parents=True)
        module_file = nested / "deep_actuator.py"
        module_file.write_text(
            '__action_space_urn__ = "urn:coreason:actionspace:oracle:test:v1"\n',
            encoding="utf-8",
        )

        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 1
        assert "urn:coreason:actionspace:oracle:test:v1" in registry._mock_state  # type: ignore[attr-defined]


class TestLegacyURNDeprecationWarnings:
    """Legacy URN prefixes emit DeprecationWarning."""

    @pytest.mark.asyncio
    async def test_hydrate_from_matrix_warns_on_legacy_oracle(
        self, tmp_path: Path
    ) -> None:
        matrix_file = tmp_path / "capabilities.matrix.yaml"
        matrix_data = {
            "capabilities": [
                {
                    "urn": "urn:coreason:oracle:legacy_test",
                    "endpoint": "http://legacy:8000",
                    "clearance": "PUBLIC",
                }
            ]
        }
        matrix_file.write_text(yaml.dump(matrix_data), encoding="utf-8")

        registry = SovereignMCPRegistry()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await registry.hydrate_from_matrix(matrix_file)
            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) == 1
            assert "Legacy URN prefix detected" in str(deprecation_warnings[0].message)

    @pytest.mark.asyncio
    async def test_hydrate_from_matrix_warns_on_legacy_state(
        self, tmp_path: Path
    ) -> None:
        matrix_file = tmp_path / "capabilities.matrix.yaml"
        matrix_data = {
            "capabilities": [
                {
                    "urn": "urn:coreason:state:treasury",
                    "endpoint": "http://treasury:8000",
                    "clearance": "RESTRICTED",
                }
            ]
        }
        matrix_file.write_text(yaml.dump(matrix_data), encoding="utf-8")

        registry = SovereignMCPRegistry()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await registry.hydrate_from_matrix(matrix_file)
            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) == 1

    @pytest.mark.asyncio
    async def test_no_warning_for_actionspace_urn(self, tmp_path: Path) -> None:
        matrix_file = tmp_path / "capabilities.matrix.yaml"
        matrix_data = {
            "capabilities": [
                {
                    "urn": "urn:coreason:actionspace:solver:clean:v1",
                    "endpoint": "http://clean:8000",
                    "clearance": "PUBLIC",
                }
            ]
        }
        matrix_file.write_text(yaml.dump(matrix_data), encoding="utf-8")

        registry = SovereignMCPRegistry()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await registry.hydrate_from_matrix(matrix_file)
            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) == 0

    @pytest.mark.asyncio
    async def test_hydrate_from_matrix_with_callback_url(self, tmp_path: Path) -> None:
        matrix_file = tmp_path / "capabilities.matrix.yaml"
        matrix_data = {
            "capabilities": [
                {
                    "urn": "urn:coreason:actionspace:solver:clean:v1",
                    "endpoint": "http://clean:8000",
                    "clearance": "PUBLIC",
                    "callback_url": "http://svix-broker.internal/api/v1/webhook",
                }
            ]
        }
        matrix_file.write_text(yaml.dump(matrix_data), encoding="utf-8")

        registry = SovereignMCPRegistry()
        await registry.hydrate_from_matrix(matrix_file)
        state = await registry._get_state()
        entry = state.get("urn:coreason:actionspace:solver:clean:v1")
        assert entry is not None
        assert (
            entry.get("capability_metadata", {}).get("callback_url")
            == "http://svix-broker.internal/api/v1/webhook"
        )


# ---------------------------------------------------------------------------
# Helpers for Substrate Resolution tests
# ---------------------------------------------------------------------------


def _make_rigidity_policy(
    rigidity: int = 0,
    vram: int | None = None,
    security: str = "PUBLIC",
    protocols: list[str] | None = None,
) -> Any:
    """Lightweight stub mimicking EpistemicRigidityPolicy attributes."""

    class _Stub:
        pass

    stub = _Stub()
    stub.minimum_rigidity_tier = rigidity  # type: ignore[attr-defined]
    stub.minimum_vram_gb = vram  # type: ignore[attr-defined]
    stub.required_epistemic_security = security  # type: ignore[attr-defined]
    stub.permitted_remote_decoding_protocols = protocols or ["NONE"]  # type: ignore[attr-defined]
    return stub


def _make_frontier_policy(preference: str = "balanced") -> Any:
    """Lightweight stub mimicking RoutingFrontierPolicy attributes."""

    class _Stub:
        pass

    stub = _Stub()
    stub.tradeoff_preference = preference  # type: ignore[attr-defined]
    return stub


def _seed_substrate(
    registry: Any,
    urn: str,
    rigidity: int = 128,
    vram: int = 24,
    security: str = "CONFIDENTIAL",
    protocols: list[str] | None = None,
) -> None:
    """Inject a substrate entry directly into the mock state."""
    registry._mock_state[urn] = {
        "clearance": security,
        "epistemic_status": "PUBLISHED",
        "capability_metadata": {
            "default_minimum_rigidity_tier": rigidity,
            "provided_vram_gb": vram,
            "provided_epistemic_security": security,
            "supported_remote_decoding_protocols": protocols or ["NONE"],
        },
    }


class TestGetCapabilityMetadata:
    """Tests for the get_capability_metadata query."""

    @pytest.mark.asyncio
    async def test_existing_urn_returns_metadata(self) -> None:
        registry = SovereignMCPRegistry()
        _seed_substrate(
            registry, "urn:coreason:actionspace:substrate:gpu_a:v1", vram=80
        )
        meta = await registry.get_capability_metadata(
            "urn:coreason:actionspace:substrate:gpu_a:v1"
        )
        assert meta["provided_vram_gb"] == 80

    @pytest.mark.asyncio
    async def test_missing_urn_returns_empty(self) -> None:
        registry = SovereignMCPRegistry()
        meta = await registry.get_capability_metadata(
            "urn:coreason:actionspace:substrate:missing:v1"
        )
        assert meta == {}


class TestResolveOptimalSubstrate:
    """Tests for delegated Substrate resolution."""

    @pytest.mark.asyncio
    async def test_delegates_to_first_candidate(self) -> None:
        registry = SovereignMCPRegistry()
        _seed_substrate(
            registry,
            "urn:coreason:actionspace:substrate:alpha:v1",
            rigidity=100,
            vram=24,
        )
        result = await registry.resolve_optimal_substrate(
            ["urn:coreason:actionspace:substrate:alpha:v1"],
            _make_rigidity_policy(rigidity=50, vram=16),
        )
        assert result == "urn:coreason:actionspace:substrate:alpha:v1"

    @pytest.mark.asyncio
    async def test_no_candidates_raises(self) -> None:
        registry = SovereignMCPRegistry()
        with pytest.raises(KeyError, match="Substrate Resolution Fault"):
            await registry.resolve_optimal_substrate(
                [],
                _make_rigidity_policy(rigidity=200, vram=80),
            )
