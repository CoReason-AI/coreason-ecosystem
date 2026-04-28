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
        self: Any, urn: str, endpoint: str, clearance: str, epistemic_status: str
    ) -> None:
        if not hasattr(self, "_mock_state"):
            self._mock_state = {}
        self._mock_state[urn] = {
            "endpoint": endpoint,
            "clearance": clearance,
            "epistemic_status": epistemic_status,
        }

    async def mock_get_state(self: Any) -> dict[str, dict[str, str]]:
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
            "urn:coreason:archetype_b:tools:probe"
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
            '__action_space_urn__ = "urn:coreason:archetype_b:tools:probe"\n',
            encoding="utf-8",
        )

        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 1
        assert "urn:coreason:archetype_b:tools:probe" in registry._mock_state  # type: ignore[attr-defined]

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
            '__action_space_urn__ = "urn:coreason:archetype_b:tools:duplicate"\n',
            encoding="utf-8",
        )

        registry = SovereignMCPRegistry()
        registry._mock_state["urn:coreason:archetype_b:tools:duplicate"] = {  # type: ignore[attr-defined]
            "endpoint": "http://existing:8000",
            "clearance": "PUBLIC",
            "epistemic_status": "PUBLISHED",
        }
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 0
        # Original cache entry preserved
        assert (
            registry._mock_state["urn:coreason:archetype_b:tools:duplicate"]["endpoint"]  # type: ignore[attr-defined]
            == "http://existing:8000"
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
            '__action_space_urn__ = "urn:coreason:archetype_b:tools:test"\n',
            encoding="utf-8",
        )

        registry = SovereignMCPRegistry()
        count = await registry.scan_action_space_modules([scan_dir])
        assert count == 1
        assert "urn:coreason:archetype_b:tools:test" in registry._mock_state  # type: ignore[attr-defined]


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
                    "urn": "urn:coreason:archetype_b:tools:clean",
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
