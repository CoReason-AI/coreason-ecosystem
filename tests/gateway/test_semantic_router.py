# Copyright (c) 2026 CoReason, Inc.
"""
Tests for the Hybrid Semantic Router — deterministic and structural tests.

These tests validate the structural behavior of the router using
deterministic vector inputs. No mocks — all assertions are against real
objects and real math.
"""
import pytest
import pyarrow as pa
from pathlib import Path

from coreason_ecosystem.gateway.semantic_router import (
    SemanticRouter,
    IntentWeighting,
    HybridWeighting,
    ScoreCalibration,
)


@pytest.fixture
def dummy_arrow_matrix(tmp_path: Path) -> Path:
    arrow_path = tmp_path / "compiled_matrix.arrow"

    dummy_data = [
        {
            "urn": "urn:coreason:actionspace:solver:data_extract:v1",
            "congruence_score": 0.95,
            "description_instruction": "Extract structured data from documents",
            "description_affordance": "Parse PDF and HTML into JSON",
            "description_bounds": "Max 50MB input, UTF-8 only",
            "description_routing": "NLP solver data extraction pipeline",
            "embedding_instruction": [1.0, 0.0] + [0.0] * 382,
            "embedding_affordance": [0.0, 1.0] + [0.0] * 382,
            "embedding_bounds": [1.0, 1.0] + [0.0] * 382,
            "embedding_routing": [0.5, 0.5] + [0.0] * 382,
        },
        {
            "urn": "urn:coreason:actionspace:oracle:bad_tool:v1",
            "congruence_score": 0.60,  # Below 0.85, should be filtered
            "description_instruction": "Bad tool",
            "description_affordance": "",
            "description_bounds": "",
            "description_routing": "",
            "embedding_instruction": [1.0, 0.0] + [0.0] * 382,
            "embedding_affordance": [1.0, 0.0] + [0.0] * 382,
            "embedding_bounds": [1.0, 0.0] + [0.0] * 382,
            "embedding_routing": [1.0, 0.0] + [0.0] * 382,
        },
        {
            "urn": "urn:coreason:actionspace:effector:write_db:v1",
            "congruence_score": 0.90,
            "description_instruction": "Write records to database",
            "description_affordance": "Insert, upsert operations",
            "description_bounds": "Max 1000 records per batch",
            "description_routing": "Database effector write pipeline",
            "embedding_instruction": [0.0, 1.0] + [0.0] * 382,
            "embedding_affordance": [1.0, 0.0] + [0.0] * 382,
            "embedding_bounds": [0.0, 1.0] + [0.0] * 382,
            "embedding_routing": [1.0, 0.0] + [0.0] * 382,
        },
    ]

    table = pa.Table.from_pylist(dummy_data)
    with pa.OSFile(str(arrow_path), "wb") as sink:
        with pa.RecordBatchFileWriter(sink, table.schema) as writer:
            writer.write_table(table)

    return arrow_path


# ---------------------------------------------------------------
# Core routing tests (backward compatible — multi-well only)
# ---------------------------------------------------------------


def test_semantic_router_loads_arrow(dummy_arrow_matrix: Path) -> None:
    router = SemanticRouter(dummy_arrow_matrix)
    assert len(router.registry) == 3
    assert (
        router.registry[0]["urn"] == "urn:coreason:actionspace:solver:data_extract:v1"
    )


def test_semantic_router_routing(dummy_arrow_matrix: Path) -> None:
    """Backward-compatible: multi-well only (no hybrid, no query_text)."""
    router = SemanticRouter(dummy_arrow_matrix)

    intent = {
        "instruction": [1.0, 0.0] + [0.0] * 382,
        "affordance": [0.0, 1.0] + [0.0] * 382,
        "bounds": [1.0, 1.0] + [0.0] * 382,
        "routing": [0.5, 0.5] + [0.0] * 382,
    }

    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)
    results = router.route_intent(intent, weighting, min_score=0.5)

    assert len(results) >= 1
    assert results[0] == "urn:coreason:actionspace:solver:data_extract:v1"
    assert "urn:coreason:actionspace:oracle:bad_tool:v1" not in results


def test_semantic_router_empty_registry() -> None:
    router = SemanticRouter(Path("nonexistent.arrow"))
    router.registry = []
    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)
    assert router.route_intent({}, weighting) == []


def test_semantic_router_zero_cosine() -> None:
    router = SemanticRouter(Path("nonexistent.arrow"))
    v1 = [0.0] * 384
    v2 = [1.0] * 384
    assert router._cosine_similarity(v1, v2) == 0.0


# ---------------------------------------------------------------
# Encoder tests (real — no mocks)
# ---------------------------------------------------------------


def test_semantic_router_encoder_init() -> None:
    router = SemanticRouter(Path("nonexistent.arrow"))
    assert router._encoder is None


def test_semantic_router_generate_embedding_no_init() -> None:
    router = SemanticRouter(Path("nonexistent.arrow"))
    with pytest.raises(RuntimeError, match="Encoder is not initialized"):
        router.generate_query_embedding("test")


def test_semantic_router_encoder_idempotent() -> None:
    """Second init is a no-op when encoder is already set."""
    router = SemanticRouter(Path("nonexistent.arrow"))
    router._encoder = "already_initialized"
    router._init_encoder()
    assert router._encoder == "already_initialized"


# ---------------------------------------------------------------
# HybridWeighting tests
# ---------------------------------------------------------------


def test_hybrid_weighting_defaults() -> None:
    hw = HybridWeighting()
    assert abs(hw.w_holistic - 0.30) < 0.01
    assert abs(hw.w_wells - 0.70) < 0.01
    assert abs(hw.w_holistic + hw.w_wells - 1.0) < 1e-9


def test_hybrid_weighting_normalization() -> None:
    hw = HybridWeighting(w_holistic=1.0, w_wells=3.0)
    assert abs(hw.w_holistic - 0.25) < 0.01
    assert abs(hw.w_wells - 0.75) < 0.01
    assert abs(hw.w_holistic + hw.w_wells - 1.0) < 1e-9


def test_hybrid_weighting_custom() -> None:
    hw = HybridWeighting(w_holistic=0.5, w_wells=0.5)
    assert abs(hw.w_holistic - 0.5) < 0.01
    assert abs(hw.w_wells - 0.5) < 0.01


def test_hybrid_weighting_with_calibration() -> None:
    cal = ScoreCalibration(holistic_exponent=2.0, wells_exponent=0.5)
    hw = HybridWeighting(w_holistic=0.3, w_wells=0.7, calibration=cal)
    assert hw.calibration is not None
    assert hw.calibration.holistic_exponent == 2.0
    assert hw.calibration.wells_exponent == 0.5


def test_hybrid_weighting_no_calibration() -> None:
    hw = HybridWeighting()
    assert hw.calibration is None


# ---------------------------------------------------------------
# ScoreCalibration tests
# ---------------------------------------------------------------


def test_score_calibration_defaults() -> None:
    cal = ScoreCalibration()
    assert cal.holistic_exponent == 1.0
    assert cal.wells_exponent == 1.0


def test_score_calibration_identity() -> None:
    """With exponent=1.0, calibration is identity (no-op)."""
    cal = ScoreCalibration(holistic_exponent=1.0, wells_exponent=1.0)
    assert abs(cal.calibrate_holistic(0.8) - 0.8) < 1e-9
    assert abs(cal.calibrate_wells(0.5) - 0.5) < 1e-9


def test_score_calibration_sharpening() -> None:
    """With exponent>1.0, mid-range scores are suppressed."""
    cal = ScoreCalibration(holistic_exponent=2.0)
    # 0.8^2 = 0.64
    assert abs(cal.calibrate_holistic(0.8) - 0.64) < 1e-9
    # Perfect score unaffected: 1.0^2 = 1.0
    assert abs(cal.calibrate_holistic(1.0) - 1.0) < 1e-9
    # Zero unaffected: 0.0^2 = 0.0
    assert abs(cal.calibrate_holistic(0.0) - 0.0) < 1e-9


def test_score_calibration_flattening() -> None:
    """With exponent<1.0, mid-range scores are boosted."""
    cal = ScoreCalibration(wells_exponent=0.5)
    # 0.64^0.5 = 0.8
    assert abs(cal.calibrate_wells(0.64) - 0.8) < 1e-9


def test_score_calibration_clamps_input() -> None:
    """Scores outside [0.0, 1.0] are clamped before exponentiation."""
    cal = ScoreCalibration(holistic_exponent=2.0)
    # Negative → clamped to 0.0
    assert cal.calibrate_holistic(-0.5) == 0.0
    # >1.0 → clamped to 1.0
    assert abs(cal.calibrate_holistic(1.5) - 1.0) < 1e-9


# ---------------------------------------------------------------
# Hybrid routing tests (structural — graceful degradation)
# ---------------------------------------------------------------


def test_route_intent_hybrid_without_aurelio(dummy_arrow_matrix: Path) -> None:
    """Hybrid mode requested but Aurelio not initialized — degrades to multi-well."""
    router = SemanticRouter(dummy_arrow_matrix)

    intent = {
        "instruction": [1.0, 0.0] + [0.0] * 382,
        "affordance": [0.0, 1.0] + [0.0] * 382,
        "bounds": [1.0, 1.0] + [0.0] * 382,
        "routing": [0.5, 0.5] + [0.0] * 382,
    }

    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)
    hybrid = HybridWeighting(w_holistic=0.3, w_wells=0.7)

    results = router.route_intent(
        intent,
        weighting,
        min_score=0.5,
        hybrid=hybrid,
        query_text="extract data from PDF",
    )

    assert len(results) >= 1
    assert results[0] == "urn:coreason:actionspace:solver:data_extract:v1"


def test_route_intent_hybrid_no_query_text(dummy_arrow_matrix: Path) -> None:
    """Hybrid requested but no query_text/query_vector — uses multi-well only."""
    router = SemanticRouter(dummy_arrow_matrix)

    intent = {
        "instruction": [1.0, 0.0] + [0.0] * 382,
        "affordance": [0.0, 1.0] + [0.0] * 382,
        "bounds": [1.0, 1.0] + [0.0] * 382,
        "routing": [0.5, 0.5] + [0.0] * 382,
    }

    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)
    hybrid = HybridWeighting()

    results = router.route_intent(
        intent, weighting, min_score=0.5, hybrid=hybrid, query_text=None
    )

    assert len(results) >= 1


# ---------------------------------------------------------------
# Aurelio initialization tests (structural)
# ---------------------------------------------------------------


def test_aurelio_init_empty_registry() -> None:
    router = SemanticRouter(Path("nonexistent.arrow"))
    router.registry = []
    router._init_aurelio()
    assert not router._aurelio_available


def test_aurelio_init_idempotent() -> None:
    """Second _init_aurelio call is a no-op."""
    router = SemanticRouter(Path("nonexistent.arrow"))
    router._aurelio_router = "already_initialized"
    router._init_aurelio()
    assert router._aurelio_router == "already_initialized"


def test_score_holistic_when_unavailable() -> None:
    router = SemanticRouter(Path("nonexistent.arrow"))
    assert router._aurelio_available is False
    scores = router._score_holistic([0.0] * 384)
    assert scores == {}


# ---------------------------------------------------------------
# Arrow loading error handling
# ---------------------------------------------------------------


def test_semantic_router_arrow_load_error(tmp_path: Path) -> None:
    corrupt_path = tmp_path / "corrupt.arrow"
    corrupt_path.write_text("not arrow data")

    router = SemanticRouter(corrupt_path)
    assert router.registry == []


# ---------------------------------------------------------------
# Score wells (internal)
# ---------------------------------------------------------------


def test_score_wells_filters_low_congruence(dummy_arrow_matrix: Path) -> None:
    router = SemanticRouter(dummy_arrow_matrix)

    intent = {
        "instruction": [1.0, 0.0] + [0.0] * 382,
        "affordance": [1.0, 0.0] + [0.0] * 382,
        "bounds": [1.0, 0.0] + [0.0] * 382,
        "routing": [1.0, 0.0] + [0.0] * 382,
    }

    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)
    results = router._score_wells(intent, weighting)

    # bad_tool (congruence 0.60) should be excluded
    assert "urn:coreason:actionspace:oracle:bad_tool:v1" not in results
    # data_extract (congruence 0.95) and write_db (0.90) should be present
    assert "urn:coreason:actionspace:solver:data_extract:v1" in results
    assert "urn:coreason:actionspace:effector:write_db:v1" in results
