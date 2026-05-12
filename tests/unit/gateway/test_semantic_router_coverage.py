# Copyright (c) 2026 CoReason, Inc.
from pathlib import Path
from unittest.mock import patch

import pytest

from coreason_ecosystem.gateway.semantic_router import SemanticRouter


def test_semantic_router_init_onnx_import_error() -> None:
    """Cover lines 89-92: ImportError during ONNX init."""
    with patch.dict("sys.modules", {"onnxruntime": None}):
        router = SemanticRouter(Path("/nonexistent"))
        router._init_onnx("nonexistent_path")
        assert router._onnx_session is None
        assert router._tokenizer is None


def test_semantic_router_generate_embedding_no_init() -> None:
    """Cover lines 96-98: RuntimeError when session not initialized."""
    router = SemanticRouter(Path("/nonexistent"))
    with pytest.raises(RuntimeError, match="ONNX inference session is not initialized"):
        router.generate_query_embedding_onnx("test")
