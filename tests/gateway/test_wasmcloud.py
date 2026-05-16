# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

"""Tests for the wasmCloud integration layer.

Tests are organized into two tiers:

1. **Deterministic structural tests** — validate URN handling, payload
   construction, and volumetric guards using pure string/dict inputs.
   These always run (no external dependencies).

2. **NATS integration tests** — validate actual NATS connectivity,
   JetStream KV operations, and lattice communication. These require
   a running NATS server and are skipped if NATS is unreachable.

Per the Anti-Mocking directive: no unittest.mock, no MonkeyPatch for
core logic. Tests use real NATS servers or deterministic inputs.
"""

import pytest
from typing import AsyncGenerator

from coreason_ecosystem.wasmcloud.gateway_provider import (
    MAX_PAYLOAD_BYTES,
    NATSGatewayProvider,
    SUBJECT_TOOL_INVOKE,
)
from coreason_ecosystem.wasmcloud.nats_registry import (
    NATSCapabilityRegistry,
    _ACTIONSPACE_URN_PATTERN,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_nats_available() -> bool:
    """Check if a NATS server is reachable on localhost:4222."""
    import socket

    try:
        sock = socket.create_connection(("localhost", 4222), timeout=1)
        sock.close()
        return True
    except ConnectionRefusedError, OSError, TimeoutError:
        return False


requires_nats = pytest.mark.skipif(
    not _check_nats_available(),
    reason="NATS server not available on localhost:4222",
)


# ===========================================================================
# Tier 1: Deterministic Structural Tests (no NATS required)
# ===========================================================================


class TestURNValidation:
    """Zero-trust URN validation for the NATS registry."""

    def test_valid_coreason_urn(self) -> None:
        NATSCapabilityRegistry.validate_urn(
            "urn:coreason:actionspace:solver:clinical_extractor:v1"
        )

    def test_valid_federated_urn(self) -> None:
        """Federated namespace authorities (e.g. nlm, ohdsi) must be accepted."""
        NATSCapabilityRegistry.validate_urn("urn:nlm:actionspace:oracle:mesh_lookup:v3")

    def test_all_six_categories_valid(self) -> None:
        """All 6 universal asset categories must be accepted."""
        categories = ["oracle", "solver", "effector", "substrate", "sensory", "node"]
        for cat in categories:
            NATSCapabilityRegistry.validate_urn(
                f"urn:coreason:actionspace:{cat}:test_cap:v1"
            )

    def test_invalid_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="URN Topology Breach"):
            NATSCapabilityRegistry.validate_urn(
                "urn:coreason:invalid:clinical_extractor"
            )

    def test_empty_urn_raises(self) -> None:
        with pytest.raises(ValueError, match="URN Topology Breach"):
            NATSCapabilityRegistry.validate_urn("")

    def test_hallucinated_urn_raises(self) -> None:
        with pytest.raises(ValueError, match="URN Topology Breach"):
            NATSCapabilityRegistry.validate_urn("urn:hallucinated:fake:capability")

    def test_missing_version_raises(self) -> None:
        with pytest.raises(ValueError, match="URN Topology Breach"):
            NATSCapabilityRegistry.validate_urn(
                "urn:coreason:actionspace:solver:no_version"
            )

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValueError, match="URN Topology Breach"):
            NATSCapabilityRegistry.validate_urn(
                "urn:coreason:actionspace:widget:bad_cat:v1"
            )


class TestURNKeyConversion:
    """Verify the URN ↔ NATS KV key bijection."""

    def test_urn_to_key(self) -> None:
        key = NATSCapabilityRegistry._urn_to_key(
            "urn:coreason:actionspace:solver:test:v1"
        )
        assert ":" not in key
        assert key == "urn.coreason.actionspace.solver.test.v1"

    def test_key_to_urn(self) -> None:
        urn = NATSCapabilityRegistry._key_to_urn(
            "urn.coreason.actionspace.solver.test.v1"
        )
        assert urn == "urn:coreason:actionspace:solver:test:v1"

    def test_roundtrip_preserves_urn(self) -> None:
        original = "urn:coreason:actionspace:oracle:medical_kg:v1"
        key = NATSCapabilityRegistry._urn_to_key(original)
        restored = NATSCapabilityRegistry._key_to_urn(key)
        assert restored == original


class TestURNRegexConsistency:
    """Verify the regex matches the canonical actionspace taxonomy."""

    def test_pattern_matches_expected_format(self) -> None:
        assert _ACTIONSPACE_URN_PATTERN.match(
            "urn:coreason:actionspace:solver:clinical_extractor:v1"
        )

    def test_pattern_rejects_uppercase(self) -> None:
        assert not _ACTIONSPACE_URN_PATTERN.match(
            "urn:CoReason:actionspace:solver:test:v1"
        )

    def test_pattern_rejects_spaces(self) -> None:
        assert not _ACTIONSPACE_URN_PATTERN.match(
            "urn:coreason:actionspace:solver:test cap:v1"
        )


class TestGatewayRequestID:
    """Deterministic request ID computation."""

    def test_deterministic_hash(self) -> None:
        args = {"query": "test", "limit": 10}
        id1 = NATSGatewayProvider._compute_request_id(args)
        id2 = NATSGatewayProvider._compute_request_id(args)
        assert id1 == id2

    def test_different_args_different_ids(self) -> None:
        id1 = NATSGatewayProvider._compute_request_id({"a": 1})
        id2 = NATSGatewayProvider._compute_request_id({"b": 2})
        assert id1 != id2

    def test_key_ordering_invariant(self) -> None:
        """SHA-256 is computed over sort_keys=True JSON, so key order doesn't matter."""
        id1 = NATSGatewayProvider._compute_request_id({"z": 1, "a": 2})
        id2 = NATSGatewayProvider._compute_request_id({"a": 2, "z": 1})
        assert id1 == id2

    def test_id_length(self) -> None:
        result = NATSGatewayProvider._compute_request_id({"test": True})
        assert len(result) == 16  # Truncated SHA-256 hex


class TestNATSSubjectDerivation:
    """Verify NATS subject patterns derived from URNs."""

    def test_subject_formatting(self) -> None:
        urn = "urn:coreason:actionspace:solver:test:v1"
        subject = SUBJECT_TOOL_INVOKE.format(urn=urn.replace(":", "."))
        assert subject == "coreason.tool.urn.coreason.actionspace.solver.test.v1.invoke"

    def test_subject_contains_no_colons(self) -> None:
        urn = "urn:nlm:actionspace:oracle:mesh_lookup:v3"
        subject = SUBJECT_TOOL_INVOKE.format(urn=urn.replace(":", "."))
        assert ":" not in subject


class TestVolumetricGuard:
    """Validate the 10MB payload size enforcement."""

    @pytest.mark.asyncio
    async def test_gateway_not_connected_raises(self) -> None:
        gw = NATSGatewayProvider(nats_url="nats://localhost:4222")
        assert not gw.is_connected
        with pytest.raises(RuntimeError, match="NATS connection not established"):
            await gw.invoke_tool(
                "urn:coreason:actionspace:solver:test:v1",
                {"query": "test"},
            )

    def test_max_payload_constant(self) -> None:
        """Verify the 10MB limit matches the runtime WASM enclave limit."""
        assert MAX_PAYLOAD_BYTES == 10_485_760


class TestRegistryHydration:
    """Test matrix hydration logic (deterministic — no NATS needed)."""

    def test_validate_urn_rejects_invalid_in_matrix(self) -> None:
        """Invalid URNs in the compiled matrix must be skipped."""
        with pytest.raises(ValueError, match="URN Topology Breach"):
            NATSCapabilityRegistry.validate_urn("not:a:valid:urn")


# ===========================================================================
# Tier 2: NATS Integration Tests (require running NATS server)
# ===========================================================================


@requires_nats
class TestNATSRegistryIntegration:
    """Integration tests for NATSCapabilityRegistry against a real NATS server."""

    @pytest.fixture
    async def registry(self) -> AsyncGenerator[NATSCapabilityRegistry, None]:
        """Create and initialize a registry connected to the local NATS server."""
        reg = NATSCapabilityRegistry(nats_url="nats://localhost:4222")
        await reg.initialize()
        yield reg
        await reg.shutdown()

    @pytest.mark.asyncio
    async def test_register_and_resolve(self, registry: NATSCapabilityRegistry) -> None:
        urn = "urn:coreason:actionspace:solver:integration_test:v1"
        await registry.register_capability(
            urn=urn,
            clearance="PUBLIC",
            epistemic_status="DRAFT",
        )
        result = await registry.resolve_urn(urn)
        assert result["clearance"] == "PUBLIC"
        assert result["epistemic_status"] == "DRAFT"

    @pytest.mark.asyncio
    async def test_resolve_missing_raises(
        self, registry: NATSCapabilityRegistry
    ) -> None:
        with pytest.raises(KeyError, match="Geometrical topology fault"):
            await registry.resolve_urn(
                "urn:coreason:actionspace:solver:does_not_exist:v1"
            )

    @pytest.mark.asyncio
    async def test_get_epistemic_status(self, registry: NATSCapabilityRegistry) -> None:
        urn = "urn:coreason:actionspace:oracle:status_test:v1"
        await registry.register_capability(
            urn=urn,
            epistemic_status="PUBLISHED",
        )
        status = await registry.get_epistemic_status(urn)
        assert status == "PUBLISHED"

    @pytest.mark.asyncio
    async def test_get_epistemic_status_missing_returns_draft(
        self, registry: NATSCapabilityRegistry
    ) -> None:
        status = await registry.get_epistemic_status(
            "urn:coreason:actionspace:solver:nonexistent:v1"
        )
        assert status == "DRAFT"


@requires_nats
class TestNATSGatewayIntegration:
    """Integration tests for NATSGatewayProvider against a real NATS server."""

    @pytest.fixture
    async def gateway(self) -> AsyncGenerator[NATSGatewayProvider, None]:
        gw = NATSGatewayProvider(nats_url="nats://localhost:4222")
        await gw.connect()
        yield gw
        await gw.disconnect()

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self) -> None:
        gw = NATSGatewayProvider(nats_url="nats://localhost:4222")
        await gw.connect()
        assert gw.is_connected
        await gw.disconnect()
        assert not gw.is_connected

    @pytest.mark.asyncio
    async def test_discover_returns_list(self, gateway: NATSGatewayProvider) -> None:
        """Discovery should return a list (possibly empty if no providers registered)."""
        capabilities = await gateway.discover_capabilities(timeout=1.0)
        assert isinstance(capabilities, list)
