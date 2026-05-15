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
Hybrid Semantic Router for the Ecosystem Gateway.

Implements a two-stage routing architecture:

1. **Holistic stage** (Aurelio semantic-router) — coarse-grained "totality of meaning"
   matching. Each URN capability is registered as an Aurelio Route with its
   description as utterance examples. The Aurelio router returns an aggregated
   similarity score per capability.

2. **Multi-well stage** (CoReason proprietary) — fine-grained 4-dimensional
   scoring across instruction, affordance, bounds, and routing embedding wells.
   Applies the congruence quality gate and dynamic IntentWeighting.

3. **Hybrid fusion** — configurable weighted combination of both scores, with
   the ability to adjust the holistic-vs-well balance per query via
   HybridWeighting.

Embedding inference is delegated to sentence-transformers (Borrow-vs-Build
mandate).  The multi-dimensional scoring logic, congruence gating, and dynamic
IntentWeighting remain as core CoReason business value.

Performance optimizations (v2):
- PrecomputedEncoder eliminates the double-encode penalty: the query is encoded
  once by sentence-transformers, and the resulting vector is injected into
  Aurelio via its native ``vector=`` parameter.
- ScoreCalibration provides optional non-linear scaling to align Aurelio and
  multi-well score distributions before blending.
"""

import math
import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc
from pathlib import Path
from loguru import logger
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Weighting & calibration configuration
# ---------------------------------------------------------------------------


class IntentWeighting:
    """Dynamic per-query weight distribution across the 4 semantic wells."""

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


class ScoreCalibration:
    """Optional non-linear score calibration applied before fusion blending.

    When the Aurelio holistic score and the CoReason multi-well score use
    different internal normalization, a raw 0.8 from Aurelio may not carry
    the same semantic confidence as a 0.8 from the multi-well scorer.

    ScoreCalibration applies a power-law scaling ``score^exponent`` to each
    signal independently before they are blended by HybridWeighting, ensuring
    the two distributions are calibrated.

    Attributes:
        holistic_exponent: Power exponent for Aurelio holistic scores.
                           >1.0 suppresses mid-range scores (sharper),
                           <1.0 boosts mid-range scores (flatter).
        wells_exponent:    Power exponent for multi-well composite scores.
    """

    def __init__(
        self,
        holistic_exponent: float = 1.0,
        wells_exponent: float = 1.0,
    ):
        self.holistic_exponent = holistic_exponent
        self.wells_exponent = wells_exponent

    def calibrate_holistic(self, score: float) -> float:
        """Apply non-linear calibration to a holistic score."""
        return math.pow(max(0.0, min(1.0, score)), self.holistic_exponent)

    def calibrate_wells(self, score: float) -> float:
        """Apply non-linear calibration to a multi-well score."""
        return math.pow(max(0.0, min(1.0, score)), self.wells_exponent)


class HybridWeighting:
    """Configurable balance between holistic (Aurelio) and multi-well (CoReason) scores.

    Attributes:
        w_holistic: Weight for the Aurelio holistic similarity score (0.0-1.0).
        w_wells:    Weight for the CoReason multi-well composite score (0.0-1.0).
                    Must satisfy w_holistic + w_wells = 1.0.
        calibration: Optional ScoreCalibration for non-linear score alignment.
    """

    def __init__(
        self,
        w_holistic: float = 0.30,
        w_wells: float = 0.70,
        calibration: Optional[ScoreCalibration] = None,
    ):
        total = w_holistic + w_wells
        # Normalize to guarantee sum = 1.0
        self.w_holistic = w_holistic / total
        self.w_wells = w_wells / total
        self.calibration = calibration


# ---------------------------------------------------------------------------
# PrecomputedEncoder — eliminates the double-encode penalty
# ---------------------------------------------------------------------------


def _build_precomputed_encoder() -> Optional[Any]:
    """Build a lightweight DenseEncoder that returns pre-injected vectors.

    This encoder is used exclusively during Aurelio route *indexing* (document
    encoding).  At query time, pre-computed vectors are passed directly to
    Aurelio via ``vector=``, bypassing the encoder entirely.

    Returns None if the semantic-router package is not installed.
    """
    try:
        from typing import ClassVar
        from pydantic import ConfigDict
        from semantic_router.encoders.base import DenseEncoder
    except ImportError:
        return None

    class PrecomputedEncoder(DenseEncoder):
        """A DenseEncoder that stores and replays pre-computed embeddings.

        Used to bridge CoReason's sentence-transformers pipeline to the
        Aurelio SemanticRouter without double-encoding.  Document embeddings
        are injected via ``set_embeddings`` before route compilation.
        """

        name: str = "precomputed"
        _vectors: List[List[float]] = []

        model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

        def set_embeddings(self, vectors: List[List[float]]) -> None:
            """Inject pre-computed document embeddings for route indexing."""
            object.__setattr__(self, "_vectors", vectors)

        def __call__(self, docs: List[Any]) -> List[List[float]]:
            """Return pre-computed vectors during route indexing.

            For query-time encoding this is never called — we pass vectors
            directly via Aurelio's ``vector=`` parameter.
            """
            if self._vectors:
                return self._vectors
            # Fallback: return zero vectors (should not happen in practice)
            return [[0.0] * 384] * len(docs)

    return PrecomputedEncoder()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class SemanticRouter:
    """Hybrid two-stage semantic router for URN capability matching.

    Stage 1 — Aurelio SemanticRouter for holistic "totality of meaning" matching.
    Stage 2 — CoReason multi-well scorer for fine-grained 4D intent scoring.
    Fusion  — Weighted combination controlled by HybridWeighting.

    When Aurelio dependencies are unavailable, the router gracefully degrades
    to multi-well-only scoring (backward compatible).
    """

    def __init__(self, compiled_matrix_arrow_path: Path):
        self.matrix_path = compiled_matrix_arrow_path
        self.registry: List[Dict[str, Any]] = []
        self._encoder: Any = None
        self._aurelio_router: Any = None
        self._aurelio_available: bool = False
        self._load_registry()

    # ------------------------------------------------------------------
    # Registry loading (Arrow IPC)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Encoder initialization (sentence-transformers — Borrow-vs-Build)
    # ------------------------------------------------------------------

    def _init_encoder(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the sentence-transformers encoder (Borrow-vs-Build mandate).

        Replaces the proprietary ONNX tokenize→forward→pool→normalize pipeline
        with the standard sentence-transformers library.
        """
        if self._encoder is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(model_name)
            logger.info(f"Initialized sentence-transformers encoder: {model_name}")
        except ImportError as e:
            logger.error(
                f"Failed to initialize encoder: {e}. "
                "Please install sentence-transformers."
            )

    def generate_query_embedding(self, query_text: str) -> List[float]:
        """Encode query text into embedding via sentence-transformers.

        Delegates tokenization, inference, mean pooling, and L2 normalization
        to the sentence-transformers library (Borrow-vs-Build mandate).
        """
        if self._encoder is None:
            raise RuntimeError(
                "Encoder is not initialized. Call _init_encoder() first."
            )

        embedding = self._encoder.encode(query_text, normalize_embeddings=True)
        return list(embedding.tolist())

    # ------------------------------------------------------------------
    # Stage 1: Aurelio holistic routing (Borrow-vs-Build — OSS)
    # ------------------------------------------------------------------

    def _init_aurelio(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the Aurelio SemanticRouter with Routes derived from the
        capability registry.

        Each registered capability becomes an Aurelio Route whose utterances
        are constructed from the capability's descriptive metadata fields
        (instruction, affordance, bounds, routing tags).  This gives the
        Aurelio router enough semantic surface area to perform holistic
        similarity matching.

        Uses a PrecomputedEncoder to avoid double-encoding: utterances are
        encoded once via sentence-transformers, and the resulting vectors are
        injected into Aurelio's index.  At query time, pre-computed query
        vectors are passed directly via Aurelio's ``vector=`` parameter.
        """
        if self._aurelio_router is not None:
            return

        try:
            from semantic_router import Route as AurelioRoute
            from semantic_router.routers import SemanticRouter as AurelioSemanticRouter
        except ImportError:
            logger.warning(
                "Aurelio semantic-router not installed. "
                "Falling back to multi-well-only scoring."
            )
            self._aurelio_available = False
            return

        if not self.registry:
            logger.warning("Registry empty — skipping Aurelio initialization.")
            self._aurelio_available = False
            return

        # Ensure our own encoder is ready for pre-computing utterance embeddings
        self._init_encoder(model_name)
        if self._encoder is None:
            logger.warning(
                "sentence-transformers encoder unavailable — "
                "skipping Aurelio initialization."
            )
            self._aurelio_available = False
            return

        # Build routes and pre-compute all utterance embeddings in a single batch
        routes: List[Any] = []
        all_utterances: List[str] = []
        utterance_route_map: List[int] = []  # maps utterance index → route index

        for route_idx, capability in enumerate(self.registry):
            urn = capability.get("urn", "unknown")
            # Build utterances from the 4 descriptive metadata fields.
            # These give the holistic router enough semantic context.
            utterances: List[str] = []
            for field in (
                "description_instruction",
                "description_affordance",
                "description_bounds",
                "description_routing",
            ):
                text = capability.get(field)
                if text and isinstance(text, str) and text.strip():
                    utterances.append(text.strip())

            # Fallback: use URN name as a minimal utterance
            if not utterances:
                # Extract human-readable name from URN
                parts = urn.split(":")
                name_part = parts[-2] if len(parts) >= 2 else urn
                utterances = [name_part.replace("_", " ")]

            routes.append(
                AurelioRoute(
                    name=urn,
                    utterances=utterances,
                    metadata={
                        "congruence_score": capability.get("congruence_score", 0.0),
                    },
                )
            )
            all_utterances.extend(utterances)
            utterance_route_map.extend([route_idx] * len(utterances))

        # Batch-encode all utterances once via sentence-transformers
        all_vectors = self._encoder.encode(
            all_utterances, normalize_embeddings=True
        ).tolist()

        # Build a PrecomputedEncoder that will replay these vectors during
        # Aurelio's route indexing phase
        precomputed = _build_precomputed_encoder()
        if precomputed is None:
            self._aurelio_available = False
            return

        precomputed.set_embeddings(all_vectors)

        try:
            self._aurelio_router = AurelioSemanticRouter(
                encoder=precomputed,
                routes=routes,
                auto_sync=None,
            )
            self._aurelio_available = True
            logger.info(
                f"Aurelio holistic router initialized with {len(routes)} routes "
                f"({len(all_utterances)} utterances, zero double-encode)."
            )
        except Exception as e:
            logger.error(f"Aurelio router initialization failed: {e}")
            self._aurelio_available = False

    def _score_holistic(self, query_vector: List[float]) -> Dict[str, float]:
        """Score all capabilities holistically via Aurelio.

        Passes the pre-computed query vector directly to Aurelio via its
        ``vector=`` parameter, completely bypassing the encoder and eliminating
        the double-encode penalty.

        Returns a dict mapping URN → holistic similarity score (0.0-1.0).
        """
        if not self._aurelio_available or self._aurelio_router is None:
            return {}

        try:
            # Pass vector= directly — Aurelio skips its encoder (line 598 of base.py)
            results = self._aurelio_router(
                vector=query_vector,
                simulate_static=True,
                limit=None,
            )

            scores: Dict[str, float] = {}
            if isinstance(results, list):
                for rc in results:
                    if rc.name and rc.similarity_score is not None:
                        scores[rc.name] = float(rc.similarity_score)
            elif hasattr(results, "name") and results.name:
                if results.similarity_score is not None:
                    scores[results.name] = float(results.similarity_score)

            return scores
        except Exception as e:
            logger.warning(f"Aurelio holistic scoring failed: {e}")
            return {}

    # ------------------------------------------------------------------
    # Stage 2: Multi-well scoring (CoReason proprietary — core value)
    # ------------------------------------------------------------------

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Cosine similarity via numpy (Borrow-vs-Build mandate)."""
        a, b = np.asarray(v1), np.asarray(v2)
        n1, n2 = np.linalg.norm(a), np.linalg.norm(b)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(a, b) / (n1 * n2))

    def _score_wells(
        self,
        intent_embeddings: Dict[str, List[float]],
        weighting: IntentWeighting,
    ) -> Dict[str, Tuple[float, float]]:
        """Score all capabilities via the 4D multi-well mechanism.

        Returns a dict mapping URN → (well_score, congruence).
        well_score is the weighted combination of the 4 cosine similarities.
        Capabilities below the congruence gate (< 0.85) are excluded.
        """
        results: Dict[str, Tuple[float, float]] = {}

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

            urn = str(capability.get("urn"))
            results[urn] = (base_score, congruence)

        return results

    # ------------------------------------------------------------------
    # Fusion: Hybrid routing (Aurelio holistic × CoReason multi-well)
    # ------------------------------------------------------------------

    def route_intent(
        self,
        intent_embeddings: Dict[str, List[float]],
        weighting: IntentWeighting,
        min_score: float = 0.70,
        hybrid: Optional[HybridWeighting] = None,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
    ) -> List[str]:
        """Routes an intent using the hybrid two-stage scoring architecture.

        Stage 1 (Aurelio): If query_vector (or query_text) is provided and
                           Aurelio is initialized, computes holistic similarity
                           for each capability.  Uses the pre-computed vector
                           directly — zero double-encode penalty.
        Stage 2 (CoReason): Scores each capability across the 4 semantic wells
                            with dynamic IntentWeighting and congruence gating.
        Fusion:  Combines both scores using HybridWeighting.

        When Aurelio is unavailable or no query signal is provided, this method
        is fully backward compatible and uses multi-well-only scoring.

        Args:
            intent_embeddings: Dict with keys 'instruction', 'affordance',
                              'bounds', 'routing' → embedding vectors.
            weighting: Dynamic per-query weight distribution for the 4 wells.
            min_score: Minimum final score threshold.
            hybrid: Optional HybridWeighting to blend holistic and well scores.
                    If None, defaults to multi-well-only (backward compatible).
            query_text: Raw query text for Aurelio holistic matching. If both
                        query_text and query_vector are provided, query_vector
                        takes precedence.
            query_vector: Pre-computed query embedding for Aurelio. This is
                          the recommended parameter — it eliminates the
                          double-encode penalty by reusing the vector already
                          generated by sentence-transformers.

        Returns:
            List of URNs sorted by final score (highest first).
        """
        if not self.registry:
            return []

        # Stage 2: Multi-well scoring (always runs)
        well_results = self._score_wells(intent_embeddings, weighting)

        # Stage 1: Holistic scoring (conditional — requires Aurelio + vector)
        holistic_scores: Dict[str, float] = {}
        use_hybrid = (
            hybrid is not None
            and self._aurelio_available
            and (query_vector is not None or query_text is not None)
        )
        if use_hybrid:
            # Prefer pre-computed vector to avoid double-encode penalty.
            # If only query_text is provided, encode it once here.
            if query_vector is not None:
                h_vector = query_vector
            elif query_text is not None and self._encoder is not None:
                h_vector = self.generate_query_embedding(query_text)
            else:
                h_vector = None

            if h_vector is not None:
                holistic_scores = self._score_holistic(h_vector)
            else:
                use_hybrid = False

        # Fusion
        calibration = hybrid.calibration if (hybrid and hybrid.calibration) else None
        results: List[Tuple[float, str]] = []
        for urn, (well_score, congruence) in well_results.items():
            if use_hybrid and hybrid is not None:
                h_score = holistic_scores.get(urn, 0.0)

                # Apply optional non-linear calibration before blending
                if calibration is not None:
                    h_score = calibration.calibrate_holistic(h_score)
                    well_score = calibration.calibrate_wells(well_score)

                # Blend holistic and well scores
                blended = (h_score * hybrid.w_holistic) + (well_score * hybrid.w_wells)
                # Apply congruence quality gate
                final_score = blended * congruence
            else:
                # Backward compatible: multi-well only
                final_score = well_score * congruence

            if final_score >= min_score:
                results.append((final_score, urn))

        results.sort(key=lambda x: x[0], reverse=True)
        return [urn for _score, urn in results]
