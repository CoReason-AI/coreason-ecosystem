# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""
Quality-Weighted Semantic Router using ONNX for the Ecosystem Gateway.

This module provides intent-based dynamic weighting and leverages ONNX runtime
for vector inference to ensure low-latency, non-bloated semantic routing
of URN capabilities.
"""

import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc
from pathlib import Path
from loguru import logger
from typing import Any, Dict, List, Tuple


class IntentWeighting:
    def __init__(
        self,
        w_inst: float = 0.25,
        w_aff: float = 0.25,
        w_bounds: float = 0.25,
        w_routing: float = 0.25,
    ):
        self.w_inst = w_inst
        self.w_aff = w_aff
        self.w_bounds = w_bounds
        self.w_routing = w_routing


class SemanticRouter:
    def __init__(self, compiled_matrix_arrow_path: Path):
        self.matrix_path = compiled_matrix_arrow_path
        self.registry: List[Dict[str, Any]] = []
        self._onnx_session: Any = None
        self._tokenizer: Any = None
        self._load_registry()

    def _load_registry(self) -> None:
        """Loads the capability metadata and embeddings using Arrow IPC."""
        if not self.matrix_path.exists():
            logger.warning(
                f"Arrow registry not found at {self.matrix_path}. Router will be empty."
            )
            return

        try:
            with pa.OSFile(str(self.matrix_path), "rb") as source:
                with ipc.RecordBatchFileReader(source) as reader:  # type: ignore
                    table = reader.read_all()
                    self.registry = table.to_pylist()
            logger.info(
                f"Loaded {len(self.registry)} capabilities into Semantic Router from Arrow IPC."
            )
        except Exception as e:
            logger.error(f"Failed to load Arrow registry: {e}")

    def _init_onnx(self, model_path: str = "model.onnx") -> None:
        """Initialize the ONNX inference session and tokenizer for query embedding."""
        if self._onnx_session is not None:
            return

        try:
            import onnxruntime as ort  # type: ignore
            from transformers import AutoTokenizer

            # Using sentence-transformers/all-MiniLM-L6-v2 tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                "sentence-transformers/all-MiniLM-L6-v2"  # nosec B615
            )

            if Path(model_path).exists():
                self._onnx_session = ort.InferenceSession(model_path)
            else:
                logger.warning(
                    f"ONNX model not found at {model_path}. Query encoding will fail."
                )

        except ImportError as e:
            logger.error(
                f"Failed to initialize ONNX runtime: {e}. Please ensure onnxruntime and transformers are installed."
            )

    def generate_query_embedding_onnx(self, query_text: str) -> List[float]:
        """Encode query text into embedding using ONNX runtime to prevent PyTorch bloat."""
        if not self._tokenizer or not self._onnx_session:
            raise RuntimeError(
                "ONNX inference session is not initialized. Call _init_onnx() first."
            )

        inputs = self._tokenizer(
            query_text, return_tensors="np", padding=True, truncation=True
        )

        # Determine inputs expected by ONNX model. MiniLM typically expects these 3
        ort_inputs = {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"],
            "token_type_ids": inputs["token_type_ids"],
        }

        # Handle cases where the model doesn't use token_type_ids
        expected_inputs = [i.name for i in self._onnx_session.get_inputs()]
        ort_inputs = {k: v for k, v in ort_inputs.items() if k in expected_inputs}

        ort_outputs = self._onnx_session.run(None, ort_inputs)

        # mean pooling
        last_hidden_state = ort_outputs[0]
        attention_mask = inputs["attention_mask"]

        input_mask_expanded = np.expand_dims(attention_mask, -1)
        sum_embeddings = np.sum(last_hidden_state * input_mask_expanded, 1)
        sum_mask = np.clip(np.sum(input_mask_expanded, 1), a_min=1e-9, a_max=None)
        embeddings = sum_embeddings / sum_mask

        # L2 normalize
        norm = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.clip(norm, a_min=1e-12, a_max=None)

        return list(embeddings[0].tolist())

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (n1 * n2))

    def route_intent(
        self,
        intent_embeddings: Dict[str, List[float]],
        weighting: IntentWeighting,
        min_score: float = 0.70,
    ) -> List[str]:
        """
        Routes an intent by scoring the local registry against the 4 multi-well embeddings,
        applying dynamic intent weighting, and filtering by congruence quality.
        """
        if not self.registry:
            return []

        results: List[Tuple[float, str]] = []
        for capability in self.registry:
            # Enforce Congruence Guillotine:
            congruence = capability.get("congruence_score", 0.0)
            if congruence < 0.85:
                continue

            emb_inst = capability.get("embedding_instruction") or [0.0] * 384
            emb_aff = capability.get("embedding_affordance") or [0.0] * 384
            emb_bounds = capability.get("embedding_bounds") or [0.0] * 384
            emb_routing = capability.get("embedding_routing") or [0.0] * 384

            s_inst = self._cosine_similarity(
                intent_embeddings.get("instruction", [0.0] * 384), emb_inst
            )
            s_aff = self._cosine_similarity(
                intent_embeddings.get("affordance", [0.0] * 384), emb_aff
            )
            s_bounds = self._cosine_similarity(
                intent_embeddings.get("bounds", [0.0] * 384), emb_bounds
            )
            s_routing = self._cosine_similarity(
                intent_embeddings.get("routing", [0.0] * 384), emb_routing
            )

            # Quality-weighted semantic score
            base_score = (
                (s_inst * weighting.w_inst)
                + (s_aff * weighting.w_aff)
                + (s_bounds * weighting.w_bounds)
                + (s_routing * weighting.w_routing)
            )

            # Adjust by congruence score
            final_score = base_score * congruence

            if final_score >= min_score:
                results.append((final_score, str(capability.get("urn"))))

        results.sort(key=lambda x: x[0], reverse=True)
        return [urn for score, urn in results]
