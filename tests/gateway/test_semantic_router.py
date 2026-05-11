# Copyright (c) 2026 CoReason, Inc.
import pytest
import pyarrow as pa
from pathlib import Path

from coreason_ecosystem.gateway.semantic_router import SemanticRouter, IntentWeighting


@pytest.fixture
def dummy_arrow_matrix(tmp_path: Path) -> Path:
    arrow_path = tmp_path / "compiled_matrix.arrow"

    # Create fake capabilities
    dummy_data = [
        {
            "urn": "urn:coreason:actionspace:solver:data_extract:v1",
            "congruence_score": 0.95,
            "embedding_instruction": [1.0, 0.0] + [0.0] * 382,
            "embedding_affordance": [0.0, 1.0] + [0.0] * 382,
            "embedding_bounds": [1.0, 1.0] + [0.0] * 382,
            "embedding_routing": [0.5, 0.5] + [0.0] * 382,
        },
        {
            "urn": "urn:coreason:actionspace:oracle:bad_tool:v1",
            "congruence_score": 0.60,  # Below 0.85, should be filtered
            "embedding_instruction": [1.0, 0.0] + [0.0] * 382,
            "embedding_affordance": [1.0, 0.0] + [0.0] * 382,
            "embedding_bounds": [1.0, 0.0] + [0.0] * 382,
            "embedding_routing": [1.0, 0.0] + [0.0] * 382,
        },
        {
            "urn": "urn:coreason:actionspace:effector:write_db:v1",
            "congruence_score": 0.90,
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


def test_semantic_router_loads_arrow(dummy_arrow_matrix: Path) -> None:
    router = SemanticRouter(dummy_arrow_matrix)
    assert len(router.registry) == 3
    assert (
        router.registry[0]["urn"] == "urn:coreason:actionspace:solver:data_extract:v1"
    )


def test_semantic_router_routing(dummy_arrow_matrix: Path) -> None:
    router = SemanticRouter(dummy_arrow_matrix)

    intent = {
        "instruction": [1.0, 0.0] + [0.0] * 382,
        "affordance": [0.0, 1.0] + [0.0] * 382,
        "bounds": [1.0, 1.0] + [0.0] * 382,
        "routing": [0.5, 0.5] + [0.0] * 382,
    }

    weighting = IntentWeighting(0.25, 0.25, 0.25, 0.25)

    # Route intent
    results = router.route_intent(intent, weighting, min_score=0.5)

    # Expect data_extract to be top due to exact match and high congruence
    # bad_tool is filtered out due to congruence < 0.85
    # write_db has lower cosine similarity
    assert len(results) >= 1
    assert results[0] == "urn:coreason:actionspace:solver:data_extract:v1"
    assert "urn:coreason:actionspace:oracle:bad_tool:v1" not in results


def test_semantic_router_onnx_init() -> None:
    # Just testing initialization gracefully without model
    router = SemanticRouter(Path("nonexistent.arrow"))
    router._init_onnx("fake_path.onnx")
    # Shouldn't crash, should just log warning
    assert router._onnx_session is None
