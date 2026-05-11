# Copyright (c) 2026 CoReason, Inc.
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from coreason_ecosystem.gateway.semantic_router import SemanticRouter

def test_semantic_router_init_onnx_import_error():
    # Mock sys.modules to trigger ImportError for onnxruntime or transformers
    with patch.dict("sys.modules", {"onnxruntime": None}):
        router = SemanticRouter(Path("/nonexistent"))
        # This should hit the except ImportError block
        router._init_onnx("nonexistent_path")
        assert router._onnx_session is None
        assert router._tokenizer is None

def test_semantic_router_generate_embedding_no_init():
    router = SemanticRouter(Path("/nonexistent"))
    with pytest.raises(RuntimeError, match="ONNX inference session is not initialized"):
        router.generate_query_embedding_onnx("test")
