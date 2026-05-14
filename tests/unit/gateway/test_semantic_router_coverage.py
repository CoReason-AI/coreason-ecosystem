# Copyright (c) 2026 CoReason, Inc.
"""
Real integration tests for the Hybrid Semantic Router — no mocks.

These tests exercise the full sentence-transformers + Aurelio semantic-router
pipeline using real model inference and real Aurelio route compilation.
"""
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.ipc as ipc
import pytest

from coreason_ecosystem.gateway.semantic_router import (
    HybridWeighting,
    IntentWeighting,
    ScoreCalibration,
    SemanticRouter,
    _build_precomputed_encoder,
)


@pytest.fixture
def rich_arrow_matrix(tmp_path: Path) -> Path:
    """Arrow matrix with realistic multi-field descriptions for integration tests."""
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


@pytest.fixture
def no_description_arrow_matrix(tmp_path: Path) -> Path:
    """Arrow matrix where a capability has NO description fields (URN fallback)."""
    arrow_path = tmp_path / "no_desc_matrix.arrow"

    dummy_data = [
        {
            "urn": "urn:coreason:actionspace:solver:mystery_tool:v1",
            "congruence_score": 0.92,
            "description_instruction": "",
            "description_affordance": "",
            "description_bounds": "",
            "description_routing": "",
            "embedding_instruction": [1.0, 0.0] + [0.0] * 382,
            "embedding_affordance": [0.0, 1.0] + [0.0] * 382,
            "embedding_bounds": [1.0, 1.0] + [0.0] * 382,
            "embedding_routing": [0.5, 0.5] + [0.0] * 382,
        },
    ]

    table = pa.Table.from_pylist(dummy_data)
    with pa.OSFile(str(arrow_path), "wb") as sink:
        with pa.RecordBatchFileWriter(sink, table.schema) as writer:
            writer.write_table(table)

    return arrow_path


# ---------------------------------------------------------------
# Real encoder initialization tests (sentence-transformers)
# ---------------------------------------------------------------


def test_init_encoder_real() -> None:
    """Real: sentence-transformers initializes and encodes text."""
    router = SemanticRouter(Path("nonexistent.arrow"))
    router._init_encoder("all-MiniLM-L6-v2")
    assert router._encoder is not None

    embedding = router.generate_query_embedding("extract data from PDF")
    assert len(embedding) == 384
    # Normalized embedding: magnitude ≈ 1.0
    import numpy as np
    mag = float(np.linalg.norm(embedding))
    assert abs(mag - 1.0) < 0.01


def test_init_encoder_idempotent() -> None:
    """Encoder init is idempotent — second call is a no-op."""
    router = SemanticRouter(Path("nonexistent.arrow"))
    router._init_encoder("all-MiniLM-L6-v2")
    first_encoder = router._encoder
    router._init_encoder("all-MiniLM-L6-v2")
    assert router._encoder is first_encoder


# ---------------------------------------------------------------
# Real Aurelio initialization tests (full pipeline)
# ---------------------------------------------------------------


def test_aurelio_init_real(rich_arrow_matrix: Path) -> None:
    """Real: Full Aurelio router initialization with sentence-transformers."""
    router = SemanticRouter(rich_arrow_matrix)
    router._init_aurelio("all-MiniLM-L6-v2")
    assert router._aurelio_available is True
    assert router._aurelio_router is not None


def test_aurelio_init_with_urn_fallback_utterance(
    no_description_arrow_matrix: Path,
) -> None:
    """Real: Aurelio init falls back to URN name when descriptions are empty."""
    router = SemanticRouter(no_description_arrow_matrix)
    router._init_aurelio("all-MiniLM-L6-v2")
    assert router._aurelio_available is True


def test_aurelio_init_empty_registry() -> None:
    """Real: Aurelio init skips when registry is empty."""
    router = SemanticRouter(Path("nonexistent.arrow"))
    router.registry = []
    router._init_aurelio()
    assert not router._aurelio_available


def test_aurelio_init_idempotent(rich_arrow_matrix: Path) -> None:
    """Real: Second _init_aurelio call is a no-op."""
    router = SemanticRouter(rich_arrow_matrix)
    router._init_aurelio("all-MiniLM-L6-v2")
    first_router = router._aurelio_router
    router._init_aurelio("all-MiniLM-L6-v2")
    assert router._aurelio_router is first_router


# ---------------------------------------------------------------
# Real holistic scoring tests (Aurelio vector injection)
# ---------------------------------------------------------------


def test_score_holistic_with_vector(rich_arrow_matrix: Path) -> None:
    """Real: Aurelio scores capabilities using a pre-computed vector."""
    router = SemanticRouter(rich_arrow_matrix)
    router._init_aurelio("all-MiniLM-L6-v2")
    assert router._aurelio_available

    # Generate a real query vector
    query_vec = router.generate_query_embedding("extract data from PDF documents")
    scores = router._score_holistic(query_vec)

    # Should return at least some scores (Aurelio thresholding may filter some)
    assert isinstance(scores, dict)
    # All returned scores should be floats
    for urn, score in scores.items():
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


def test_score_holistic_when_unavailable() -> None:
    """Holistic scoring returns empty dict when Aurelio is unavailable."""
    router = SemanticRouter(Path("nonexistent.arrow"))
    assert router._aurelio_available is False
    scores = router._score_holistic([0.0] * 384)
    assert scores == {}


# ---------------------------------------------------------------
# Real end-to-end hybrid routing tests
# ---------------------------------------------------------------


def test_route_intent_hybrid_full_pipeline(rich_arrow_matrix: Path) -> None:
    """Real: Full hybrid routing with real encoder + real Aurelio."""
    router = SemanticRouter(rich_arrow_matrix)
    router._init_aurelio("all-MiniLM-L6-v2")
    assert router._aurelio_available

    # Generate real query vector
    query_vec = router.generate_query_embedding("extract structured data from PDF")

    # Build real intent embeddings from the same encoder
    intent = {
        "instruction": router.generate_query_embedding("extract structured data"),
        "affordance": router.generate_query_embedding("parse PDF to JSON"),
        "bounds": router.generate_query_embedding("max 50MB UTF-8 input"),
        "routing": router.generate_query_embedding("NLP data extraction"),
    }

    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)
    hybrid = HybridWeighting(w_holistic=0.3, w_wells=0.7)

    results = router.route_intent(
        intent,
        weighting,
        min_score=0.01,  # Low threshold to ensure we get results
        hybrid=hybrid,
        query_vector=query_vec,
    )

    assert isinstance(results, list)
    # At minimum, the data_extract capability should survive congruence gate
    # (bad_tool is at 0.60 congruence and is excluded by _score_wells)
    assert "urn:coreason:actionspace:oracle:bad_tool:v1" not in results


def test_route_intent_hybrid_with_query_text_fallback(
    rich_arrow_matrix: Path,
) -> None:
    """Real: Hybrid routing using query_text (encoder encodes once at route_intent)."""
    router = SemanticRouter(rich_arrow_matrix)
    router._init_aurelio("all-MiniLM-L6-v2")
    assert router._aurelio_available

    intent = {
        "instruction": router.generate_query_embedding("write records to database"),
        "affordance": router.generate_query_embedding("insert upsert operations"),
        "bounds": router.generate_query_embedding("max 1000 records"),
        "routing": router.generate_query_embedding("database write pipeline"),
    }

    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)
    hybrid = HybridWeighting(w_holistic=0.3, w_wells=0.7)

    results = router.route_intent(
        intent,
        weighting,
        min_score=0.01,
        hybrid=hybrid,
        query_text="write records to database",
    )

    assert isinstance(results, list)


def test_route_intent_hybrid_with_calibration(rich_arrow_matrix: Path) -> None:
    """Real: Hybrid routing with ScoreCalibration applied."""
    router = SemanticRouter(rich_arrow_matrix)
    router._init_aurelio("all-MiniLM-L6-v2")
    assert router._aurelio_available

    query_vec = router.generate_query_embedding("extract data from documents")

    intent = {
        "instruction": router.generate_query_embedding("extract structured data"),
        "affordance": router.generate_query_embedding("parse PDF to JSON"),
        "bounds": router.generate_query_embedding("max 50MB UTF-8 input"),
        "routing": router.generate_query_embedding("NLP data extraction"),
    }

    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)
    calibration = ScoreCalibration(holistic_exponent=2.0, wells_exponent=0.5)
    hybrid = HybridWeighting(w_holistic=0.3, w_wells=0.7, calibration=calibration)

    results = router.route_intent(
        intent,
        weighting,
        min_score=0.01,
        hybrid=hybrid,
        query_vector=query_vec,
    )

    assert isinstance(results, list)


def test_route_intent_backward_compatible(rich_arrow_matrix: Path) -> None:
    """Real: multi-well-only routing (no hybrid, no Aurelio) still works."""
    router = SemanticRouter(rich_arrow_matrix)

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


def test_route_intent_hybrid_aurelio_unavailable_degrades(
    rich_arrow_matrix: Path,
) -> None:
    """Real: Hybrid requested but Aurelio not initialized — degrades gracefully."""
    router = SemanticRouter(rich_arrow_matrix)
    # Do NOT call _init_aurelio — test degradation path

    intent = {
        "instruction": [1.0, 0.0] + [0.0] * 382,
        "affordance": [0.0, 1.0] + [0.0] * 382,
        "bounds": [1.0, 1.0] + [0.0] * 382,
        "routing": [0.5, 0.5] + [0.0] * 382,
    }

    hybrid = HybridWeighting(w_holistic=0.3, w_wells=0.7)
    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)

    results = router.route_intent(
        intent,
        weighting,
        min_score=0.5,
        hybrid=hybrid,
        query_text="extract data",
    )

    assert len(results) >= 1
    assert results[0] == "urn:coreason:actionspace:solver:data_extract:v1"


def test_route_intent_hybrid_no_vector_no_text_no_encoder(
    rich_arrow_matrix: Path,
) -> None:
    """Real: Aurelio available but no query_vector, no query_text → multi-well only."""
    router = SemanticRouter(rich_arrow_matrix)
    router._init_aurelio("all-MiniLM-L6-v2")

    intent = {
        "instruction": [1.0, 0.0] + [0.0] * 382,
        "affordance": [0.0, 1.0] + [0.0] * 382,
        "bounds": [1.0, 1.0] + [0.0] * 382,
        "routing": [0.5, 0.5] + [0.0] * 382,
    }

    hybrid = HybridWeighting(w_holistic=0.3, w_wells=0.7)
    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)

    results = router.route_intent(
        intent,
        weighting,
        min_score=0.5,
        hybrid=hybrid,
        query_text=None,
        query_vector=None,
    )

    assert isinstance(results, list)


# ---------------------------------------------------------------
# PrecomputedEncoder real tests
# ---------------------------------------------------------------


def test_precomputed_encoder_real() -> None:
    """Real: PrecomputedEncoder builds and replays vectors."""
    encoder = _build_precomputed_encoder()
    assert encoder is not None
    assert encoder.name == "precomputed"

    test_vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    encoder.set_embeddings(test_vectors)
    result = encoder(["doc1", "doc2"])
    assert result == test_vectors


def test_precomputed_encoder_fallback_zeros() -> None:
    """Real: PrecomputedEncoder without set_embeddings returns zero vectors."""
    encoder = _build_precomputed_encoder()
    assert encoder is not None

    result = encoder(["doc1", "doc2"])
    assert len(result) == 2
    assert all(v == 0.0 for v in result[0])
