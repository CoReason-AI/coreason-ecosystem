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


def test_semantic_router_onnx_execution_mock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from unittest.mock import MagicMock
    import sys
    import numpy as np

    mock_ort = MagicMock()
    mock_session = MagicMock()
    mock_ort.InferenceSession.return_value = mock_session
    monkeypatch.setitem(sys.modules, "onnxruntime", mock_ort)

    # Mock Path.exists to return True for the model path
    model_path = tmp_path / "model.onnx"
    model_path.touch()

    router = SemanticRouter(Path("nonexistent.arrow"))
    
    # Test RuntimeError before init
    with pytest.raises(RuntimeError, match="not initialized"):
        router.generate_query_embedding_onnx("test")

    # Mock tokenizer
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {
        "input_ids": np.array([[1, 2, 3]]),
        "attention_mask": np.array([[1, 1, 1]]),
        "token_type_ids": np.array([[0, 0, 0]]),
    }
    
    # Patch transformers.AutoTokenizer.from_pretrained
    mock_transformers = MagicMock()
    mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    # Call _init_onnx (covers line 83)
    router._init_onnx(str(model_path))
    assert router._onnx_session is not None

    # Call _init_onnx again (covers line 71 early return)
    router._init_onnx(str(model_path))

    # Mock session.run output (mean pooling simulation)
    # output shape (batch_size, seq_len, hidden_size)
    mock_session.run.return_value = [np.random.rand(1, 3, 384)]
    mock_session.get_inputs.return_value = [
        MagicMock(name="input_ids"),
        MagicMock(name="attention_mask"),
        MagicMock(name="token_type_ids"),
    ]

    embedding = router.generate_query_embedding_onnx("test query")
    assert len(embedding) == 384


def test_semantic_router_arrow_load_error(tmp_path: Path) -> None:
    # Create a corrupted arrow file
    corrupt_path = tmp_path / "corrupt.arrow"
    corrupt_path.write_text("not arrow data")

    router = SemanticRouter(corrupt_path)
    # Should handle exception and registry should be empty
    assert router.registry == []
