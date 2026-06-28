import re
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)


class BaseReranker:
    """Base interface for candidate list reranking."""

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        """Rerank candidates based on semantic relevance."""
        raise NotImplementedError


class CrossEncoderReranker(BaseReranker):
    """Reranker using a Cross-Encoder model.

    Attempts to load sentence-transformers CrossEncoder. Falls back to a token-overlap scoring
    algorithm if sentence-transformers is not installed, running efficiently in any environment.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._is_fallback = False

    def _load_model(self) -> None:
        """Lazy-load Cross-Encoder model."""
        if self._model is not None or self._is_fallback:
            return

        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            logger.info("Loaded CrossEncoder model successfully", model=self.model_name)
        except (ImportError, Exception):
            logger.warning(
                "sentence-transformers not installed or failed to load. "
                "Falling back to token-overlap scoring for CrossEncoderReranker."
            )
            self._is_fallback = True

    def _fallback_score(self, query: str, text: str) -> float:
        """Calculate basic overlap score between query and document text."""
        query_words = set(re.findall(r"\b\w+\b", query.lower()))
        text_words = set(re.findall(r"\b\w+\b", text.lower()))

        if not query_words:
            return 0.0

        # Calculate intersection
        intersection = query_words.intersection(text_words)
        # Jaccard-like score scaled to query
        score = len(intersection) / len(query_words)
        return float(score)

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        """Compute cross-attention relevance scores, sort, and return top_k candidates."""
        if not candidates:
            return []

        self._load_model()

        scored_candidates = []

        if self._is_fallback:
            for c in candidates:
                score = self._fallback_score(query, c["chunk_text"])
                scored_candidates.append((c, score))
        else:
            try:
                pairs = [(query, c["chunk_text"]) for c in candidates]
                scores = self._model.predict(pairs)
                for c, score in zip(candidates, scores):
                    scored_candidates.append((c, float(score)))
            except Exception as e:
                logger.error("Error running CrossEncoder model inference. Using fallback.", error=str(e))
                for c in candidates:
                    score = self._fallback_score(query, c["chunk_text"])
                    scored_candidates.append((c, score))

        # Sort candidates by their score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Build return list and append final scores
        results = []
        for c, score in scored_candidates[:top_k]:
            c["score"] = score
            results.append(c)

        return results
